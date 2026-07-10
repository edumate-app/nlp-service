from fastapi import APIRouter
from yt_dlp import YoutubeDL

from app.models.request_models import TranslateRequest
from app.services.transcript_service import get_transcript_service
from app.core.ytdlp_transcript import YouTubeTranscriptApi
from app.utils.log_utils import log, log_error
from math import gcd

router = APIRouter()

@router.get("/info/{video_id}")
def get_video_info(video_id: str):
    log(f"[GET /info/{video_id}] start")
    url = f"https://www.youtube.com/watch?v={video_id}"

    ydl_opts = {
        "quiet": True,
        "skip_download": True,
    }

    with YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=False)

    return {
        # "id": info.get("id"),
        "title": info.get("title"),
        "author": info.get("uploader"),
        # "channel": info.get("channel"),
        # "channel_id": info.get("channel_id"),
        "duration": info.get("duration"),
        # "thumbnail": info.get("thumbnail"),
        # "upload_date": info.get("upload_date"),   
        # "description": info.get("description"),
        # "language": info.get("language"),
    }


@router.get("/lang/{video_id}")
def get_available_langs(video_id: str):
    log(f"[GET /lang/{video_id}] start")
    try:
        api = YouTubeTranscriptApi()
        transcript_list = api.list(video_id)

        result = {}

        for t in transcript_list:
            result[t.language_code] = {
                "language": t.language,
                "language_code": t.language_code,
            }

        langs = list(result.values())
        log(f"[GET /lang/{video_id}] ok, {len(langs)} languages")
        return langs
    except Exception as exc:
        log_error(f"[GET /lang/{video_id}] failed", exc)
        raise


@router.post("/transcript/{video_id}")
def get_transcript(video_id: str, request: TranslateRequest):
    log(
        f"[POST /transcript/{video_id}] start "
        f"(native={request.native_lang}, target={request.target_lang})"
    )
    try:
        result = get_transcript_service(video_id, request)
        log(f"[POST /transcript/{video_id}] ok, {len(result)} segments")
        return result
    except Exception as exc:
        log_error(f"[POST /transcript/{video_id}] failed", exc)
        raise

@router.get("/health")
def health():
    log("[GET /health] ok")
    return {"status": "ok"}
