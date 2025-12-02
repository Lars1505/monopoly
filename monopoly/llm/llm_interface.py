"""LLM interface with multi-turn chat support for Gemini and Llama."""

from google import genai
from google.genai import types
from typing import Optional
import ollama
import time


class GeminiChat:
    """Gemini chat interface - one chat per game."""
    
    def __init__(self, api_key: str, model: str = "gemini-2.0-flash-exp", logger=None):
        """Create a new Gemini chat session.
        
        Args:
            api_key: Gemini API key
            model: Model name to use
            logger: Optional callable to log messages (e.g., events_log.add)
        """
        self.client = genai.Client(api_key=api_key)
        self.logger = logger
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
        delays = [120, 240, 480, 960, 1920, 3840]  # 2, 4, 8, 16, 32, 64 minutes in seconds
        
        for attempt, delay in enumerate(delays):
            try:
                response = self.chat.send_message(message)
                return response.text.strip()
            except Exception as e:
                error_str = str(e)
                is_rate_limit = "429" in error_str or "rate limit" in error_str.lower() or "usage limit" in error_str.lower()
                
                if is_rate_limit and attempt < len(delays) - 1:
                    delay_min = delay // 60
                    print("\n" + "="*80)
                    print(f"⚠️  GEMINI API RATE LIMIT ERROR (Attempt {attempt + 1}/{len(delays)})")
                    print(f"⚠️  Error: {e}")
                    print(f"⚠️  Retrying in {delay_min} minutes ({delay} seconds)...")
                    print("="*80 + "\n")
                    if self.logger:
                        self.logger(f"[PRINT] Gemini API rate limit error: {e}. Retrying in {delay_min} minutes...")
                    time.sleep(delay)
                else:
                    print("\n" + "!"*80)
                    print(f"❌ GEMINI API ERROR - FINAL FAILURE")
                    print(f"❌ Error: {e}")
                    print("!"*80 + "\n")
                    if self.logger:
                        self.logger(f"[PRINT] Gemini API error: {e}")
                    return "PASS"
        
        return "PASS"
    
    def get_history(self):
        """Get full chat history."""
        return self.chat.get_history()


class LlamaChat:
    """Llama chat interface - one chat per game with manual history management."""
    
    def __init__(self, model: str = "gpt-oss:120b-cloud", logger=None):
        """Create a new Llama chat session.
        
        Args:
            model: Model name to use
            logger: Optional callable to log messages (e.g., events_log.add)
        """
        self.model = model
        self.logger = logger
        self.history = []
        # Add system instruction as first message
        self.history.append({
            'role': 'system',
            'content': """You are playing Monopoly.
            You can BUY properties, PASS on buying, IMPROVE properties or choose NO_IMPROVEMENT.
            You can negotiate trades with the other player, you only have one round to negotiate, so make your moves wisely.
            The other player can accept, reject or counter your offer.
            Other users can also negotiate trades with you, you can accept or reject their counter-offers or make a counter-offer.
            but you can only counter once.
            Give your reasons briefly if needed.
            You will respond with NEGOTIATE:<offer_details> when you want to request negotiation, 
            ACCEPT, REJECT, BUY, PASS, IMPROVE:<property_name>, or NO_IMPROVEMENT with brief explanations. 
            """
        })
    
    def send_message(self, message: str) -> str:
        """Send message to chat and return response."""
        delays = [120, 240, 480, 960, 1920, 3840]  # 2, 4, 8, 16, 32, 64 minutes in seconds
        
        for attempt, delay in enumerate(delays):
            try:
                # Add user message to history
                self.history.append({'role': 'user', 'content': message})
                # Get response from Ollama
                response = ollama.chat(model=self.model, messages=self.history)
                
                # Extract reply
                reply = response['message']['content']
                
                # Add assistant reply to history
                self.history.append({'role': 'assistant', 'content': reply})
                
                return reply
            except Exception as e:
                error_str = str(e)
                is_rate_limit = "429" in error_str or "rate limit" in error_str.lower() or "usage limit" in error_str.lower()
                
                # Remove the user message we just added if it failed
                if self.history and self.history[-1]['role'] == 'user':
                    self.history.pop()
                
                if is_rate_limit and attempt < len(delays) - 1:
                    delay_min = delay // 60
                    print("\n" + "="*80)
                    print(f"⚠️  LLAMA API RATE LIMIT ERROR (Attempt {attempt + 1}/{len(delays)})")
                    print(f"⚠️  Error: {e}")
                    print(f"⚠️  Retrying in {delay_min} minutes ({delay} seconds)...")
                    print("="*80 + "\n")
                    if self.logger:
                        self.logger(f"[PRINT] Llama API rate limit error: {e}. Retrying in {delay_min} minutes...")
                    time.sleep(delay)
                else:
                    print("\n" + "!"*80)
                    print(f"❌ LLAMA API ERROR - FINAL FAILURE")
                    print(f"❌ Error: {e}")
                    print("!"*80 + "\n")
                    if self.logger:
                        self.logger(f"[PRINT] Llama API error: {e}")
                    return "PASS"
        
        return "PASS"
    
    def get_history(self):
        """Return history as list of message-like objects compatible with Gemini format."""
        class MockMessage:
            def __init__(self, role, text):
                self.role = role
                self.parts = [MockPart(text)]
        class MockPart:
            def __init__(self, text):
                self.text = text
        
        # Filter out system messages and convert to message-like objects
        messages = []
        for msg in self.history:
            if msg['role'] != 'system':  # Skip system messages in history output
                messages.append(MockMessage(msg['role'], msg['content']))
        return messages


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
