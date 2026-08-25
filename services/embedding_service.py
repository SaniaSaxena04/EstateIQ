import os
import google.generativeai as genai

class EmbeddingService:
    def __init__(self):
        api_key = os.getenv("GEMINI_API_KEY")
        if api_key:
            genai.configure(api_key=api_key)

    def get_embedding(self, text: str):
        """Generate vector embeddings using Google Gemini API."""
        try:
            response = genai.embed_content(
                model="models/text-embedding-004",
                content=text,
                task_type="retrieval_document"
            )
            return response["embedding"]
        except Exception as e:
            print(f"[Embedding Service Error]: {e}")
            # Return zero vector fallback if API call fails
            return [0.0] * 768

embedding_service = EmbeddingService()