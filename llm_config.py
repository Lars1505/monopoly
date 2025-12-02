"""Configuration for LLM players."""

import os

# Global Gemini API Key (shared by all Gemini players, can be overridden per-player)
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "AIzaSyBa3kG9Sc2On_DeaMGENdDR9rglISWSfUo")

# Per-player LLM configuration
# Each player can have their own provider and model
# Format: {"player_name": {"provider": "gemini"|"llama", "model": "model_name", "api_key": "optional"}}
LLM_PLAYER_CONFIG = {
    "LLM1": {"provider": "llama", "model": "gpt-oss:20b-cloud"},
    "LLM2": {"provider": "llama", "model": "gpt-oss:20b-cloud"},
    # Example for multiple players:
    # "Alice": {"provider": "gemini", "model": "gemini-2.0-flash-exp"},
    # "Bob": {"provider": "llama", "model": "gpt-oss:120b-cloud"},
}

# Legacy single-provider config (for backward compatibility)
# If LLM_PLAYER_CONFIG is empty or player not found, these defaults are used
LLM_PROVIDER = os.getenv("LLM_PROVIDER", "gemini")  # Options: "gemini", "llama"
GEMINI_MODEL = "gemini-2.0-flash-exp"  # or "gemini-2.5-flash"
LLAMA_MODEL = os.getenv("LLAMA_MODEL", "gpt-oss:120b-cloud")  # Ollama model name

# Which players should be LLM players?
# If LLM_PLAYER_CONFIG is defined, this is derived from config keys
# Otherwise, use this list directly
if LLM_PLAYER_CONFIG:
    LLM_PLAYER_NAMES = list(LLM_PLAYER_CONFIG.keys())
else:
    LLM_PLAYER_NAMES = ["Hero"]  # Change to [] to disable LLM players
