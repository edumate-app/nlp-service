from pydantic import BaseModel


class TranslateRequest(BaseModel):
    target_lang: str
    native_lang: str
class AnalyzeRequest(BaseModel):
    text : str
    lang: str