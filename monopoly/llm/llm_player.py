"""LLM-based player using Gemini multi-turn chat."""

from typing import List, Optional
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
        
        # Other players
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
                lines.append(f"{p.name}:${p.money},{len(p.owned)}props({props_str}){improv},at {pos_cell.name}")
        
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
        """Store players context."""
        self._current_players = players
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
