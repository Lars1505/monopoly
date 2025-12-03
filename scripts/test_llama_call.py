"""Quick test to call the LlamaChat implementation directly.

Run this from project root:

    python scripts/test_llama_call.py

This prints timing info and exception trace to help debug hangs.
"""

import sys
import time
from pathlib import Path

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from monopoly.llm.llm_interface import LlamaChat


def main():
    model = "gpt-oss:20b-cloud"
    print(f"Creating LlamaChat for model: {model}")
    chat = LlamaChat(model=model)

    msg = "Hello, please respond with a short token like BUY or PASS"
    print(f"Sending message: {msg}")
    start = time.time()
    try:
        resp = chat.send_message(msg)
        elapsed = time.time() - start
        print(f"Response received in {elapsed:.2f}s:\n{resp}")
    except Exception as e:
        elapsed = time.time() - start
        print(f"Exception after {elapsed:.2f}s: {e}")


if __name__ == '__main__':
    main()
