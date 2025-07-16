import os
import openai

# Input validation: check for empty or too long input
def validate_input(text: str, max_length: int = 1099):
    """
    Validates user input for emptiness and length.
    """
    if not text or not text.strip():
        raise ValueError("Input is empty.")
    if len(text) > max_length:
        raise ValueError(f"Input exceeds maximum length of {max_length} characters.")
    return True

# Input moderation using OpenAI Moderation API
def input_moderation(text: str):
    """
    Uses OpenAI Moderation API to check user input for unsafe content.
    """
    openai.api_key = os.getenv("OPENAI_API_KEY")
    response = openai.moderations.create(input=text)
    results = response.results[0]
    if results.flagged:
        raise ValueError(f"Input flagged as unsafe: {results.categories}")
    return True

# Output moderation using OpenAI Moderation API
def output_moderation(text: str):
    """
    Uses OpenAI Moderation API to check output for unsafe content.
    """
    openai.api_key = os.getenv("OPENAI_API_KEY")
    response = openai.moderations.create(input=text)
    results = response.results[0]
    if results.flagged:
        raise ValueError(f"Output flagged as unsafe: {results.categories}")
    return True 