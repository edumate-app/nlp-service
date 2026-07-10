from fastapi import APIRouter,HTTPException
from app.models.request_models import TranslateRequest,AnalyzeRequest
from app.services.transcript_service import get_transcript_service
from app.core.ytdlp_transcript import YouTubeTranscriptApi
import stanza
import string
router = APIRouter()

#pobieranie tego pipeline dla danego jezyka
pipelines = {}

@router.post("/install/{lang}")
def install_lang(lang : str):
    
    try:
        stanza.download(lang)
        if lang not in pipelines:
            pipelines[lang] = stanza.Pipeline(lang)

    except Exception as e:
        
        raise HTTPException(
            status_code=500,
            detail=str(e))

@router.post("/analyze/")
def analyze(lang : str,request : AnalyzeRequest ):
    
    if lang not in pipelines:
        raise HTTPException(status_code=404)
    text = request.text.translate(
        str.maketrans("", "", string.punctuation)
    )
    doc = pipelines[lang](text)
    tokens = []
    
    for sentence in doc.sentences:
        for word in sentence.words:

            token = {
                "text": word.text,
                "infinitive": word.lemma,
                "pos": word.upos
            }

            if word.upos == "VERB":
                tense = None

                if word.feats:
                    for feature in word.feats.split("|"):
                        if feature.startswith("Tense="):
                            tense = feature.split("=")[1]

                token["tense"] = tense
            tokens.append(token)

    return {
        "lang": lang,
        "tokens": tokens
    }
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




@router.get("/health")
def health():
    return {"status": "ok"}
