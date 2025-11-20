"""Run simulation with LLM players."""

import random
from tqdm.contrib.concurrent import process_map

from monopoly.analytics import Analyzer
from monopoly.core.game_llm import monopoly_game_llm
from monopoly.log_settings import LogSettings
from settings import SimulationSettings


def run_simulation():
    """Run simulation with LLM support."""
    LogSettings.init_logs()
    
    master_rng = random.Random(SimulationSettings.seed)
    game_seed_pairs = [
        (i + 1, master_rng.getrandbits(32)) 
        for i in range(SimulationSettings.n_games)
    ]
    
    print(f"Running {SimulationSettings.n_games} games...")
    
    # Use single process for LLM to avoid API rate limits
    process_map(
        monopoly_game_llm,
        game_seed_pairs,
        max_workers=1,
        total=SimulationSettings.n_games,
        desc="Simulating games",
    )
    
    Analyzer().run_all()


if __name__ == "__main__":
    run_simulation()
