from concurrent.futures import ThreadPoolExecutor

from deep_translator import GoogleTranslator

from app.utils.segment_utils import make_segment
from app.core.youtube import best_source_transcript


def _find_transcript(transcript_list, lang_code: str):
    try:
        return transcript_list.find_transcript([lang_code])
    except Exception:
        return None


def fetch_transcript_for_lang(transcript_list, lang_code: str):

    try:
        t = transcript_list.find_transcript([lang_code])
        return t.fetch(), "native"
    except Exception:
        pass

    source = best_source_transcript(transcript_list)
    if source is None:
        raise ValueError(f"No transcript source available for {lang_code}")

    raw_segments = source.fetch()
    translated_segments = google_translate_segments(raw_segments, lang_code)

    return translated_segments, "gt_trans"


def fetch_transcript_pair(transcript_list, native_lang: str, target_lang: str):
    transcript_list.prefetch_for_langs(native_lang, target_lang)

    native_transcript = _find_transcript(transcript_list, native_lang)
    target_transcript = _find_transcript(transcript_list, target_lang)

    if native_transcript and target_transcript:
        with ThreadPoolExecutor(max_workers=2) as executor:
            native_future = executor.submit(native_transcript.fetch)
            target_future = executor.submit(target_transcript.fetch)
            return native_future.result(), target_future.result()

    if native_transcript and not target_transcript:
        native_segments = native_transcript.fetch()
        target_segments, _ = fetch_transcript_for_lang(transcript_list, target_lang)
        return native_segments, target_segments

    if target_transcript and not native_transcript:
        target_segments = target_transcript.fetch()
        native_segments, _ = fetch_transcript_for_lang(transcript_list, native_lang)
        return native_segments, target_segments

    source = best_source_transcript(transcript_list)
    if source is None:
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
    return result


def _translate_chunk(translator, chunk, sep: str):
    combined = sep.join(s.text for s in chunk)

    try:
        translated = translator.translate(combined)
    except Exception:
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
