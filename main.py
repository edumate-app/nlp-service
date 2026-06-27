from fastapi import FastAPI
import uvicorn
from youtube_transcript_api import YouTubeTranscriptApi
from youtube_transcript_api._errors import VideoUnavailable, TranscriptsDisabled

app = FastAPI()


@app.get("/health")
def health():
    return {"status": "test"}


@app.get("/lang/{video_id}")
def getAvailableLangs(video_id: str):
    try:
        ytt_api = YouTubeTranscriptApi()
        transcript_list = ytt_api.list(video_id)

        def clean_language(name: str) -> str:
            return name
            # return name.split("(")[0].strip()

        result = {}

        for t in transcript_list:
            language_code = t.language_code
            if language_code not in result:
                result[language_code] = {
                    "language": clean_language(t.language),
                    "language_code": language_code,
                }

        return list(result.values())
    except VideoUnavailable:
        return []
    except TranscriptsDisabled:
        return []


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
