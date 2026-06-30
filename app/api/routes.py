from fastapi import APIRouter
from app.models.request_models import TranslateRequest
from app.services.transcript_service import get_transcript_service
from youtube_transcript_api import YouTubeTranscriptApi

router = APIRouter()


@router.get("/lang/{video_id}")
def get_available_langs(video_id: str):
    print("lang endpoint")
    api = YouTubeTranscriptApi()
    transcript_list = api.list(video_id)

    result = {}

    for t in transcript_list:
        result[t.language_code] = {
            "language": t.language,
            "language_code": t.language_code,
        }

    return list(result.values())


@router.post("/transcript/{video_id}")
def get_transcript(video_id: str, request: TranslateRequest):
    print("transcript endpoint")
    return get_transcript_service(video_id, request)
