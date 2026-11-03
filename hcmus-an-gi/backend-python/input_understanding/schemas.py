from typing import Optional, Literal
from pydantic import BaseModel, Field


class ExtractedIntent(BaseModel):
    intent: Literal[
        "search_food",
        "refine_search",
        "recommendation",
        "other"
    ] = "search_food"

    campus: Optional[Literal["q5", "lang"]] = None

    budget: Optional[int] = None

    radius_m: Optional[int] = None

    cuisine: Optional[str] = None

    keywords: list[str] = Field(default_factory=list)