from typing import List, Optional, Union, Literal
from pydantic import BaseModel, Field, field_validator, RootModel
from datetime import datetime

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
    name: str = Field(
        ...,
        description="Human-friendly display name (include acronym in parentheses yourself if helpful, e.g. 'CE Marking (CE)')"
    )
    issuing_body: str = Field(
        ...,
        description="Organization that issues or governs the certification (e.g., 'European Commission')"
    )
    region: str = Field(
        ...,
        description="Geographic scope where it applies (string or list; e.g. 'EU/EEA' or 'US' or 'Canada')"
    )
    description: str = Field(
        ...,
        max_length=400,
        description="1–2 sentence plain-language explanation of what the certification proves/ensures"
    )
    classifications: List[ClassificationTag] = Field(
        ...,
        min_length=1, max_length=5,
        description="Overlapping tags from the allowed set above (1–3 recommended); aids filtering"
    )
    mandatory: bool = Field(
        ...,
        description="Context-level flag: required for the user's scenario/market? (computed at answer time)"
    )
    validity: Optional[str] = Field(
        None,
        description="Typical validity/renewal info in free text (e.g., '3 years', 'No fixed expiry')"
    )
    official_link: str = Field(
        ...,
        description="One authoritative source URL (official site/regulation owner)"
    )
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


# ComplianceArtifact model for formal compliance documentation and certification schemes
class ComplianceArtifact(BaseModel):
    artifact_type: Literal[
        "product_certification",
        "management_system_certification",
        "registration",
        "market_access_authorisation",
        "shipment_document",
    ] = Field(
        ...,
        description="One of: product_certification, management_system_certification, registration, market_access_authorisation, shipment_document."
    )

    name: str = Field(
        ...,
        description="Official, most formal title of the scheme (no abbreviations or parentheses)"
    )

    aliases: Optional[List[str]] = Field(
        None,
        description="0-5 common alternative names or acronyms (e.g. ['RoHS', 'RoHS 2'])"
    )

    issuing_body: str = Field(
        ...,
        description="Full proper name of the issuing organisation (e.g. 'European Commission')"
    )

    region: str = Field(
        ...,
        description="Geographic scope (EU/EEA, United States, Global, China Mainland, etc.)"
    )

    mandatory: bool = Field(
        ...,
        description="True if legally required in the region; false if voluntary"
    )

    validity_period_months: int = Field(
        ...,
        description="Renewal cycle in months (0 = no fixed expiry)"
    )

    overview: str = Field(
        ...,
        description="1–2 sentence summary of purpose and coverage (≤400 chars)"
    )

    full_description: str = Field(
        ...,
        description="80-150 word paragraph on purpose, scope, applicability, and use cases"
    )

    legal_reference: str = Field(
        ...,
        description="Official citation of the legal instrument or standard (e.g. 'Directive 2011/65/EU')"
    )

    domain_tags: List[Literal["product","safety","environment","csr","other"]]= Field(
        ...,
        description="Pick thematic tags: product, safety, environment, csr, other"
    )

    scope_tags: Optional[List[str]] = Field(
        None,
        description="0-10 snake_case tokens defining product families or industry sectors"
    )

    harmonized_standards: Optional[List[str]] = Field(
        None,
        description="List of EN/IEC/ISO numbers referenced by the scheme"
    )

    fee: Optional[str] = Field(
        None,
        description="Typical cost note including currency (e.g. '≈ €450 per model')"
    )

    application_process: Optional[str] = Field(
        None,
        description="Bullet steps or URL on how to obtain or renew (≤300 chars)"
    )

    official_link: str = Field(
        ...,
        description="Canonical HTTPS URL of the official scheme documentation (must be valid URL)"
    )

    updated_at: datetime = Field(
        ...,
        description="UTC timestamp when this record was last reviewed"
    )

    sources: List[str] = Field(
        ...,
        description="List of all source URLs or PDFs used to populate this record (first must be official_link, all must be valid URLs)"
    )
