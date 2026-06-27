from fastapi import FastAPI
from app.api.routes import router

app = FastAPI()

app.include_router(router)


@app.get("/health")
def health():
    return {"status": "ok"}


# from fastapi import FastAPI
# import uvicorn
# from youtube_transcript_api import YouTubeTranscriptApi
# from pydantic import BaseModel
# from youtube_transcript_api._errors import (
#     TranscriptsDisabled,
#     NoTranscriptFound,
#     VideoUnavailable,
#     TranslationLanguageNotAvailable,
# )
# from deep_translator import GoogleTranslator
# import time

# app = FastAPI()


# @app.get("/health")
# def health():
#     return {"status": "test"}


# @app.get("/lang/{video_id}")
# def getAvailableLangs(video_id: str):
#     try:
#         ytt_api = YouTubeTranscriptApi()
#         transcript_list = ytt_api.list(video_id)

#         def clean_language(name: str) -> str:
#             return name
#             # return name.split("(")[0].strip()

#         result = {}

#         for t in transcript_list:
#             language_code = t.language_code
#             if language_code not in result:
#                 result[language_code] = {
#                     "language": clean_language(t.language),
#                     "language_code": language_code,
#                 }

#         return list(result.values())
#     except VideoUnavailable:
#         return []
#     except TranscriptsDisabled:
#         return []


# class TranslateRequest(BaseModel):
#     target_lang: str
#     native_lang: str


# @app.post("/transcript/{video_id}")
# def get_transcript(video_id: str, request: TranslateRequest):
#     try:
#         ytt_api = YouTubeTranscriptApi()
#         transcript_list = ytt_api.list(video_id)
#         native_segments, _ = fetch_transcript_for_lang(
#             transcript_list, request.native_lang
#         )
#         target_segments, _ = fetch_transcript_for_lang(
#             transcript_list, request.target_lang
#         )

#         return [
#             {
#                 "nativeText": n.text,
#                 "targetText": t.text,
#                 "start": n.start,
#                 "duration": n.duration,
#             }
#             for n, t in zip(native_segments, target_segments)
#         ]

#     except VideoUnavailable:
#         return []
#     except TranscriptsDisabled:
#         return []


# def google_translate_segments(segments, target_lang: str, chunk_size: int = 4000):
#     """
#     Tłumaczy listę segmentów przez Google Translate (deep-translator).
#     Łączy teksty w chunki, tłumaczy, rozdziela z powrotem.
#     Zachowuje oryginalne znaczniki czasu.
#     """
#     translator = GoogleTranslator(source="auto", target=target_lang)

#     # Separator który nie wystąpi w zwykłym tekście
#     SEP = " |||SEP||| "

#     # Grupuj segmenty w chunki nie przekraczające chunk_size znaków
#     chunks = []  # lista list segmentów
#     current_chunk = []
#     current_len = 0

#     for seg in segments:
#         text = seg.text.replace("\n", " ").strip()
#         needed = len(text) + len(SEP)
#         if current_len + needed > chunk_size and current_chunk:
#             chunks.append(current_chunk)
#             current_chunk = []
#             current_len = 0
#         current_chunk.append(seg)
#         current_len += needed

#     if current_chunk:
#         chunks.append(current_chunk)

#     result_segments = []
#     for i, chunk in enumerate(chunks):
#         combined = SEP.join(s.text.replace("\n", " ").strip() for s in chunk)
#         try:
#             translated_combined = translator.translate(combined)
#             time.sleep(0.15)  # grzeczny rate limit
#         except Exception as e:
#             print(f"    ⚠️   Błąd tłumaczenia chunka {i+1}/{len(chunks)}: {e}")
#             translated_combined = combined  # fallback: bez tłumaczenia

#         parts = translated_combined.split("|||SEP|||")

#         # Dopasuj przetłumaczone części do oryginalnych segmentów
#         for j, seg in enumerate(chunk):
#             translated_text = parts[j].strip() if j < len(parts) else seg.text
#             # Tworzymy obiekt-like dict z tymi samymi polami co FetchedTranscriptSnippet
#             result_segments.append(
#                 _make_segment(
#                     text=translated_text,
#                     start=seg.start,
#                     duration=seg.duration,
#                 )
#             )

#         if len(chunks) > 1:
#             print(f"    🔄  Tłumaczenie chunk {i+1}/{len(chunks)}…", end="\r")

#     if len(chunks) > 1:
#         print()  # newline po \r

#     return result_segments


# class _make_segment:
#     """Prosty obiekt imitujący FetchedTranscriptSnippet."""

#     def __init__(self, text, start, duration):
#         self.text = text
#         self.start = start
#         self.duration = duration


# def fetch_transcript_for_lang(transcript_list, lang_code: str):
#     print(f"transcript_list: {transcript_list}")
#     print("lang code: ", lang_code)
#     """
#     Pobiera transkrypcję dla lang_code. Zwraca (segments_list, method_str).

#     Metody (w kolejności prób):
#       'native'    — oryginalna transkrypcja w tym języku
#       'yt_trans'  — przetłumaczona przez YouTube API
#       'gt_trans'  — przetłumaczona przez Google Translate
#     """

#     # ── Próba 1: natywna ──────────────────────────────────────────────────────
#     try:
#         t = transcript_list.find_transcript([lang_code])
#         return t.fetch(), "native"
#     except NoTranscriptFound:
#         pass

#     # ── Próba 2: YouTube Translation ──────────────────────────────────────────
#     # Próbujemy translate() na każdej dostępnej transkrypcji wprost,
#     # bez sprawdzania listy — niektóre filmy mają niepełną listę w API
#     all_transcripts = list(transcript_list)
#     for candidate in all_transcripts:
#         try:
#             translated = candidate.translate(lang_code)
#             segments = translated.fetch()
#             return segments, "yt_trans"
#         except (TranslationLanguageNotAvailable, Exception):
#             continue

#     source = best_source_transcript(transcript_list)
#     if source is None:
#         raise RuntimeError(f"Brak jakiejkolwiek transkrypcji do tłumaczenia.")

#     print(f"    ℹ️   YouTube nie obsługuje tłumaczenia → używam Google Translate")
#     print(f"    📖  Źródło: [{source.language_code}] {source.language}")

#     raw_segments = source.fetch()

#     # Tłumaczymy w paczkach (Google Translate ma limit ~5000 znaków)
#     translated_segments = google_translate_segments(raw_segments, lang_code)
#     return translated_segments, "gt_trans"


# def best_source_transcript(transcript_list):
#     """
#     Wybiera najlepszą transkrypcję źródłową do tłumaczenia:
#     preferuje ręczne angielskie, potem ręczne inne, potem auto-generated.
#     """
#     all_t = list(transcript_list)
#     # Priorytet: ręczna EN > ręczna inna > auto EN > auto inne
#     for preferred in [
#         lambda t: not t.is_generated and t.language_code == "en",
#         lambda t: not t.is_generated,
#         lambda t: t.language_code == "en",
#         lambda t: True,
#     ]:
#         candidates = [t for t in all_t if preferred(t)]
#         if candidates:
#             return candidates[0]
#     return None


# if __name__ == "__main__":
#     uvicorn.run(app, host="0.0.0.0", port=8000)
