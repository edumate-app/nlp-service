from fastapi import APIRouter,HTTPException,BackgroundTasks
from app.models.request_models import TranslateRequest,AnalyzeRequest
from app.services.transcript_service import get_transcript_service
import stanza
import string

from yt_dlp import YoutubeDL

from app.core.ytdlp_transcript import YouTubeTranscriptApi
from app.utils.log_utils import log, log_error



router = APIRouter()
install_status = {}
def install_language(lang: str):

    if install_status.get(lang) == "ready":
        return

    if install_status.get(lang) == "installing":
        return

    install_status[lang] = "installing"

    try:
        stanza.download(lang)

        if lang not in pipelines:
            pipelines[lang] = stanza.Pipeline(lang)

        install_status[lang] = "ready"

    except Exception:
        install_status[lang] = "failed"
        raise

@router.get("/install/status/{lang}")
def install_status_endpoint(lang: str):
    return {
        "language":lang,
        "status":install_status.get(lang,"not_installed")
    }

@router.get("/info/{video_id}")
def get_video_info(video_id: str,backgroundtasks : BackgroundTasks):
    log(f"[GET /info/{video_id}] start")
    url = f"https://www.youtube.com/watch?v={video_id}"

    ydl_opts = {
        "quiet": True,
        "skip_download": True,
    }

    with YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=False)
    
    
    language = info.get("language")
    if install_status.get(language) != "ready":
        backgroundtasks.add_task(install_language,language)

    backgroundtasks.add_task(install_language,language)
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

pipelines = {}

@router.post("/install/{lang}")
def install_lang(lang : str):
    install_language(lang)
    

@router.post("/analyze")
def analyze(request : AnalyzeRequest):
    
    if request.lang not in pipelines:
        raise HTTPException(status_code=404)
    text = request.text.translate(
        str.maketrans("", "", string.punctuation)
    )
    doc = pipelines[request.lang](text)
    tokens = []
    
    for sentence in doc.sentences:
        for word in sentence.words:
            features = {}
            if word.feats:
                for feature in word.feats.split("|"):
                    key,value = feature.split("=")
                    features[key] = value
            token = {
                "text": word.text,
                "lemma": word.lemma,
                "pos": word.upos
            }
            if word.upos in ["VERB","AUX"]:
                token["person"] = features.get("Person")
                token["number"] = features.get("Number")
                token["tense"] = features.get("Tense")
                token["mood"] = features.get("Mood")
                token["gender"] = features.get("Gender")

            tokens.append(token)
    return tokens

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
