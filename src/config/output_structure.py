from pydantic import BaseModel, RootModel, Field
from typing import List, Dict, Any, Optional

class Reason_Structure(BaseModel):

    reason: str = Field(
        ...,
        description=(
            "A concise and clear one sentence reason of why choosing this handoff"
        )
    )
    
#TODO: add description?
class Certification_Structure(BaseModel):
    """Model for certification data"""
    certificate_name: str
    certificate_description: str
    legal_regulation: str
    legal_text_excerpt: str
    legal_text_meaning: str
    registration_fee: str
    is_required: bool

class Certifications_Structure(BaseModel):
    """Wrapper model for certifications"""
    certifications: List[Certification_Structure]