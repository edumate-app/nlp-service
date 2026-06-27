from youtube_transcript_api import YouTubeTranscriptApi
from youtube_transcript_api._errors import VideoUnavailable, TranscriptsDisabled

from app.services.translation_service import fetch_transcript_for_lang


def get_transcript_service(video_id: str, request):
    try:
        api = YouTubeTranscriptApi()
        transcript_list = api.list(video_id)

        native_segments, _ = fetch_transcript_for_lang(
            transcript_list, request.native_lang
        )

        target_segments, _ = fetch_transcript_for_lang(
            transcript_list, request.target_lang
        )

        return [
            {
                "nativeText": n.text,
                "targetText": t.text,
                "start": n.start,
                "duration": n.duration,
            }
            for n, t in zip(native_segments, target_segments)
        ]

    except (VideoUnavailable, TranscriptsDisabled):
        return []
