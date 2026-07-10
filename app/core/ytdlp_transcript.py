import json
import re
import time
from concurrent.futures import ThreadPoolExecutor
from typing import Callable

import yt_dlp
from yt_dlp.utils import DownloadError

from app.utils.segment_utils import make_segment
from app.utils.log_utils import log, log_error

_LIST_CACHE: dict[str, tuple[float, "TranscriptList"]] = {}
_LIST_CACHE_TTL_SECONDS = 300
_YDL_OPTS = {
    "skip_download": True,
    "quiet": True,
    "no_warnings": True,
    "noplaylist": True,
    "ignore_no_formats_error": True,
    "extractor_args": {
        "youtube": {
            "player_client": ["android", "web"],
        }
    },
}


class VideoUnavailable(Exception):
    pass


class TranscriptsDisabled(Exception):
    pass


class _NoTranscriptFound(Exception):
    pass


def _base_lang(code: str) -> str:
    return code.split("-")[0].lower()


def _lang_matches(track_code: str, requested: str) -> bool:
    if track_code == requested:
        return True
    return _base_lang(track_code) == _base_lang(requested)


def _language_display(code: str, is_generated: bool) -> str:
    if is_generated:
        return f"{code} (auto-generated)"
    return code


def _pick_subtitle_format(formats: list[dict]) -> dict | None:
    for ext in ("json3", "vtt", "srv3", "ttml"):
        match = next((fmt for fmt in formats if fmt.get("ext") == ext), None)
        if match:
            return match
    return formats[0] if formats else None


def _parse_json3(content: str) -> list:
    data = json.loads(content)
    segments = []

    for event in data.get("events", []):
        if "segs" not in event:
            continue

        text = "".join(part.get("utf8", "") for part in event["segs"]).strip()
        if not text:
            continue

        start = event.get("tStartMs", 0) / 1000.0
        duration = event.get("dDurationMs", 0) / 1000.0
        segments.append(make_segment(text=text, start=start, duration=duration))

    return segments


def _parse_vtt(content: str) -> list:
    segments = []
    blocks = re.split(r"\n\s*\n", content.strip())

    for block in blocks:
        lines = [line.strip() for line in block.splitlines() if line.strip()]
        if len(lines) < 2:
            continue

        timing_line = lines[1] if "-->" in lines[1] else lines[0]
        text_lines = lines[2:] if "-->" in lines[1] else lines[1:]
        if "-->" not in timing_line:
            continue

        start_raw, end_raw = [part.strip() for part in timing_line.split("-->")]
        start = _vtt_timestamp_to_seconds(start_raw)
        end = _vtt_timestamp_to_seconds(end_raw.split()[0])
        text = re.sub(r"<[^>]+>", "", " ".join(text_lines)).strip()

        if not text:
            continue

        segments.append(
            make_segment(text=text, start=start, duration=max(end - start, 0.0))
        )

    return segments


def _vtt_timestamp_to_seconds(value: str) -> float:
    value = value.replace(",", ".")
    parts = value.split(":")

    if len(parts) == 3:
        hours, minutes, seconds = parts
        return int(hours) * 3600 + int(minutes) * 60 + float(seconds)

    if len(parts) == 2:
        minutes, seconds = parts
        return int(minutes) * 60 + float(seconds)

    return float(parts[0])


def _parse_subtitle_content(content: str, ext: str) -> list:
    if ext == "json3":
        return _parse_json3(content)

    if ext in {"vtt", "srv3", "ttml"}:
        return _parse_vtt(content)

    try:
        return _parse_json3(content)
    except json.JSONDecodeError:
        return _parse_vtt(content)


class Transcript:
    def __init__(
        self,
        language: str,
        language_code: str,
        is_generated: bool,
        fetcher: Callable[[], list],
    ):
        self.language = language
        self.language_code = language_code
        self.is_generated = is_generated
        self._fetcher = fetcher
        self._cache: list | None = None

    def fetch(self) -> list:
        if self._cache is None:
            self._cache = self._fetcher()
        return self._cache

    def translate(self, lang_code: str) -> "Transcript":
        source = self

        def fetch_translated() -> list:
            from app.services.translation_service import google_translate_segments

            return google_translate_segments(source.fetch(), lang_code)

        return Transcript(
            language=_language_display(lang_code, is_generated=True),
            language_code=lang_code,
            is_generated=True,
            fetcher=fetch_translated,
        )


class TranscriptList:
    def __init__(self, transcripts: list[Transcript], fetcher: "_TranscriptFetcher | None" = None):
        self._transcripts = transcripts
        self._fetcher = fetcher

    def prefetch_for_langs(self, *lang_codes: str) -> None:
        if not self._fetcher:
            return

        needed: list[Transcript] = []
        for lang_code in lang_codes:
            try:
                needed.append(self.find_transcript([lang_code]))
            except _NoTranscriptFound:
                continue

        self._fetcher.prefetch_tracks(needed)

    def __iter__(self):
        return iter(self._transcripts)

    def __repr__(self) -> str:
        return repr(self._transcripts)

    def find_transcript(self, lang_codes: list[str]) -> Transcript:
        for lang_code in lang_codes:
            manual = next(
                (
                    transcript
                    for transcript in self._transcripts
                    if not transcript.is_generated
                    and _lang_matches(transcript.language_code, lang_code)
                ),
                None,
            )
            if manual:
                return manual

            generated = next(
                (
                    transcript
                    for transcript in self._transcripts
                    if transcript.is_generated
                    and _lang_matches(transcript.language_code, lang_code)
                ),
                None,
            )
            if generated:
                return generated

        raise _NoTranscriptFound(lang_codes)


