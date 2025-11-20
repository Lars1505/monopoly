"""Extended game setup with LLM player support."""

from pathlib import Path
from monopoly.core.game import setup_game, _check_end_conditions, log_players_and_board_state
from monopoly.core.move_result import MoveResult
from monopoly.log import Log
from monopoly.log_settings import LogSettings
from settings import SimulationSettings, GameSettings


def setup_players_llm(board, dice, chat):
    """Setup players with LLM support."""
    from monopoly.core.player import Player
    from monopoly.core.game_utils import assign_property
    from monopoly.llm.llm_player import LLMPlayer
    
    try:
        from llm_config import LLM_PLAYER_NAMES
    except ImportError:
        LLM_PLAYER_NAMES = []
    
    players = []
    for player_name, player_setting in GameSettings.players_list:
        if chat and player_name in LLM_PLAYER_NAMES:
            player = LLMPlayer(player_name, player_setting, chat)
        else:
            player = Player(player_name, player_setting)
        players.append(player)
    
    if GameSettings.shuffle_players:
        dice.shuffle(players)
    
    starting_money = GameSettings.starting_money
    if isinstance(starting_money, dict):
        for player in players:
            player.money = starting_money.get(player.name, 0)
    else:
        for player in players:
            player.money = starting_money
    
    for player in players:
        property_indices = GameSettings.starting_properties.get(player.name, [])
        for cell_index in property_indices:
            assign_property(player, board.cells[cell_index], board)
    
    return players


def monopoly_game_llm(game_number_and_seeds):
    """Game loop with LLM player support."""
    game_number, game_seed = game_number_and_seeds
    board, dice, events_log, bankruptcies_log = setup_game(game_number, game_seed)
    
    # Create Gemini chat for this game
    chat = None
    try:
        from llm_config import GEMINI_API_KEY, GEMINI_MODEL
        from monopoly.llm.llm_interface import GeminiChat, MockChat
        
        if GEMINI_API_KEY:
            chat = GeminiChat(api_key=GEMINI_API_KEY, model=GEMINI_MODEL)
            print(f"✓ Gemini chat created for game {game_number}")
        else:
            chat = MockChat()
    except Exception as e:
        print(f"⚠ Gemini setup failed: {e}, using mock")
        from monopoly.llm.llm_interface import MockChat
        chat = MockChat()
    
    players = setup_players_llm(board, dice, chat)
    
    # Game loop
    for turn_n in range(1, SimulationSettings.n_moves + 1):
        events_log.add(f"\n== GAME {game_number} Turn {turn_n} ===")
        log_players_and_board_state(board, events_log, players)
        board.log_board_state(events_log)
        events_log.add("")
        
        if _check_end_conditions(players, events_log, game_number, turn_n):
            break
        
        for player in players:
            if player.is_bankrupt:
                continue
            move_result = player.make_a_move(board, players, dice, events_log)
            if move_result == MoveResult.BANKRUPT:
                bankruptcies_log.add(f"{game_number}\t{player}\t{turn_n}")
    
    # Save chat history
    if chat:
        history_dir = Path("gameHistory")
        history_dir.mkdir(exist_ok=True)
        history_file = history_dir / f"game_{game_number}_chat_history.txt"
        
        with open(history_file, 'w') as f:
            f.write(f"=== Game {game_number} Chat History ===\n\n")
            for message in chat.get_history():
                role = getattr(message, 'role', 'unknown')
                parts = getattr(message, 'parts', [])
                text = parts[0].text if parts and hasattr(parts[0], 'text') else str(parts[0]) if parts else ""
                f.write(f"{role.upper()}: {text}\n\n")
        print(f"✓ Chat history saved to {history_file}")
    
    board.log_current_map(events_log)
    events_log.save()
    if bankruptcies_log.content:
        bankruptcies_log.save()
