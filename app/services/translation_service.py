from concurrent.futures import ThreadPoolExecutor

from deep_translator import GoogleTranslator

from app.utils.segment_utils import make_segment
from app.core.youtube import best_source_transcript
from app.utils.log_utils import log, log_error


def _find_transcript(transcript_list, lang_code: str):
    try:
        return transcript_list.find_transcript([lang_code])
    except Exception as exc:
        log(f"[_find_transcript] no transcript for {lang_code}: {type(exc).__name__}")
        return None


def fetch_transcript_for_lang(transcript_list, lang_code: str):
    log(f"[fetch_transcript_for_lang] lang={lang_code}")

    try:
        t = transcript_list.find_transcript([lang_code])
        segments = t.fetch()
        log(f"[fetch_transcript_for_lang] native transcript for {lang_code}, {len(segments)} segments")
        return segments, "native"
    except Exception as exc:
        log(f"[fetch_transcript_for_lang] no native transcript for {lang_code}: {type(exc).__name__}: {exc}")

    source = best_source_transcript(transcript_list)
    if source is None:
        log_error(f"[fetch_transcript_for_lang] no source available for {lang_code}")
        raise ValueError(f"No transcript source available for {lang_code}")

    log(f"[fetch_transcript_for_lang] translating from {source.language_code} -> {lang_code}")
    raw_segments = source.fetch()
    translated_segments = google_translate_segments(raw_segments, lang_code)

    return translated_segments, "gt_trans"


def fetch_transcript_pair(transcript_list, native_lang: str, target_lang: str):
    log(f"[fetch_transcript_pair] native={native_lang}, target={target_lang}")
    transcript_list.prefetch_for_langs(native_lang, target_lang)

    native_transcript = _find_transcript(transcript_list, native_lang)
    target_transcript = _find_transcript(transcript_list, target_lang)

    if native_transcript and target_transcript:
        log("[fetch_transcript_pair] both langs found, fetching in parallel")
        with ThreadPoolExecutor(max_workers=2) as executor:
            native_future = executor.submit(native_transcript.fetch)
            target_future = executor.submit(target_transcript.fetch)
            return native_future.result(), target_future.result()

    if native_transcript and not target_transcript:
        log(f"[fetch_transcript_pair] only native ({native_lang}), translating target")
        native_segments = native_transcript.fetch()
        target_segments, _ = fetch_transcript_for_lang(transcript_list, target_lang)
        return native_segments, target_segments

    if target_transcript and not native_transcript:
        log(f"[fetch_transcript_pair] only target ({target_lang}), translating native")
        target_segments = target_transcript.fetch()
        native_segments, _ = fetch_transcript_for_lang(transcript_list, native_lang)
        return native_segments, target_segments

    log("[fetch_transcript_pair] neither lang found, translating both from source")
    source = best_source_transcript(transcript_list)
    if source is None:
        log_error("[fetch_transcript_pair] no transcript source available")
        raise ValueError("No transcript source available")

    raw_segments = source.fetch()
    with ThreadPoolExecutor(max_workers=2) as executor:
        native_future = executor.submit(
            google_translate_segments, raw_segments, native_lang
        )
        target_future = executor.submit(
            google_translate_segments, raw_segments, target_lang
        )
        return native_future.result(), target_future.result()


def google_translate_segments(segments, target_lang: str, chunk_size: int = 4000):
    log(f"[google_translate_segments] target={target_lang}, {len(segments)} segments")
    translator = GoogleTranslator(source="auto", target=target_lang)

    SEP = " |||827548543255||| "

    chunks = []
    current = []
    size = 0

    for seg in segments:
        text = seg.text.replace("\n", " ").strip()
        needed = len(text) + len(SEP)

        if size + needed > chunk_size and current:
            chunks.append(current)
            current = []
            size = 0

        current.append(seg)
        size += needed

    if current:
        chunks.append(current)

    if not chunks:
        return []

    if len(chunks) == 1:
        return _translate_chunk(translator, chunks[0], SEP)

    log(f"[google_translate_segments] translating {len(chunks)} chunks in parallel")
    with ThreadPoolExecutor(max_workers=min(len(chunks), 4)) as executor:
        translated_chunks = list(
            executor.map(
                lambda chunk: _translate_chunk(translator, chunk, SEP),
                chunks,
            )
        )

    result = []
    for translated_chunk in translated_chunks:
        result.extend(translated_chunk)
    log(f"[google_translate_segments] done, {len(result)} segments")
    return result


def _translate_chunk(translator, chunk, sep: str):
    combined = sep.join(s.text for s in chunk)

    try:
        translated = translator.translate(combined)
    except Exception as exc:
        log_error(f"[_translate_chunk] translation failed, using original text", exc)
        translated = combined

    parts = translated.split(sep)
    return [
        make_segment(
            text=parts[i] if i < len(parts) else seg.text,
            start=seg.start,
            duration=seg.duration,
        )
        for i, seg in enumerate(chunk)
    ]
