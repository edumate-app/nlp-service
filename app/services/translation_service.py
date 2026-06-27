from deep_translator import GoogleTranslator
import time

from app.utils.segment_utils import make_segment
from app.core.youtube import best_source_transcript


def fetch_transcript_for_lang(transcript_list, lang_code: str):

    try:
        t = transcript_list.find_transcript([lang_code])
        return t.fetch(), "native"
    except Exception:
        pass

    for candidate in list(transcript_list):
        try:
            translated = candidate.translate(lang_code)
            return translated.fetch(), "yt_trans"
        except Exception:
            continue

    source = best_source_transcript(transcript_list)

    raw_segments = source.fetch()
    translated_segments = google_translate_segments(raw_segments, lang_code)

    return translated_segments, "gt_trans"


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

    result = []

    for chunk in chunks:
        combined = SEP.join(s.text for s in chunk)

        try:
            translated = translator.translate(combined)
            time.sleep(0.15)
        except Exception:
            translated = combined

        parts = translated.split(SEP)

        for i, seg in enumerate(chunk):
            result.append(
                make_segment(
                    text=parts[i] if i < len(parts) else seg.text,
                    start=seg.start,
                    duration=seg.duration,
                )
            )

    return result
