"""LLM-based player using Gemini multi-turn chat."""

import re
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
        self._current_turn = 0
        self._last_strategy_call = -999  # Track when we last called batched strategy
    
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

Respond with EXACTLY one of:
- BUY (purchase this property)
- PASS (skip this property)"""
            
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
        """Store players context and handle batched LLM strategy (trade + improvements)."""
        self._current_players = players
        self._current_turn += 1
        
        # Batched strategy call (every 3 turns)
        strategy = None
        if self._current_turn % 3 == 1 and len(self.owned) >= 2:
            strategy = self.get_turn_strategy(board, players, log)
            
            # Handle trade proposal if present
            if strategy.get('trade_proposal'):
                try:
                    proposal = strategy['trade_proposal']
                    target_name = proposal['target']
                    target_player = next((p for p in players if p.name.upper() == target_name.upper() and not p.is_bankrupt), None)
                    
                    if target_player and isinstance(target_player, LLMPlayer):
                        success, final_proposal, final_proposer, final_target = self.negotiate_trade(
                            self, target_player, proposal, board, players, log
                        )
                        if success and final_proposal and final_proposer and final_target:
                            if self.execute_llm_trade(final_proposer, final_target, final_proposal, board, players, log):
                                log.add(f"✓ Trade completed: {final_proposer.name} ↔ {final_target.name}")
                    elif target_player:
                        log.add(f"{self.name} tried to trade with non-LLM player {target_name}, skipping")
                except Exception as e:
                    log.add(f"{self.name} trade execution error: {e}")
        
        # Execute normal move (dice roll, movement, rent, etc.)
        result = super().make_a_move(board, players, dice, log)
        
        # Execute improvement strategy if we have one (after movement/purchases)
        if strategy and strategy.get('improvements'):
            try:
                self._execute_improvement_strategy(strategy['improvements'], board, log)
            except Exception as e:
                log.add(f"{self.name} improvement execution error: {e}")
        
        return result
    
    def improve_properties(self, board, log):
        """
        Override property improvement.
        NOTE: This is now a fallback method. Improvements are normally handled
        via batched strategy in make_a_move(). This only runs if batched strategy
        wasn't used (e.g., non-LLM turn or error case).
        """
        # Check if improvements were already handled by batched strategy this turn
        if hasattr(self, '_improvements_handled_this_turn') and self._improvements_handled_this_turn:
            return
        
        improvable = self._get_improvable_properties(board)
        if not improvable:
            return
        
        # Single call for all improvements (simplified from iterative)
        props_list = [f"{p.name}:${p.cost_house}" for p in improvable]
        players = getattr(self, '_current_players', [])
        
        prompt = f"""You:${self.money},net${self.net_worth()}
Can improve: {', '.join(props_list)}

Respond with EXACTLY one of:
- IMPROVE:<prop1>,<prop2>,... (comma-separated, max 5)
- NO_IMPROVEMENT"""
        
        try:
            response = self._send_message(prompt, board, players)
            cleaned = self.action_parser.clean_response(response)
            
            # Parse as batch improvement
            if "NO_IMPROVEMENT" in cleaned.upper():
                return
            
            if "IMPROVE:" in cleaned.upper():
                improve_match = re.search(r'IMPROVE:\s*(.+?)(?:\n|$)', cleaned, re.IGNORECASE)
                if improve_match:
                    props_str = improve_match.group(1).strip()
                    property_names = [p.strip() for p in props_str.split(',') if p.strip()]
                    self._execute_improvement_strategy(property_names, board, log)
        except Exception as e:
            log.add(f"{self.name} improvement error: {e}")
    
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
    
    def get_turn_strategy(self, board: Board, players: List[Player], log) -> dict:
        """
        Get batched decisions for trade proposal and improvements.
        Returns dict with 'trade_proposal' and 'improvements' keys.
        """
        # Skip if no properties to trade or improve
        if len(self.owned) < 2:
            return {'trade_proposal': None, 'improvements': []}
        
        # Build improvable properties list
        improvable = self._get_improvable_properties(board)
        improvable_str = ', '.join([f"{p.name}:${p.cost_house}" for p in improvable]) if improvable else "None"
        
        # Build LLM player list
        llm_players = [p.name for p in players if isinstance(p, LLMPlayer) and p != self and not p.is_bankrupt]
        llm_list = ', '.join(llm_players) if llm_players else "None"
        
        # Skip if nothing to do
        if not llm_players and not improvable:
            return {'trade_proposal': None, 'improvements': []}
        
        prompt = f"""TURN STRATEGY - Provide answers for ALL sections:

