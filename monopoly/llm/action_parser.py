"""Parse LLM responses into game actions."""

import re
from typing import Optional, Tuple, List
from monopoly.core.cell import Property


class ActionParser:
    """Parse LLM text responses into structured game actions."""
    
    @staticmethod
    def parse_buy_decision(llm_response: str) -> bool:
        """
        Parse a buy/pass decision from LLM response.
        
        Args:
            llm_response: The LLM's text response
            
        Returns:
            True if should buy, False if should pass
        """
        response_upper = llm_response.strip().upper()
        
        # Look for explicit keywords
        if "BUY" in response_upper and "DON'T BUY" not in response_upper and "NOT BUY" not in response_upper:
            return True
        if "PASS" in response_upper or "DECLINE" in response_upper or "NO" in response_upper[:10]:
            return False
        
        # Default to pass if unclear
        return False
    
    @staticmethod
    def parse_improve_decision(llm_response: str, available_properties: List[Property]) -> Optional[Property]:
        """
        Parse a property improvement decision from LLM response.
        
        Args:
            llm_response: The LLM's text response
            available_properties: List of properties that can be improved
            
        Returns:
            Property object to improve, or None if no improvement
        """
        response_upper = llm_response.strip().upper()
        
        # Check for explicit "no improvement" response
        if "NO_IMPROVEMENT" in response_upper or "NO IMPROVEMENT" in response_upper:
            return None
        if "PASS" in response_upper or "SKIP" in response_upper:
            return None
        
        # Look for "IMPROVE:" pattern
        improve_pattern = r"IMPROVE:\s*(.+?)(?:\n|$)"
        match = re.search(improve_pattern, response_upper)
        
        if match:
            property_name = match.group(1).strip()
            # Try to match with available properties
            for prop in available_properties:
                if property_name in prop.name.upper():
                    return prop
        
        # Try to find any property name mentioned in the response
        for prop in available_properties:
            # Check for various parts of the property name
            prop_name_upper = prop.name.upper()
            
            # Try full name
            if prop_name_upper in response_upper:
                return prop
            
            # Try just the main part (e.g., "BOARDWALK" from "H2 Boardwalk")
            parts = prop_name_upper.split()
            if len(parts) >= 2:
                main_name = " ".join(parts[1:])  # Skip the prefix like "A1", "H2"
                if main_name in response_upper:
                    return prop
        
        # Default to no improvement if unclear
        return None
    
    @staticmethod
    def parse_jail_decision(llm_response: str) -> str:
        """
        Parse a jail strategy decision from LLM response.
        
        Args:
            llm_response: The LLM's text response
            
        Returns:
            One of: 'use_goojf', 'pay_fine', 'wait'
        """
        response_upper = llm_response.strip().upper()
        
        # Check for explicit responses
        if "USE_GOOJF" in response_upper or "USE GOOJF" in response_upper or "USE CARD" in response_upper:
            return "use_goojf"
        
        if "PAY_FINE" in response_upper or "PAY FINE" in response_upper or "PAY" in response_upper[:20]:
            return "pay_fine"
        
        if "WAIT" in response_upper or "ROLL" in response_upper:
            return "wait"
        
        # Default to waiting (safest option)
        return "wait"
    
    @staticmethod
    def parse_trade_decision(llm_response: str) -> bool:
        """
        Parse a trade accept/reject decision from LLM response.
        
        Args:
            llm_response: The LLM's text response
            
        Returns:
            True if accept trade, False if reject
        """
        response_upper = llm_response.strip().upper()
        
        # Look for explicit keywords
        if "ACCEPT" in response_upper:
            return True
        if "REJECT" in response_upper or "DECLINE" in response_upper or "NO" in response_upper[:10]:
            return False
        
        # Default to reject if unclear
        return False
    
    @staticmethod
    def clean_response(llm_response: str) -> str:
        """
        Clean and extract the actual decision from LLM response.
        
        Sometimes LLMs add explanation or formatting. This tries to extract
        just the decision part.
        
        Args:
            llm_response: Raw LLM response
            
        Returns:
            Cleaned response with just the decision
        """
        # Remove common prefixes
        prefixes_to_remove = [
            "my decision is:",
            "i choose:",
            "i will:",
            "decision:",
            "action:",
            "response:",
        ]
        
        response_lower = llm_response.lower().strip()
        for prefix in prefixes_to_remove:
            if response_lower.startswith(prefix):
                llm_response = llm_response[len(prefix):].strip()
                break
        
        # If there are multiple lines, take the first non-empty line
        lines = [line.strip() for line in llm_response.split('\n') if line.strip()]
        if lines:
            return lines[0]
        
        return llm_response.strip()
    
    @staticmethod
    def parse_trade_proposal(llm_response: str) -> Optional[Tuple[str, List[str], List[str], int]]:
        """
        Parse a trade proposal from LLM response.
        
        Format: TRADE_PROPOSE:<target_player>:<properties_to_give>:<properties_to_receive>:<cash_amount>
        Properties are comma-separated.
        
        Args:
            llm_response: The LLM's text response
            
        Returns:
            (target_player_name, properties_to_give_list, properties_to_receive_list, cash_amount) or None
        """
        try:
            response_upper = llm_response.strip().upper()
            if "TRADE_PROPOSE:" not in response_upper or "NO_TRADE" in response_upper:
                return None
            
            # Extract the proposal part
            pattern = r"TRADE_PROPOSE:\s*([^:]+):\s*([^:]*):\s*([^:]*):\s*(-?\d+)"
            match = re.search(pattern, response_upper)
            if not match:
                return None
            
            target_player = match.group(1).strip()
            props_give_str = match.group(2).strip()
            props_receive_str = match.group(3).strip()
            cash_str = match.group(4).strip()
            
            # Parse properties (comma-separated, filter empty)
            props_give = [p.strip() for p in props_give_str.split(',') if p.strip()] if props_give_str else []
            props_receive = [p.strip() for p in props_receive_str.split(',') if p.strip()] if props_receive_str else []
            
            # Parse cash amount
            cash = int(cash_str) if cash_str else 0
            
            return (target_player, props_give, props_receive, cash)
        except Exception:
            return None
    
    @staticmethod
    def parse_negotiation_response(llm_response: str) -> Optional[str]:
        """
        Parse negotiation response to detect accept/reject/end.
        
        Args:
            llm_response: The LLM's text response
            
        Returns:
            'accept', 'reject', 'end', or None (continue negotiation)
        """
        try:
            response_upper = llm_response.strip().upper()
            
            if "TRADE_ACCEPT" in response_upper:
                return 'accept'
            if "TRADE_REJECT" in response_upper or "REJECT" in response_upper[:20]:
                return 'reject'
            if "TRADE_END" in response_upper or "END_NEGOTIATION" in response_upper:
                return 'end'
            
            return None
        except Exception:
            return None




