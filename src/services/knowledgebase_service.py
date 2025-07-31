"""
Knowledge base service functions - Final implementation
"""
import json
import os
import time
from datetime import datetime, timezone

import openai
import voyageai
from dotenv import load_dotenv
import weaviate
from weaviate import WeaviateClient
from weaviate.auth import AuthApiKey
from weaviate.classes import query as wq
from weaviate.connect import ConnectionParams, ProtocolParams
from pydantic import BaseModel
from typing import List, Dict
from src.config.schemas import ComplianceArtifact

def _get_weaviate_client():
    """Get connected Weaviate client using environment configuration.
    
    Returns:
        WeaviateClient: Connected Weaviate client instance
        
    Raises:
        ValueError: If required environment variables are missing
    """
    weaviate_api_key = os.getenv("WEAVIATE_API_KEY")
    endpoint = os.getenv("WEAVIATE_URL")
    
    if not weaviate_api_key or not endpoint:
        raise ValueError("Missing WEAVIATE_API_KEY or WEAVIATE_URL environment variables")
    
    client = WeaviateClient(
        connection_params=ConnectionParams(
            http=ProtocolParams(host=endpoint, port=8080, secure=False),
            grpc=ProtocolParams(host=endpoint, port=50051, secure=False)
        ),
        auth_client_secret=AuthApiKey(weaviate_api_key),
    )
    client.connect()
    return client

async def kb_domain_lookup(query: str):
    OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

    # Initialize OpenAI
    openai.api_key = OPENAI_API_KEY

    # VoyageAI API key and client
    VOYAGE_API_KEY = os.getenv("VOYAGE_API_KEY")
    voyage_client = voyageai.Client(VOYAGE_API_KEY)

    # ─── 2.  Controlled vocab lists (for the prompt & validation) ─────────────
    ORG_TYPES = [
        "government",
        "standards_org",
        "accreditation_body",
        "certification_body",
        "inspection_body",
        "testing_lab",
        "consulting_firm",
    ]
    LEVELS = ["international", "supranational", "national", "subnational", "local"]
    COMPLIANCE = [
        "toy_safety",
        "electrical_electronics",
        "chemical_substances",
        "food_agriculture",
        "medical_healthcare",
        "automotive_transport",
        "industrial_machinery",
        "construction_building",
        "environmental",
        "occupational_safety",
        "information_security",
        "energy_utilities",
        "textiles_apparel",
        "aerospace_defense",
        "consumer_products",
    ]

    # ─── 3.  Prompt & JSON schema for GPT-4o-mini ─────────────────────────────
    PLAN_PROMPT = f"""
    You are a Weaviate query planner for trade‑compliance search.

    Guidelines
    * Extract every relevant token for **each** facet; leave an array empty if nothing is clearly implied.
    * Allowed vocabularies:
        org_type = {ORG_TYPES}
        level    = {LEVELS}
        compliance_domain = {COMPLIANCE}
    * Do **not** invent new tokens or fields.
    * Keep JSON minified: no trailing commas, no extra keys, no additional whitespace outside strings.
    Guidelines:
    * org_type: list **every** organization type implied (e.g., certification_body, inspection_body).
    * jurisdiction: include **each** ISO-3166-1 α-2 code for origin and destination; use GLOBAL for worldwide scope.
    * If any EU member state is included, also include "EU" in the jurisdiction array.
    * level: include each governance level implied (international, national, local, etc.).
    * compliance_domain: include **all** compliance domain referenced or implied (e.g., food_agriculture, chemical_substances).
    * Build vector_query by stripping filler words and focusing on core concepts (e.g., 'export honey certifications India US').
    * Only use allowed tokens; do not invent new ones.
    * Do NOT add any fields beyond the three specified.
    * Ensure the JSON is strictly formatted with no extra whitespace or properties.

    Example
    User: "certifications to export honey from India to US"
    Return:
    {{
    "keywords": {{
        "jurisdiction": ["IN","US"],
        "org_type": ["certification_body", "government", "standards_org"],
        "level": ["international", "national"],
        "compliance_domain": ["food_agriculture"]
    }}
    }}
    """

    SCHEMA = {
        "type": "object",
        "properties": {
            "keywords": {
                "type": "object",
                "properties": {
                    "jurisdiction": {"type": "array", "items": {"type": "string"}},
                    "org_type": {"type": "array", "items": {"type": "string"}},
                    "level": {"type": "array", "items": {"type": "string"}},
                    "compliance_domain": {"type": "array", "items": {"type": "string"}},
                },
                "required": [],
            },
        },
        "required": ["vector_query", "keywords"],
        "additionalProperties": False,
    }

    class Plan(BaseModel):
        keywords: Dict[str, List[str]]

    def _plan(query: str) -> Plan:
        """Call GPT‑4o to get structured plan."""
        resp = openai.chat.completions.create(
            model="gpt-4o",
            temperature=0,
            response_format={
                "type": "json_schema",
                "json_schema": {"name": "plan", "schema": SCHEMA},
            },
            messages=[
                {"role": "system", "content": PLAN_PROMPT},
                {"role": "user", "content": query},
            ],
        )
        return Plan.model_validate_json(resp.choices[0].message.content)

    plan = _plan(query)
    property_keywords = {k: v for k, v in plan.keywords.items() if v}

    # Weaviate client
    client = _get_weaviate_client()

    whitelist = client.collections.get("URL_Whitelist")

    # Build BM25 query: natural‑language sentence + facet keywords
    bm25_query = f"{query} " + " ".join(sum(property_keywords.values(), []))
    # bm25_props = list(property_keywords.keys())
    # print(bm25_props)
    response = whitelist.query.hybrid(
        query=bm25_query,
        # vector=vector_embed,
        alpha=0.5,
        limit=5,
        # query_properties=bm25_props,
        return_properties=["domain"],
        return_metadata=wq.MetadataQuery(score=True),
    )

    # Collect domains
    domain_list = [obj.properties["domain"] for obj in response.objects]
    client.close()
    return domain_list

