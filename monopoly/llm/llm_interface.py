"""Gemini LLM interface with multi-turn chat support."""

from google import genai
from google.genai import types
from typing import Optional


class GeminiChat:
    """Gemini chat interface - one chat per game."""
    
    def __init__(self, api_key: str, model: str = "gemini-2.0-flash-exp"):
        """Create a new Gemini chat session."""
        self.client = genai.Client(api_key=api_key)
        self.chat = self.client.chats.create(
            model=model,
            config=types.GenerateContentConfig(
                system_instruction="""You play Monopoly. Respond with ONLY the action keyword - no explanations.
Buy decision: BUY or PASS
Improve decision: IMPROVE:<property_name> or NO_IMPROVEMENT
Keep responses under 20 tokens.""",
                thinking_config=types.ThinkingConfig(thinking_budget=0)
            ),
        )
    
    def send_message(self, message: str) -> str:
        """Send message to chat and return response."""
        try:
            response = self.chat.send_message(message)
            return response.text.strip()
        except Exception as e:
            print(f"Gemini API error: {e}")
            return "PASS"
    
    def get_history(self):
        """Get full chat history."""
        return self.chat.get_history()


class MockChat:
    """Mock chat for testing."""
    
    def __init__(self):
        self.history = []
        self.default_response = "BUY"
    
    def send_message(self, message: str) -> str:
        self.history.append(("user", message))
        self.history.append(("assistant", self.default_response))
        return self.default_response
    
    def get_history(self):
        """Return history as list of message-like objects."""
        class MockMessage:
            def __init__(self, role, text):
                self.role = role
                self.parts = [MockPart(text)]
        class MockPart:
            def __init__(self, text):
                self.text = text
        return [MockMessage(r, t) for r, t in self.history]
