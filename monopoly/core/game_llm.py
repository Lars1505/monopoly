"""Extended game setup with LLM player support."""

from pathlib import Path
from monopoly.core.game import setup_game, _check_end_conditions, log_players_and_board_state
from monopoly.core.move_result import MoveResult
from monopoly.log import Log
from monopoly.log_settings import LogSettings
from settings import SimulationSettings, GameSettings


def setup_players_llm(board, dice):
    """Setup players with LLM support. Creates individual chat instances for each LLM player.
    
    Returns:
        tuple: (players list, dict mapping player_name to chat_instance)
    """
    from monopoly.core.player import Player
    from monopoly.core.game_utils import assign_property
    from monopoly.llm.llm_player import LLMPlayer
    
    try:
        from llm_config import LLM_PLAYER_NAMES, LLM_PLAYER_CONFIG, LLM_PROVIDER, GEMINI_API_KEY, GEMINI_MODEL, LLAMA_MODEL
        from monopoly.llm.llm_interface import GeminiChat, LlamaChat, MockChat
    except ImportError:
        LLM_PLAYER_NAMES = []
        LLM_PLAYER_CONFIG = {}
        LLM_PROVIDER = "gemini"
        GEMINI_API_KEY = None
        GEMINI_MODEL = "gemini-2.0-flash-exp"
        LLAMA_MODEL = "gpt-oss:120b-cloud"
        from monopoly.llm.llm_interface import MockChat
    
    # Create chat instances for each LLM player
    player_chats = {}
    
    for player_name, player_setting in GameSettings.players_list:
        if player_name in LLM_PLAYER_NAMES:
            chat = None
            try:
                # Try to get per-player config
                if LLM_PLAYER_CONFIG and player_name in LLM_PLAYER_CONFIG:
                    config = LLM_PLAYER_CONFIG[player_name]
                    provider = config.get("provider", LLM_PROVIDER).lower()
                    model = config.get("model", GEMINI_MODEL if provider == "gemini" else LLAMA_MODEL)
                    api_key = config.get("api_key", GEMINI_API_KEY)
                else:
                    # Fall back to legacy single-provider config
                    provider = LLM_PROVIDER.lower()
                    if provider == "gemini":
                        model = GEMINI_MODEL
                        api_key = GEMINI_API_KEY
                    else:
                        model = LLAMA_MODEL
                        api_key = None
                
                # Create appropriate chat instance
                if provider == "llama":
                    chat = LlamaChat(model=model)
                    print(f"✓ Llama chat created for {player_name} (model: {model})")
                elif provider == "gemini":
                    if api_key:
                        chat = GeminiChat(api_key=api_key, model=model)
                        print(f"✓ Gemini chat created for {player_name} (model: {model})")
                    else:
                        print(f"⚠ GEMINI_API_KEY not set for {player_name}, using mock")
                        chat = MockChat()
                else:
                    print(f"⚠ Unknown provider '{provider}' for {player_name}, using mock")
                    chat = MockChat()
            except Exception as e:
                print(f"⚠ Chat setup failed for {player_name}: {e}, using mock")
                chat = MockChat()
            
            player_chats[player_name] = chat
    
    # Create players with their respective chats
    players = []
    for player_name, player_setting in GameSettings.players_list:
        if player_name in LLM_PLAYER_NAMES and player_name in player_chats:
            player = LLMPlayer(player_name, player_setting, player_chats[player_name])
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
    
    return players, player_chats


def monopoly_game_llm(game_number_and_seeds):
    """Game loop with LLM player support."""
    game_number, game_seed = game_number_and_seeds
    board, dice, events_log, bankruptcies_log = setup_game(game_number, game_seed)
    
    # Setup players and create individual chat instances for each LLM player
    players, player_chats = setup_players_llm(board, dice)
    
    # Initialize chat history files for real-time updates
    history_dir = Path("gameHistory")
    history_dir.mkdir(exist_ok=True)
    history_files = {name: history_dir / f"game_{game_number}_{name}_chat_history.txt" 
                     for name in player_chats.keys()}
    for name, file in history_files.items():
        with open(file, 'w') as f:
            f.write(f"=== Game {game_number} Chat History for {name} ===\n\n")
    
    def _update_chat_history(player_name, chat):
        """Update chat history file in real-time."""
        if player_name not in history_files:
            return
        try:
            with open(history_files[player_name], 'w') as f:
                f.write(f"=== Game {game_number} Chat History for {player_name} ===\n\n")
                for message in chat.get_history():
                    role = getattr(message, 'role', 'unknown')
                    parts = getattr(message, 'parts', [])
                    text = parts[0].text if parts and hasattr(parts[0], 'text') else str(parts[0]) if parts else ""
                    f.write(f"{role.upper()}: {text}\n\n")
                f.flush()
        except Exception:
            pass  # Silently fail to avoid disrupting game
    
    # Game loop
    for turn_n in range(1, SimulationSettings.n_moves + 1):
        events_log.add(f"\n== GAME {game_number} Turn {turn_n} ===")
        log_players_and_board_state(board, events_log, players)
        board.log_board_state(events_log)
        events_log.add("")
        events_log.flush()  # Flush after each turn
        
        if _check_end_conditions(players, events_log, game_number, turn_n):
            break
        
        for player in players:
            if player.is_bankrupt:
                continue
            move_result = player.make_a_move(board, players, dice, events_log)
            if move_result == MoveResult.BANKRUPT:
                bankruptcies_log.add(f"{game_number}\t{player}\t{turn_n}")
                bankruptcies_log.flush()
            
            # Update chat history for LLM players in real-time
            if hasattr(player, 'chat') and player.name in history_files:
                _update_chat_history(player.name, player.chat)
    
    # Final update of chat history files
    for player_name, chat in player_chats.items():
        if chat and player_name in history_files:
            _update_chat_history(player_name, chat)
            print(f"✓ Chat history saved to {history_files[player_name]}")
    
    board.log_current_map(events_log)
    events_log.save()
    if bankruptcies_log.content:
        bankruptcies_log.save()
