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
    def parse_negotiation_response(llm_response: str) -> Tuple[str, Optional[dict]]:
        """
        Parse negotiation response to detect accept/reject/counter.
        
        Args:
            llm_response: The LLM's text response
            
        Returns:
            Tuple of (action, counter_offer_dict)
            - action: 'accept', 'reject', 'counter', or 'unclear'
            - counter_offer_dict: If action is 'counter', contains the counter-offer details, else None
        """
        try:
            response_upper = llm_response.strip().upper()
            
            # Check for explicit accept
            if "TRADE_ACCEPT" in response_upper or response_upper.startswith("ACCEPT"):
                return ('accept', None)
            
            # Check for explicit reject
            if "TRADE_REJECT" in response_upper or response_upper.startswith("REJECT"):
                return ('reject', None)
            
            # Check for counter-offer
            # Format: TRADE_COUNTER:<properties_to_give>:<properties_to_receive>:<cash_amount>
            if "TRADE_COUNTER:" in response_upper:
                pattern = r"TRADE_COUNTER:\s*([^:]*):\s*([^:]*):\s*(-?\d+)"
                match = re.search(pattern, response_upper)
                if match:
                    props_give_str = match.group(1).strip()
                    props_receive_str = match.group(2).strip()
                    cash_str = match.group(3).strip()
                    
                    props_give = [p.strip() for p in props_give_str.split(',') if p.strip()] if props_give_str else []
                    props_receive = [p.strip() for p in props_receive_str.split(',') if p.strip()] if props_receive_str else []
                    cash = int(cash_str) if cash_str else 0
                    
                    counter_offer = {
                        'give': props_give,
                        'receive': props_receive,
                        'cash': cash
                    }
                    return ('counter', counter_offer)
            
            # If unclear or conversational, treat as reject
            # (Prevents endless discussion loops)
            return ('unclear', None)
        except Exception:
            return ('unclear', None)
    
    @staticmethod
    def parse_batched_strategy(llm_response: str) -> dict:
        """
        Parse batched turn strategy response.
        Expected format:
        A) TRADE_PROPOSE:... or NO_TRADE
        B) IMPROVE:... or NO_IMPROVEMENT
        
        Returns dict with 'trade_proposal' and 'improvements' keys.
        """
        result = {'trade_proposal': None, 'improvements': []}
        
        try:
            # Extract section A (trade)
            a_match = re.search(r'A\)\s*(.+?)(?=B\)|$)', llm_response, re.IGNORECASE | re.DOTALL)
            if a_match:
                a_text = a_match.group(1).strip()
                if "NO_TRADE" not in a_text.upper():
                    parsed_trade = ActionParser.parse_trade_proposal(a_text)
                    if parsed_trade:
                        target, give, receive, cash = parsed_trade
                        result['trade_proposal'] = {
                            'target': target,
                            'give': give,
                            'receive': receive,
                            'cash': cash
                        }
            
            # Extract section B (improvements)
            b_match = re.search(r'B\)\s*(.+?)$', llm_response, re.IGNORECASE | re.DOTALL)
            if b_match:
                b_text = b_match.group(1).strip()
                if "NO_IMPROVEMENT" not in b_text.upper() and "IMPROVE:" in b_text.upper():
                    improve_match = re.search(r'IMPROVE:\s*(.+?)(?:\n|$)', b_text, re.IGNORECASE)
                    if improve_match:
                        props = improve_match.group(1).strip()
                        result['improvements'] = [p.strip() for p in props.split(',') if p.strip()]
        
        except Exception:
            pass
        
        return result




