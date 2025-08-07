from typing import List, Optional, Union, Literal
from pydantic import BaseModel, Field
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
        description="Official, most formal title of the scheme"
    )
    issuing_body: str = Field(
        ...,
        description="Organization that issues or governs the certification (e.g., 'European Commission')"
    )
    region: str = Field(
        ...,
        description="Geographic scope where it applies (e.g. 'EU/EEA' or 'US' or 'Canada')"
    )
    description: str = Field(
        ...,
        max_length=400,
        description="1–2 sentence plain-language explanation of what the certification proves/ensures"
    )
    mandatory: bool = Field(
        ...,
        description="Context-level flag: required for the user's scenario/market? (computed at answer time)"
    )
    validity: Optional[str] = Field(
        None,
        description="Typical validity/renewal info in free text (e.g., '3 years', 'No fixed expiry')"
    )
    lead_time_days: Optional[int] = Field(
        None,
        description="Calendar days needed BEFORE submission (document prep, lab tests, audit booking). Null if unknown."
    )
    processing_time_days: Optional[int] = Field(
        None,
        description="Calendar days the authority takes AFTER submission to issue the certificate. Null if unknown."
    )
    prerequisites: Optional[List[str]] = Field(
        None,
        description="Other certifications/registrations that must be obtained first; empty list or null if none."
    )
    audit_scope: Optional[List[str]] = Field(
        None,
        description='High-level audit types required (e.g. ["factory_QMS", "social_compliance"]).'
    )
    test_items: Optional[List[str]] = Field(
        None,
        description='Key lab-test standards or measurements (e.g. ["EN 71-1", "EN 71-3"]).'
    )
    official_link: str = Field(
        ...,
        description="One authoritative source URL (official site/regulation owner)"
    )

class Flashcards_Structure(BaseModel):
    """Wrapper model for certifications"""
    certifications: List[Flashcard_Structure]

class ComplianceList_Structure(BaseModel):
    """Wrapper model for compliance discovery results"""
    response: List[str] = Field(
        ...,
        description="List of compliance/certification names"
    )


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
    
    lead_time_days: Optional[int] = Field(
        None,
        description="Calendar days needed BEFORE submission (document prep, lab tests, audit booking). Null if unknown."
    )
    processing_time_days: Optional[int] = Field(
        None,
        description="Calendar days the authority takes AFTER submission to issue the certificate. Null if unknown."
    )
    prerequisites: Optional[List[str]] = Field(
        None,
        description="Other certifications/registrations that must be obtained first; empty list or null if none."
    )
    audit_scope: Optional[List[str]] = Field(
        None,
        description='High-level factory audit types required (e.g. ["factory_QMS", "social_compliance"]).'
    )
    test_items: Optional[List[str]] = Field(
        None,
        description=' List *standard references* or grouped analyte tests,  e.g. ["IEC 62321-5", "IEC 62321-7-2"] or ["heavy_metals_screen"] –  not full limit tables.'
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
