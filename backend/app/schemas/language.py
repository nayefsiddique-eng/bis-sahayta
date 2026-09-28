from pydantic import BaseModel, Field

class LanguagePreference(BaseModel):
    lang_code: str = Field(default="en", description="ISO 639-1 / Bhashini language code (e.g. en, hi, ta, te, bn, mr, gu, kn, ml, pa)")

class SupportedLanguage(BaseModel):
    code: str
    name: str
    native_name: str

class LanguageSupportResponse(BaseModel):
    languages: list[SupportedLanguage]

class TranslateTextRequest(BaseModel):
    text: str
    source_lang: str = "auto"
    target_lang: str = "en"

class TranslateTextResponse(BaseModel):
    translated_text: str
    source_lang: str
    target_lang: str
    translation_unavailable: bool = False
