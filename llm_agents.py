import json
import random
from typing import List, Optional, Dict
from dataclasses import dataclass, field
from pydantic import BaseModel, Field
import os


OPENAI_API_KEY = "" # @param {type:"string"}

print("agents llm_agents.py loaded")

from pydantic import BaseModel, Field
from typing import Optional, List
from openai import OpenAI

class TradeDetails(BaseModel):
    give_cash: int
    give_properties: List[str]
    get_cash: int
    get_properties: List[str]

class AgentDecision(BaseModel):
    thought_process: str = Field(description="Analyze the board state. Do I need to block a color set? Do I need cash?")
    action: str = Field(description="'OFFER', 'ACCEPT', 'REJECT', 'COUNTER'")
    trade_proposal: Optional[TradeDetails]

# 2. Updated Agent Class
class MonopolyAgent:
    def __init__(self, name: str, api_key: str):
        self.name = name
        self.client = OpenAI(api_key=api_key)

    def get_negotiation_decision(self, engine_output_text: str, negotiation_history: List[dict]) -> AgentDecision:
        """
        engine_output_text: The exact string from your screenshot
        negotiation_history: The back-and-forth of the current trade talk
        """
        
        system_prompt = f"""
        You are playing Monopoly. Your name is {self.name}.
        
        === CURRENT GAME STATE ===
        {engine_output_text}
        ==========================
        
        STRATEGY GUIDELINES:
        1. Analyze 'Board state': If an opponent has 2/3 of a color group, DO NOT give them the 3rd unless you get a massive return.
        2. Check 'Net worth': If you are leading, play conservatively.
        3. Check 'Status': If you are low on cash (<$200), value cash highly.
        
        Your goal is to negotiate a trade that improves your position relative to the others.
        """

        messages = [
            {"role": "system", "content": system_prompt}
        ]
        
        # Append the conversation history (e.g., "Alice offered you $500 for Park Place")
        messages.extend(negotiation_history)

        response = self.client.beta.chat.completions.parse(
            model="gpt-4o-2024-08-06",
            messages=messages,
            response_format=AgentDecision
        )
        
        return response.choices[0].message.parsed