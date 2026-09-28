from typing import Literal
from pydantic import BaseModel, Field
from app.schemas.language import LanguagePreference

class ProductInput(BaseModel):
    category: str
    sub_category: str | None = None
    description: str
    materials: list[str] | None = None
    intended_use: str | None = None
    is_imported: bool = False
    manufacturer_scale: Literal["msme", "large", "unknown"] = "unknown"
    lang: LanguagePreference = Field(default_factory=LanguagePreference)
