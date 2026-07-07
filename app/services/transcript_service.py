from app.core.ytdlp_transcript import (
    YouTubeTranscriptApi,
    VideoUnavailable,
    TranscriptsDisabled,
)

from app.services.translation_service import fetch_transcript_pair


def get_transcript_service(video_id: str, request):
    try:
        api = YouTubeTranscriptApi()
        transcript_list = api.list(video_id)

        native_segments, target_segments = fetch_transcript_pair(
            transcript_list, request.native_lang, request.target_lang
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
