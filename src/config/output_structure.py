from typing import List, Optional, Union, Literal
from pydantic import BaseModel, Field, HttpUrl, field_validator, RootModel

class Reason_Structure(BaseModel):

    reason: str = Field(
        ...,
        description=(
            "A concise and clear one sentence reason of why choosing this handoff"
        )
    )


# Allowed classification tags (overlapping, multi-select)
ClassificationTag = Literal[
    "product",                 # Product-level safety/performance/testing standards (UL, ASTM F963)
    "environment",             # Chemical or environmental requirements / eco labels (RoHS, REACH, Energy Star)
    "social_responsibility",   # Labor/CSR/ethical sourcing schemes (BSCI, SA8000)
    "label_package",           # Labeling/marking/packaging content & format rules (WEEE symbol, CLP labels)
    "market_access",           # Legal conformity marks/approvals for market entry (CE, FCC, CCC, UKCA)
    "other"                    # Everything else (e.g., ISO 9001 quality mgmt) for now
]

class Flashcard_Structure(BaseModel):
    # Human-friendly display name (include acronym in parentheses yourself if helpful, e.g. "CE Marking (CE)")
    name: str
    # Organization that issues or governs the certification (e.g., 'European Commission')
    issuing_body: str
    # Geographic scope where it applies (string or list; e.g. 'EU/EEA' or 'US' or 'Canada')
    region: str
    # 1–2 sentence plain-language explanation of what the certification proves/ensures
    description: str = Field(...,max_length=400,)
    # Overlapping tags from the allowed set above (1–3 recommended); aids filtering
    classifications: List[ClassificationTag] = Field(...,min_items=1,max_items=5,)
    # Context-level flag: required for the user's scenario/market? (computed at answer time)
    mandatory: bool
    # Typical validity/renewal info in free text (e.g., '3 years', 'No fixed expiry')
    validity: Optional[str]
    # One authoritative source URL (official site/regulation owner)
    official_link: str
    # Ensure no duplicate tags
    @field_validator("classifications", mode="before")
    def deduplicate_tags(cls, v: List[ClassificationTag]) -> List[ClassificationTag]:
        # Normalize to list
        if isinstance(v, str):
            v = [v]
        # Keep first occurrence order, drop extras
        seen = []
        for tag in v:
            if tag not in seen:
                seen.append(tag)
        return seen  # no exceptions

class Flashcards_Structure(BaseModel):
    """Wrapper model for certifications"""
    certifications: List[Flashcard_Structure]


class Answer_Structure(BaseModel):
    """Wrapper model for answers"""
    answer: str
    flashcards: List[Flashcard_Structure]

class List_Structure(BaseModel):
    """Wrapper model for List"""
    flashcards: List[Flashcard_Structure]
    answer: str