A) TRADE PROPOSAL (you can propose now, only every 3 turns)
   Available LLM players: {llm_list}
   Your properties: {', '.join([p.name for p in self.owned[:5]])}{'...' if len(self.owned) > 5 else ''}
   
   Respond with:
   - NO_TRADE, or
   - TRADE_PROPOSE:<player>:<props_you_give>:<props_you_receive>:<cash>
   
   Example: TRADE_PROPOSE:LLM2:Park Place:Boardwalk:200

B) PROPERTY IMPROVEMENTS (you have ${self.money})
   Can improve: {improvable_str}
   
   Respond with:
   - NO_IMPROVEMENT, or
   - IMPROVE:<prop1>,<prop2>,... (comma-separated, max 5)
   
   Example: IMPROVE:Park Place,Boardwalk

Respond in this exact format:
A) [your answer]
B) [your answer]"""
        
        try:
            response = self._send_message(prompt, board, players)
            parsed = self.action_parser.parse_batched_strategy(response)
            log.add(f"{self.name} batched strategy: trade={bool(parsed.get('trade_proposal'))}, improvements={len(parsed.get('improvements', []))}")
            return parsed
        except Exception as e:
            log.add(f"{self.name} strategy parsing error: {e}")
            return {'trade_proposal': None, 'improvements': []}
    
    def _execute_improvement_strategy(self, property_names: List[str], board: Board, log):
        """Execute pre-planned improvements from batched strategy."""
        improvable = self._get_improvable_properties(board)
        built_count = 0
        
        for prop_name in property_names:
            if built_count >= 5:
                break
            # Find matching property (case-insensitive, partial match)
            prop = next((p for p in improvable if prop_name.upper() in p.name.upper()), None)
            if prop and self.money >= prop.cost_house + self.settings.unspendable_cash:
                self._perform_improvement(prop, board, log)
                improvable = self._get_improvable_properties(board)
                built_count += 1
            else:
                if not prop:
                    log.add(f"{self.name} tried to improve unknown property: {prop_name}")
                else:
                    log.add(f"{self.name} insufficient cash to improve {prop.name}")
    
    def propose_trade_to_llm(self, board: Board, players: List[Player], log) -> Optional[dict]:
        """Propose a trade to another LLM player. Returns proposal dict or None."""
        try:
            # Get list of other LLM players
            llm_players = [p.name for p in players if isinstance(p, LLMPlayer) and p != self and not p.is_bankrupt]
            if not llm_players:
                return None
            
            llm_list = ', '.join(llm_players)
            prompt = f"""Do you want to propose a trade? You can ONLY trade with other LLM players: {llm_list}

Respond with EXACTLY one of:

1. NO_TRADE (skip trading this turn)

