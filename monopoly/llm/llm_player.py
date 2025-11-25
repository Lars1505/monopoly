"""LLM-based player using Gemini multi-turn chat."""

from typing import List, Optional, Tuple
from monopoly.core.player import Player
from monopoly.core.board import Board
from monopoly.core.cell import Property
from monopoly.core.constants import RAILROADS, UTILITIES
from monopoly.llm.action_parser import ActionParser


class LLMPlayer(Player):
    """Player that makes decisions via Gemini chat."""
    
    def __init__(self, name: str, settings, chat):
        super().__init__(name, settings)
        self.chat = chat
        self.action_parser = ActionParser()
    
    def _build_full_context(self, board: Board, players: List[Player]) -> str:
        """Build concise full game context - always included in every message."""
        lines = []
        
        # Other players (mark LLM players)
        other_players = [p for p in players if p != self and not p.is_bankrupt]
        if other_players:
            lines.append("Players:")
            for p in other_players:
                pos_cell = board.cells[p.position]
                props = [prop.name for prop in p.owned[:5]]
                if len(p.owned) > 5:
                    props.append(f"({len(p.owned)} total)")
                props_str = ','.join(props)
                houses = sum(prop.has_houses for prop in p.owned)
                hotels = sum(prop.has_hotel for prop in p.owned)
                improv = f",{houses}H,{hotels}hotels" if (houses or hotels) else ""
                player_type = " [LLM]" if isinstance(p, LLMPlayer) else ""
                lines.append(f"{p.name}{player_type}:${p.money},{len(p.owned)}props({props_str}){improv},at {pos_cell.name}")
        
        # Board state
        lines.append("\nBoard:")
        for group_name in sorted(board.groups.keys()):
            prop_details = []
            for p in board.groups[group_name]:
                owner = p.owner.name if p.owner else "None"
                status = owner
                if p.has_hotel:
                    status += ":HOTEL"
                elif p.has_houses:
                    status += f":{p.has_houses}H"
                if p.is_mortgaged:
                    status += ":M"
                prop_details.append(f"{p.name}:{status}")
            lines.append(f"{group_name}:{'|'.join(prop_details)}")
        
        return "\n".join(lines)
    
    def _send_message(self, decision_prompt: str, board: Board, players: List[Player]) -> str:
        """Send message with full context always included."""
        context = self._build_full_context(board, players)
        full_message = f"{context}\n\n{decision_prompt}"
        return self.chat.send_message(full_message)
    
    def handle_landing_on_property(self, board, players, dice, log):
        """Override property purchase decision."""
        landed_property = board.cells[self.position]
        
        if landed_property.owner is None:
            owned_in_group = [p for p in self.owned if p.group == landed_property.group]
            total_in_group = len(board.groups[landed_property.group])
            
            same_group = [p for p in board.groups[landed_property.group] if p != landed_property]
            group_info = []
            for p in same_group:
                owner = p.owner.name if p.owner else "None"
                status = f"{owner}"
                if p.has_hotel:
                    status += ":HOTEL"
                elif p.has_houses:
                    status += f":{p.has_houses}H"
                group_info.append(f"{p.name}:{status}")
            
            prompt = f"""You:${self.money},net${self.net_worth()},pos {board.cells[self.position].name},{len(self.owned)}props,{landed_property.group}={len(owned_in_group)}/{total_in_group}
Property:{landed_property.name},cost${landed_property.cost_base},rent${landed_property.rent_base},after${self.money - landed_property.cost_base}
Same group:{'|'.join(group_info) if group_info else 'None'}
Decision:BUY or PASS"""
            
            try:
                response = self._send_message(prompt, board, players)
                should_buy = self.action_parser.parse_buy_decision(response)
                
                if should_buy and self.money >= landed_property.cost_base:
                    landed_property.owner = self
                    self.owned.append(landed_property)
                    self.money -= landed_property.cost_base
                    log.add(f"{self.name} (LLM) bought {landed_property} for ${landed_property.cost_base}")
                    board.recalculate_monopoly_multipliers(landed_property)
                    for player in players:
                        player.update_lists_of_properties_to_trade(board)
                else:
                    log.add(f"{self.name} (LLM) passed on {landed_property}")
            except Exception as e:
                log.add(f"{self.name} (LLM) error: {e}")
                if self.money - landed_property.cost_base >= self.settings.unspendable_cash:
                    landed_property.owner = self
                    self.owned.append(landed_property)
                    self.money -= landed_property.cost_base
        else:
            super().handle_landing_on_property(board, players, dice, log)
    
    def make_a_move(self, board, players, dice, log):
        """Store players context and handle LLM trading before rule-based trading."""
        self._current_players = players
        
        # Handle LLM-to-LLM trading before rule-based trading
        try:
            proposal = self.propose_trade_to_llm(board, players, log)
            if proposal:
                target_name = proposal['target']
                # Case-insensitive match for player name
                target_player = next((p for p in players if p.name.upper() == target_name.upper() and not p.is_bankrupt), None)
                
                if target_player and isinstance(target_player, LLMPlayer):
                    success, agreement = self.negotiate_trade(self, target_player, proposal, board, players, log)
                    if success and agreement:
                        if self.execute_llm_trade(self, target_player, agreement, board, players, log):
                            log.add(f"{self.name} and {target_player.name} completed LLM trade")
                elif target_player:
                    log.add(f"{self.name} tried to trade with non-LLM player {target_name}, skipping")
        except Exception as e:
            log.add(f"{self.name} LLM trading error: {e}, continuing normally")
        
        return super().make_a_move(board, players, dice, log)
    
    def improve_properties(self, board, log):
        """Override property improvement."""
        improvable = self._get_improvable_properties(board)
        if not improvable:
            return
        
        max_improvements = 5
        for _ in range(max_improvements):
            if not improvable:
                break
            
            props_list = [f"{p.name}:${p.cost_house},{'hotel' if p.has_houses == 4 else f'house{p.has_houses + 1}'}" for p in improvable]
            
            players = getattr(self, '_current_players', [])
            prompt = f"""You:${self.money},net${self.net_worth()},pos {board.cells[self.position].name}
Can improve:{'|'.join(props_list)}
Decision:IMPROVE:<name> or NO_IMPROVEMENT"""
            
            try:
                response = self._send_message(prompt, board, players)
                cleaned = self.action_parser.clean_response(response)
                prop = self.action_parser.parse_improve_decision(cleaned, improvable)
                
                if prop is None or self.money - prop.cost_house < self.settings.unspendable_cash:
                    break
                
                self._perform_improvement(prop, board, log)
                improvable = self._get_improvable_properties(board)
            except Exception:
                break
    
    def _get_improvable_properties(self, board: Board) -> List[Property]:
        """Get list of properties that can be improved."""
        can_improve = []
        for cell in self.owned:
            if (cell.has_hotel == 0 and not cell.is_mortgaged and 
                cell.monopoly_multiplier == 2 and cell.group not in (RAILROADS, UTILITIES)):
                for other_cell in board.groups[cell.group]:
                    if ((other_cell.has_houses < cell.has_houses and not other_cell.has_hotel) or 
                        other_cell.is_mortgaged):
                        break
                else:
                    if cell.has_houses != 4 and board.available_houses > 0:
                        can_improve.append(cell)
                    elif cell.has_houses == 4 and board.available_hotels > 0:
                        can_improve.append(cell)
        return can_improve
    
    def _perform_improvement(self, prop: Property, board: Board, log):
        """Perform the improvement."""
        if prop.has_houses != 4:
            prop.has_houses += 1
            board.available_houses -= 1
            self.money -= prop.cost_house
            log.add(f"{self} (LLM) built house #{prop.has_houses} on {prop} for ${prop.cost_house}")
        elif prop.has_houses == 4:
            prop.has_houses = 0
            prop.has_hotel = 1
            board.available_houses += 4
            board.available_hotels -= 1
            self.money -= prop.cost_house
            log.add(f"{self} (LLM) built hotel on {prop} for ${prop.cost_house}")
    
    def propose_trade_to_llm(self, board: Board, players: List[Player], log) -> Optional[dict]:
        """Propose a trade to another LLM player. Returns proposal dict or None."""
        try:
            # Get list of other LLM players
            llm_players = [p.name for p in players if isinstance(p, LLMPlayer) and p != self and not p.is_bankrupt]
            if not llm_players:
                return None
            
            llm_list = ','.join(llm_players)
            prompt = f"""Do you want to propose a trade? Optional. You can ONLY trade with other LLM players: {llm_list}
Format: TRADE_PROPOSE:<LLM_player_name>:<properties_to_give>:<properties_to_receive>:<cash_amount> or NO_TRADE
Properties should be comma-separated property names. Cash can be negative if you want to receive money."""
            
            response = self._send_message(prompt, board, players)
            parsed = self.action_parser.parse_trade_proposal(response)
            
            if not parsed:
                return None
            
            target_name, props_give, props_receive, cash = parsed
            return {
                'target': target_name,
                'give': props_give,
                'receive': props_receive,
                'cash': cash
            }
        except Exception:
            return None
    
    def negotiate_trade(self, proposer: 'LLMPlayer', target: 'LLMPlayer', proposal: dict, 
                       board: Board, players: List[Player], log) -> Tuple[bool, Optional[dict]]:
        """Negotiate trade between two LLM players. Returns (success, agreement)."""
        try:
            # Build proposal details string
            give_str = ','.join(proposal['give']) if proposal['give'] else 'nothing'
            receive_str = ','.join(proposal['receive']) if proposal['receive'] else 'nothing'
            cash_str = f"${proposal['cash']}" if proposal['cash'] != 0 else "no cash"
            
            initial_prompt = f"""You received a trade proposal from {proposer.name}. You can ONLY negotiate with LLM players.
Original proposal: {proposer.name} gives {give_str} and {cash_str}, receives {receive_str} from you.
Respond with TRADE_ACCEPT, TRADE_REJECT, or discuss (but terms stay the same)."""
            
            # Send initial proposal to target
            last_message = target._send_message(initial_prompt, board, players)
            
            proposer_accepted = False
            target_accepted = False
            
            # Negotiation loop (max 8 rounds)
            for round_num in range(8):
                # Check target's response
                target_response = target.action_parser.parse_negotiation_response(last_message)
                if target_response == 'accept':
                    target_accepted = True
                elif target_response == 'reject' or target_response == 'end':
                    return (False, None)
                
                if proposer_accepted and target_accepted:
                    return (True, proposal)
                
                # Proposer responds
                proposer_prompt = f"{target.name} said: {last_message}\nYour response:"
                proposer_message = proposer._send_message(proposer_prompt, board, players)
                
                # Check proposer's response
                proposer_response = proposer.action_parser.parse_negotiation_response(proposer_message)
                if proposer_response == 'accept':
                    proposer_accepted = True
                elif proposer_response == 'reject' or proposer_response == 'end':
                    return (False, None)
                
                if proposer_accepted and target_accepted:
                    return (True, proposal)
                
                # Target responds to proposer's message
                target_prompt = f"{proposer.name} said: {proposer_message}\nYour response:"
                last_message = target._send_message(target_prompt, board, players)
            
            # Max rounds reached
            return (False, None)
        except Exception:
            return (False, None)
    
    def execute_llm_trade(self, proposer: 'LLMPlayer', target: 'LLMPlayer', proposal: dict,
                         board: Board, players: List[Player], log) -> bool:
        """Execute the trade based on proposal. Returns True if successful."""
        try:
            # Validate players
            if proposer.is_bankrupt or target.is_bankrupt:
                return False
            
            # Find properties to give (from proposer)
            props_to_give = []
            for prop_name in proposal['give']:
                prop = next((p for p in proposer.owned if prop_name.upper() in p.name.upper()), None)
                if not prop:
                    log.add(f"Trade failed: {proposer.name} doesn't own {prop_name}")
                    return False
                props_to_give.append(prop)
            
            # Find properties to receive (from target)
            props_to_receive = []
            for prop_name in proposal['receive']:
                prop = next((p for p in target.owned if prop_name.upper() in p.name.upper()), None)
                if not prop:
                    log.add(f"Trade failed: {target.name} doesn't own {prop_name}")
                    return False
                props_to_receive.append(prop)
            
            # Validate cash
            cash = proposal['cash']
            if cash > 0 and proposer.money < cash:
                log.add(f"Trade failed: {proposer.name} doesn't have ${cash}")
                return False
            if cash < 0 and target.money < abs(cash):
                log.add(f"Trade failed: {target.name} doesn't have ${abs(cash)}")
                return False
            
            # Execute property transfers
            for prop in props_to_give:
                prop.owner = target
                proposer.owned.remove(prop)
                target.owned.append(prop)
                board.recalculate_monopoly_multipliers(prop)
            
            for prop in props_to_receive:
                prop.owner = proposer
                target.owned.remove(prop)
                proposer.owned.append(prop)
                board.recalculate_monopoly_multipliers(prop)
            
            # Execute cash transfer
            if cash > 0:
                proposer.money -= cash
                target.money += cash
            elif cash < 0:
                proposer.money += abs(cash)
                target.money -= abs(cash)
            
            # Update trade lists
            for player in players:
                player.update_lists_of_properties_to_trade(board)
            
            log.add(f"LLM Trade executed: {proposer.name} gave {[p.name for p in props_to_give]} and ${cash if cash > 0 else 0}, "
                   f"received {[p.name for p in props_to_receive]} and ${abs(cash) if cash < 0 else 0} from {target.name}")
            return True
        except Exception as e:
            log.add(f"Trade execution error: {e}")
            return False
