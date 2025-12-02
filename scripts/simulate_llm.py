"""Run simulation with LLM players."""

import sys
from pathlib import Path
from datetime import datetime
import re

# Add project root to Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

import random
from tqdm.contrib.concurrent import process_map

from monopoly.analytics import Analyzer
from monopoly.core.game_llm import monopoly_game_llm
from monopoly.log_settings import LogSettings
from settings import SimulationSettings


def _get_models_from_config():
    """Extract unique model types from llm_config.py."""
    try:
        from llm_config import LLM_PLAYER_CONFIG, LLM_PROVIDER, GEMINI_MODEL, LLAMA_MODEL
        models = {cfg.get("model") for cfg in LLM_PLAYER_CONFIG.values() if "model" in cfg} if LLM_PLAYER_CONFIG else set()
        if not models:
            models = {GEMINI_MODEL if LLM_PROVIDER == "gemini" else LLAMA_MODEL}
        return sorted(models)
    except ImportError:
        return ["unknown"]


def _sanitize_model_name(name):
    """Convert model name to filesystem-safe string."""
    return re.sub(r'-+', '-', re.sub(r'[^\w\-]', '-', name)).strip('-')


def _create_run_dir(results_dir, run_dir=None):
    """Create run directory with timestamp and model types."""
    if run_dir:
        run_dir = Path(run_dir)
    else:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        models = "_".join(_sanitize_model_name(m) for m in _get_models_from_config())
        run_dir = results_dir / f"run_{timestamp}_{models}" if models else results_dir / f"run_{timestamp}"
    run_dir.mkdir(parents=True, exist_ok=True)
    return run_dir


def run_simulation(run_dir=None):
    """Run simulation with LLM support.
    
    Args:
        run_dir: Optional run directory path. If None, auto-generates one with
                 timestamp and model types from llm_config.py.
    """
    run_dir = _create_run_dir(project_root / "results", run_dir)
    print(f"Run directory: {run_dir}")
    
    LogSettings.init_logs(run_dir)
    
    rng = random.Random(SimulationSettings.seed)
    game_seed_pairs = [(i + 1, rng.getrandbits(32), run_dir) for i in range(SimulationSettings.n_games)]
    
    print(f"Running {SimulationSettings.n_games} games...")
    process_map(monopoly_game_llm, game_seed_pairs, max_workers=1, total=SimulationSettings.n_games, desc="Simulating games")
    Analyzer().run_all()


if __name__ == "__main__":
    run_simulation()
