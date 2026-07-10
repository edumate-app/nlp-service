from app.core.ytdlp_transcript import (
    YouTubeTranscriptApi,
    VideoUnavailable,
    TranscriptsDisabled,
)

from app.services.translation_service import fetch_transcript_pair
from app.utils.log_utils import log, log_error


def get_transcript_service(video_id: str, request):
    log(
        f"[get_transcript_service] video_id={video_id}, "
        f"native={request.native_lang}, target={request.target_lang}"
    )
    try:
        api = YouTubeTranscriptApi()
        transcript_list = api.list(video_id)

        native_segments, target_segments = fetch_transcript_pair(
            transcript_list, request.native_lang, request.target_lang
        )

        result = [
            {
                "nativeText": n.text,
                "targetText": t.text,
                "start": n.start,
                "duration": n.duration,
            }
            for n, t in zip(native_segments, target_segments)
        ]
        log(f"[get_transcript_service] ok, {len(result)} segments")
        return result

    except VideoUnavailable as exc:
        log_error(f"[get_transcript_service] video unavailable: {video_id}", exc)
        return []
    except TranscriptsDisabled as exc:
        log_error(f"[get_transcript_service] transcripts disabled: {video_id}", exc)
        return []
    except Exception as exc:
        log_error(f"[get_transcript_service] unexpected error: {video_id}", exc)
        raise