2. TRADE_PROPOSE:<player>:<props_you_give>:<props_you_receive>:<cash>
   Format details:
   - <player>: Target player name (one of: {llm_list})
   - <props_you_give>: Properties you give (comma-separated, or empty)
   - <props_you_receive>: Properties you receive (comma-separated, or empty)
   - <cash>: Cash amount (positive = you give, negative = you receive)
   
   Examples:
   - TRADE_PROPOSE:{llm_players[0]}:Park Place:Boardwalk:200
     (You give Park Place + $200, receive Boardwalk)
   - TRADE_PROPOSE:{llm_players[0]}::Reading Railroad:-300
     (You give nothing, receive Reading Railroad + $300)
   - TRADE_PROPOSE:{llm_players[0]}:Baltic Avenue,Park Place:Boardwalk,Short Line:0
     (Straight property swap, no cash)"""
            
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
                       board: Board, players: List[Player], log) -> Tuple[bool, Optional[dict], Optional['LLMPlayer'], Optional['LLMPlayer']]:
        """
        Negotiate trade between two LLM players using structured counter-offers.
        Max 3 counter-offers allowed per negotiation.
        
        Returns (success, final_proposal_dict, final_proposer, final_target)
        Note: proposer/target may swap during counter-offers, so final values are returned.
        """
        try:
            current_proposal = proposal
            current_proposer = proposer
            current_responder = target
            counter_count = 0
            max_counters = 3
            
            while counter_count <= max_counters:
                # Build proposal details string
                give_str = ', '.join(current_proposal['give']) if current_proposal['give'] else 'nothing'
                receive_str = ', '.join(current_proposal['receive']) if current_proposal['receive'] else 'nothing'
                
                if current_proposal['cash'] > 0:
                    cash_str = f"${current_proposal['cash']} cash"
                elif current_proposal['cash'] < 0:
                    cash_str = f"${abs(current_proposal['cash'])} cash (you give)"
                else:
                    cash_str = "no cash"
                
                # Send proposal to responder
                if counter_count == 0:
                    prompt = f"""You received a trade proposal from {current_proposer.name}.
Proposal: {current_proposer.name} gives you [{give_str}] and [{cash_str}], receives [{receive_str}] from you.

Respond with ONE of:
- TRADE_ACCEPT (accept the deal as-is)
- TRADE_REJECT (decline and end negotiation)
- TRADE_COUNTER:<props_you_give>:<props_you_receive>:<cash> (make a counter-offer)

Example counter: TRADE_COUNTER:Park Place:Boardwalk,Reading Railroad:200
This means: You give Park Place, receive Boardwalk + Reading Railroad + $200"""
                else:
                    prompt = f"""Counter-offer #{counter_count} from {current_proposer.name}.
New proposal: {current_proposer.name} gives you [{give_str}] and [{cash_str}], receives [{receive_str}] from you.

Respond with ONE of:
- TRADE_ACCEPT (accept this counter-offer)
- TRADE_REJECT (decline and end negotiation)
- TRADE_COUNTER:<props_you_give>:<props_you_receive>:<cash> (counter again, max {max_counters - counter_count} left)"""
                
                response = current_responder._send_message(prompt, board, players)
                action, counter_offer = current_responder.action_parser.parse_negotiation_response(response)
                
                # Handle response
                if action == 'accept':
                    log.add(f"✓ {current_responder.name} accepted trade from {current_proposer.name}")
                    return (True, current_proposal, current_proposer, current_responder)
                
                elif action == 'reject':
                    log.add(f"✗ {current_responder.name} rejected trade from {current_proposer.name}")
                    return (False, None, None, None)
                
                elif action == 'counter' and counter_offer:
                    counter_count += 1
                    if counter_count > max_counters:
                        log.add(f"✗ Max counter-offers ({max_counters}) reached, negotiation failed")
                        return (False, None, None, None)
                    
                    # Swap roles: responder becomes proposer with their counter-offer
                    log.add(f"↔ {current_responder.name} made counter-offer #{counter_count}")
                    current_proposal = counter_offer
                    current_proposer, current_responder = current_responder, current_proposer
                    # Continue loop with new proposal
                
                else:  # 'unclear' or invalid response
                    log.add(f"✗ {current_responder.name} gave unclear response, treating as rejection")
                    return (False, None, None, None)
            
            # Max counters reached
            log.add(f"✗ Negotiation ended: max {max_counters} counter-offers reached")
            return (False, None, None, None)
            
        except Exception as e:
            log.add(f"✗ Negotiation error: {e}")
            return (False, None, None, None)
    
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
