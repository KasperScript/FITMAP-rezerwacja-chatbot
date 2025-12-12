from google import genai
from google.genai import types
from config import GEMINI_API_KEY, GEMINI_MODEL_NAME

client = genai.Client(api_key=GEMINI_API_KEY)

def call_gemini(system_prompt: str, contents: str) -> str:
    
    response = client.models.generate_content(
        model=GEMINI_MODEL_NAME,
        contents=contents,
        config=types.GenerateContentConfig(
            system_instruction=system_prompt,
            temperature=0.2,
            candidate_count=1,
            max_output_tokens=1024,
        ),
    )
    return response.text