import os
import json
import google.generativeai as genai
from services.vector_service import vector_service
from services.property_matching import calculate_match_score

class AIAgent:
    def __init__(self):
        api_key = os.getenv("GEMINI_API_KEY")
        if api_key:
            genai.configure(api_key=api_key)
            self.model = genai.GenerativeModel("gemini-2.5-flash")
        else:
            self.model = None

    def process_chat(self, user_message: str) -> str:
        if not self.model:
            return "Gemini API key is unconfigured. Please set GEMINI_API_KEY in .env."

        # Search candidates using semantic service
        candidates = vector_service.search_properties(query=user_message, limit=3)
        
        context_str = json.dumps(candidates, indent=2)
        prompt = f"""
You are EstateIQ AI, a professional real-estate match and price intelligence assistant.
Answer the user query based ONLY on the retrieved context below. Do NOT fabricate properties.

User Request: "{user_message}"

Retrieved Properties Context:
{context_str}

Provide a helpful, concise summary highlighting top matches, price points, and property features.
        """
        try:
            response = self.model.generate_content(prompt)
            return response.text
        except Exception as e:
            return f"AI Agent processing error: {str(e)}"

ai_agent = AIAgent()