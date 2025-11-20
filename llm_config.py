"""Configuration for LLM players."""

import os

# Gemini API Configuration
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
GEMINI_MODEL = "gemini-2.0-flash-exp"  # or "gemini-2.5-flash"

# Which players should be LLM players?
LLM_PLAYER_NAMES = ["Hero"]  # Change to [] to disable LLM players
