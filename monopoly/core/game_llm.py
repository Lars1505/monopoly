"""Extended game setup with LLM player support."""

from pathlib import Path
from monopoly.core.game import setup_game, _check_end_conditions, log_players_and_board_state
from monopoly.core.move_result import MoveResult
from monopoly.log import Log
from monopoly.log_settings import LogSettings
from settings import SimulationSettings, GameSettings


def setup_players_llm(board, dice, events_log=None):
    """Setup players with LLM support."""
    from monopoly.core.player import Player
    from monopoly.core.game_utils import assign_property
    from monopoly.llm.llm_player import LLMPlayer
    
    def log_print(*args, **kwargs):
        msg = ' '.join(str(arg) for arg in args)
        if events_log and msg.strip():
            events_log.add(f"[PRINT] {msg}")
        print(*args, **kwargs)
    
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
                
                logger = (lambda msg: events_log.add(msg)) if events_log else None
                
                if provider == "llama":
                    chat = LlamaChat(model=model, logger=logger)
                    log_print(f"✓ Llama chat created for {player_name} (model: {model})")
                elif provider == "gemini":
                    if api_key:
                        chat = GeminiChat(api_key=api_key, model=model, logger=logger)
                        log_print(f"✓ Gemini chat created for {player_name} (model: {model})")
                    else:
                        chat = MockChat()
                        log_print(f"⚠ GEMINI_API_KEY not set for {player_name}, using mock")
                else:
                    chat = MockChat()
                    log_print(f"⚠ Unknown provider '{provider}' for {player_name}, using mock")
            except Exception as e:
                log_print(f"⚠ Chat setup failed for {player_name}: {e}, using mock")
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


def monopoly_game_llm(game_number_and_seeds_and_run_dir):
    """Game loop with LLM player support."""
    game_number, game_seed, run_dir = game_number_and_seeds_and_run_dir
    board, dice, events_log, bankruptcies_log = setup_game(game_number, game_seed, run_dir)
    
    def log_print(*args, **kwargs):
        msg = ' '.join(str(arg) for arg in args)
        if msg.strip():
            events_log.add(f"[PRINT] {msg}")
        print(*args, **kwargs)
    
    # Setup players and create individual chat instances for each LLM player
    players, player_chats = setup_players_llm(board, dice, events_log)
    
    # COMMENTED OUT: Hardcoded test/debug code that forces initial negotiation before game starts.
    # This causes performance issues by triggering unnecessary API calls before gameplay begins.
    # The LLMs will negotiate naturally during the game via propose_trade_to_llm() in llm_player.py.
    # LLM1_chat = player_chats.get("LLM1", None)
    # LLM2_chat = player_chats.get("LLM2", None)
    # r1 = LLM1_chat.send_message("You are playing Monopoly, you want to negotiate with the other players now") # assume engine output
    # log_print(r1)
    # if r1.startswith("NEGOTIATE"):
    #     r2 = LLM2_chat.send_message(r1 + "It's your turn to respond to the trade proposal in Monopoly, you can accept, reject or counter the offer, you can only counter once.") # assume engine output
    #     log_print(r2)
    #     r1 = LLM1_chat.send_message(r2 + "You can only accept or reject this deal for this turn") # assume engine output
    #     log_print(r1)
    # else: 
    #     r2 = LLM2_chat.send_message("<engine output>: You are playing Monopoly, you are at Park Place, with cash $800.") # assume engine output
    #     log_print(r2)    
    
    # Initialize chat history files
    history_dir = Path(run_dir) if run_dir else Path("gameHistory")
    history_dir.mkdir(parents=True, exist_ok=True)
    history_files = {name: history_dir / f"game_{game_number}_{name}_chat_history.txt" for name in player_chats.keys()}
    for name, file in history_files.items():
        file.write_text(f"=== Game {game_number} Chat History for {name} ===\n\n")
    
    def _update_chat_history(player_name, chat):
        if player_name not in history_files:
            return
        try:
            lines = [f"=== Game {game_number} Chat History for {player_name} ===\n\n"]
            for msg in chat.get_history():
                role = getattr(msg, 'role', 'unknown')
                parts = getattr(msg, 'parts', [])
                text = parts[0].text if parts and hasattr(parts[0], 'text') else str(parts[0]) if parts else ""
                lines.append(f"{role.upper()}: {text}\n")
                lines.append("============\n\n")
            history_files[player_name].write_text(''.join(lines))
        except Exception:
            pass
    
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
            log_print(f"✓ Chat history saved to {history_files[player_name]}")
    
    board.log_current_map(events_log)
    events_log.save()
    if bankruptcies_log.content:
        bankruptcies_log.save()