async def kb_compliance_lookup(query: str):
    # VoyageAI API key and client
    VOYAGE_API_KEY = os.getenv("VOYAGE_API_KEY")
    voyage_client = voyageai.Client(VOYAGE_API_KEY)

    client = _get_weaviate_client()
    print("🍎 Connected to Weaviate")
    whitelist = client.collections.get("Compliance_Artifacts")

    #TODO: create an openai call to polish the search query
    # Build BM25 query: natural‑language sentence + facet keywords
    # bm25_query = f"{query} " + " ".join(sum(property_keywords.values(), []))
    bm25_query = query
    # bm25_props = list(property_keywords.keys())

    response = whitelist.query.hybrid(
        query=bm25_query,
        # vector=vector_embed,
        alpha=0.5,
        limit=5,
        # query_properties=bm25_props,
        # return_properties=["domain"],
        return_metadata=wq.MetadataQuery(score=True),
    )
    # Print only the names from the response objects
    for obj in response.objects:
        if hasattr(obj, 'properties') and 'name' in obj.properties:
            print(f"Found: {obj.properties['name']}")

    client.close()
    return response

async def kb_compliance_save(artifact: ComplianceArtifact, uuid: str = None):
    """Save a compliance artifact to the Weaviate knowledge base.
    
    Args:
        artifact: ComplianceArtifact object with all required fields
        uuid: Optional UUID string. If provided, updates existing object; if None, creates new object
        
    Returns:
        str: UUID of the saved/updated object
        
    Raises:
        Exception: If save operation fails
    """
    # Initialize Weaviate client using extracted helper function
    client = _get_weaviate_client()
    
    try:
        # Get the compliance artifacts collection
        compliance_collection = client.collections.get("Compliance_Artifacts")
        
        # Convert ComplianceArtifact to dictionary for Weaviate
        properties = {
            "artifact_type": artifact.artifact_type,
            "name": artifact.name,
            "aliases": artifact.aliases or [],
            "issuing_body": artifact.issuing_body,
            "region": artifact.region,
            "mandatory": artifact.mandatory,
            "validity_period_months": artifact.validity_period_months,
            "overview": artifact.overview,
            "full_description": artifact.full_description,
            "legal_reference": artifact.legal_reference,
            "domain_tags": artifact.domain_tags,
            "scope_tags": artifact.scope_tags or [],
            "harmonized_standards": artifact.harmonized_standards or [],
            "fee": artifact.fee,
            "application_process": artifact.application_process,
            "official_link": str(artifact.official_link),
            "updated_at": datetime.now(timezone.utc).isoformat(),
            "sources": [str(source) for source in artifact.sources]
        }
        
        if uuid:
            # Update existing object
            compliance_collection.data.update(
                uuid=uuid,
                properties=properties
            )
            result_uuid = uuid
        else:
            # Create new object - let Weaviate generate UUID or use deterministic UUID
            from weaviate.util import generate_uuid5
            
            # Generate deterministic UUID based on name and issuing_body for deduplication
            uuid_data = f"{artifact.name}_{artifact.issuing_body}"
            generated_uuid = generate_uuid5(uuid_data)
            
            result_uuid = compliance_collection.data.insert(
                properties=properties,
                uuid=generated_uuid
            )
            
    except Exception as e:
        raise Exception(f"Failed to save compliance artifact: {str(e)}")
    finally:
        client.close()
    
    return result_uuid