class _TranscriptFetcher:
    def __init__(self, video_id: str):
        self.video_id = video_id
        self._ydl: yt_dlp.YoutubeDL | None = None
        self._info: dict | None = None

    def _ensure_info(self) -> dict:
        if self._info is not None:
            return self._info

        url = f"https://www.youtube.com/watch?v={self.video_id}"
        log(f"[_TranscriptFetcher._ensure_info] fetching info for {self.video_id}")

        try:
            self._ydl = yt_dlp.YoutubeDL(_YDL_OPTS)
            self._info = self._ydl.extract_info(url, download=False)
        except DownloadError as exc:
            message = str(exc).lower()
            if "unavailable" in message or "private" in message:
                log_error(f"[_TranscriptFetcher._ensure_info] video unavailable: {self.video_id}", exc)
                raise VideoUnavailable(str(exc)) from exc
            log_error(f"[_TranscriptFetcher._ensure_info] yt-dlp error: {self.video_id}", exc)
            raise

        if not self._info:
            log_error(f"[_TranscriptFetcher._ensure_info] empty info for {self.video_id}")
            raise VideoUnavailable(f"Video {self.video_id} is unavailable")

        log(f"[_TranscriptFetcher._ensure_info] ok for {self.video_id}")
        return self._info

    def prefetch_tracks(self, transcripts: list["Transcript"]) -> None:
        pending = [transcript for transcript in transcripts if transcript._cache is None]
        if len(pending) <= 1:
            for transcript in pending:
                transcript.fetch()
            return

        with ThreadPoolExecutor(max_workers=min(len(pending), 4)) as executor:
            list(executor.map(lambda transcript: transcript.fetch(), pending))

    def _download_segments(self, formats: list[dict]) -> list:
        ydl = self._ydl or yt_dlp.YoutubeDL(_YDL_OPTS)
        subtitle_format = _pick_subtitle_format(formats)

        if not subtitle_format or not subtitle_format.get("url"):
            log("[_TranscriptFetcher._download_segments] no subtitle format/url found")
            return []

        try:
            content = ydl.urlopen(subtitle_format["url"]).read().decode("utf-8", "replace")
            segments = _parse_subtitle_content(content, subtitle_format.get("ext", "json3"))
            log(f"[_TranscriptFetcher._download_segments] parsed {len(segments)} segments ({subtitle_format.get('ext')})")
            return segments
        except Exception as exc:
            log_error("[_TranscriptFetcher._download_segments] download/parse failed", exc)
            raise

    def build_transcript_list(self) -> TranscriptList:
        log(f"[_TranscriptFetcher.build_transcript_list] {self.video_id}")
        info = self._ensure_info()
        manual_subs = {
            language_code: formats
            for language_code, formats in (info.get("subtitles") or {}).items()
            if language_code != "live_chat"
        }
        auto_subs = info.get("automatic_captions") or {}
        video_lang = info.get("language") or "en"
        log(
            f"[_TranscriptFetcher.build_transcript_list] "
            f"manual={len(manual_subs)} langs={sorted(manual_subs)}, "
            f"auto={len(auto_subs)} langs={sorted(auto_subs)}, "
            f"video_lang={video_lang}"
        )

        transcripts: list[Transcript] = []

        for language_code, formats in manual_subs.items():
            transcripts.append(
                Transcript(
                    language=_language_display(language_code, is_generated=False),
                    language_code=language_code,
                    is_generated=False,
                    fetcher=lambda formats=formats: self._download_segments(formats),
                )
            )

        auto_lang_key = None
        for candidate in (video_lang, _base_lang(video_lang)):
            if candidate in auto_subs:
                auto_lang_key = candidate
                break

        if auto_lang_key:
            formats = auto_subs[auto_lang_key]
            transcripts.append(
                Transcript(
                    language=_language_display(auto_lang_key, is_generated=True),
                    language_code=auto_lang_key,
                    is_generated=True,
                    fetcher=lambda formats=formats: self._download_segments(formats),
                )
            )

        if not transcripts:
            log_error(f"[_TranscriptFetcher.build_transcript_list] transcripts disabled: {self.video_id}")
            raise TranscriptsDisabled(
                f"Transcripts are disabled for video {self.video_id}"
            )

        log(f"[_TranscriptFetcher.build_transcript_list] {len(transcripts)} tracks available")
        transcript_list = TranscriptList(transcripts, self)
        return transcript_list


class YouTubeTranscriptApi:
    def list(self, video_id: str) -> TranscriptList:
        log(f"[YouTubeTranscriptApi.list] video_id={video_id}")
        now = time.time()
        cached = _LIST_CACHE.get(video_id)
        if cached and now - cached[0] < _LIST_CACHE_TTL_SECONDS:
            log(f"[YouTubeTranscriptApi.list] cache hit for {video_id}")
            return cached[1]

        try:
            transcript_list = _TranscriptFetcher(video_id).build_transcript_list()
            _LIST_CACHE[video_id] = (now, transcript_list)
            return transcript_list
        except Exception as exc:
            log_error(f"[YouTubeTranscriptApi.list] failed for {video_id}", exc)
            raise
