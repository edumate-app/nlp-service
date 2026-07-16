from fastapi import APIRouter,HTTPException,BackgroundTasks
from app.models.request_models import TranslateRequest,AnalyzeRequest
from app.services.transcript_service import get_transcript_service
import stanza
import string

from yt_dlp import YoutubeDL

import os
from app.core.ytdlp_transcript import YouTubeTranscriptApi
from app.utils.log_utils import log, log_error
from pathlib import Path

router = APIRouter()

# Set the path for Stanza models
STANZA_RESOURCES_DIR = os.getenv("STANZA_RESOURCES_DIR", "/app/stanza_data")
os.makedirs(STANZA_RESOURCES_DIR, exist_ok=True)

# IMPORTANT: Set the path before any Stanza usage
os.environ["STANZA_RESOURCES_DIR"] = STANZA_RESOURCES_DIR

# Or use the download method with the parameter
# stanza.download(lang, resources_dir=STANZA_RESOURCES_DIR)

# Global dictionaries
install_status = {}
pipelines = {}
_models_loaded = False

def load_existing_models():
    global pipelines, install_status

    if _models_loaded:
        return
    
    resources_path = Path(STANZA_RESOURCES_DIR)
    print(resources_path)
    if not resources_path.exists():
        print(f"📁 Model directory does not exist: {STANZA_RESOURCES_DIR}")
        resources_path.mkdir(parents=True, exist_ok=True)
        return
    
    print(f"🔍 Looking for models in: {resources_path}")
    
    found_models = []
    loaded_models = []
    failed_models = []
    
    try:
        for item in resources_path.iterdir():
            print(f"Checking: {item}")
            if item.is_dir():
                lang = item.name
                found_models.append(lang)
                
                if any(item.iterdir()):
                    try:
                        pipelines[lang] = stanza.Pipeline(
                            lang, 
                            model_dir=STANZA_RESOURCES_DIR,
                            verbose=False
                        )
                        loaded_models.append(lang)
                        install_status[lang] = "ready"
                    except Exception as e:
                        failed_models.append(lang)
                        install_status[lang] = "failed"

                    
    except Exception as e:
        print(f"⚠️ Directory read error: {e}")
    
    if found_models:
        print(f"📦 Znalezione modele: {', '.join(found_models)}")
        if loaded_models:
            print(f"✅ Załadowane do pamięci: {', '.join(loaded_models)}")
        if failed_models:
            print(f"❌ Nie udało się załadować: {', '.join(failed_models)}")
    else:
        print("⚠️ Brak zainstalowanych modeli")

load_existing_models()

def install_language(lang: str):

    if install_status.get(lang) == "ready":
        return

    if install_status.get(lang) == "installing":
        print(f"⏳ Installation of {lang} already in progress")
        return

    install_status[lang] = "installing"
    print(f"📥 Starting installation of {lang}")

    try:
        stanza.download(
            lang,
            model_dir=STANZA_RESOURCES_DIR,
            verbose=False
        )

        pipelines[lang] = stanza.Pipeline(
            lang,
            model_dir=STANZA_RESOURCES_DIR,
            verbose=False
        )
        install_status[lang] = "ready"
        print(f"✅ Installed and loaded {lang}")

    except Exception:
        install_status[lang] = "failed"
        raise


@router.get("/install/status/{lang}")
def install_status_endpoint(lang: str):
    return {
        "language": lang,
        "status": install_status.get(lang, "not_installed"),
        "in_memory": lang in pipelines
    }

@router.get("/models/status")
def models_status():
    resources_path = Path(STANZA_RESOURCES_DIR)
    
    disk_models = []
    if resources_path.exists():
        try:
            for item in resources_path.iterdir():
                if item.is_dir() and any(item.iterdir()):
                    disk_models.append(item.name)
        except Exception as e:
            print(f"⚠️ Błąd odczytu: {e}")
    
    return {
        "loaded_in_memory": list(pipelines.keys()),
        "installed_on_disk": disk_models,
        "status": install_status,
        "models_dir": STANZA_RESOURCES_DIR,
        "models_dir_exists": resources_path.exists()
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
