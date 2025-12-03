"""Run one game in-process (no multiprocessing) for debugging LLM calls.

Run from project root:

    python scripts/run_one_game.py

This runs `monopoly_game_llm` for a single game in the main process so LLM calls aren't executed inside worker processes.
"""

import sys
from pathlib import Path
import random

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from monopoly.core.game_llm import monopoly_game_llm


def main():
    # deterministic seed for debugging
    seed = random.Random(42).getrandbits(32)
    print(f"Running one game in-process with seed={seed}")
    monopoly_game_llm((1, seed))


if __name__ == '__main__':
    main()
