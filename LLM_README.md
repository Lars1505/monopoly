# LLM Players - Gemini Multi-Turn Chat

Use Google Gemini to play Monopoly with multi-turn conversations (one chat per game).

## Setup (3 steps)

1. **Install:** `pip install google-genai`

2. **Configure** `llm_config.py`:
   ```python
   GEMINI_API_KEY = "your-key-here"  # or set env var: export GEMINI_API_KEY="..."
   GEMINI_MODEL = "gemini-2.0-flash-exp"  # or "gemini-2.5-flash"
   LLM_PLAYER_NAMES = ["Hero"]  # Which players use LLM?
   ```

3. **Run:** `python scripts/simulate_llm.py`

## How It Works

- **One chat per game**: Creates a single Gemini chat session per simulated game
- **Multi-turn conversations**: LLM remembers previous decisions in the same game
- **Full context every message**: Every API call includes:
  - Your status (cash, properties, position)
  - All other players (money, properties, positions, houses/hotels)
  - Complete board state (all properties grouped by color)
- **Short responses**: System instruction encourages minimal responses (BUY/PASS/IMPROVE:name)
- **Chat history saved**: Each game's chat history saved to `gameHistory/game_{number}_chat_history.txt`

## Files

- `llm_config.py` - API key and configuration
- `monopoly/llm/llm_interface.py` - Gemini chat client
- `monopoly/llm/llm_player.py` - LLM player using chat.send_message()
- `monopoly/core/game_llm.py` - Game setup with chat creation/history saving
- `scripts/simulate_llm.py` - Run simulation
- `gameHistory/` - Chat history files (auto-created)
