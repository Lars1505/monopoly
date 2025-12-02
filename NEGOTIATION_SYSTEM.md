# LLM Trade Negotiation System

## Overview
This document describes the simplified, structured counter-offer negotiation system for LLM players in Monopoly.

## How It Works

### 1. Initial Trade Proposal
When it's an LLM player's turn, they can propose a trade using:
```
TRADE_PROPOSE:<target_player>:<properties_to_give>:<properties_to_receive>:<cash_amount>
```

Example:
```
TRADE_PROPOSE:LLM2:Park Place:Boardwalk,Reading Railroad:300
```
Means: LLM1 gives Park Place + $300, receives Boardwalk + Reading Railroad from LLM2

### 2. Negotiation Phase (Max 3 Counter-Offers)

The target player receives the proposal and can respond with ONE of:

#### Option A: Accept
```
TRADE_ACCEPT
```
The trade executes immediately as proposed.

#### Option B: Reject
```
TRADE_REJECT
```
Negotiation ends, no trade happens.

#### Option C: Counter-Offer
```
TRADE_COUNTER:<props_you_give>:<props_you_receive>:<cash>
```

Example response from LLM2:
```
TRADE_COUNTER:Boardwalk:Park Place,Baltic Avenue:500
```
Means: LLM2 gives Boardwalk + $500, receives Park Place + Baltic Avenue

### 3. Counter-Offer Flow

When a counter-offer is made:
1. **Roles swap**: The responder becomes the new proposer
2. The original proposer receives the counter and can:
   - **TRADE_ACCEPT**: Accept the counter-offer
   - **TRADE_REJECT**: Reject and end negotiation
   - **TRADE_COUNTER**: Make another counter (if under 3 total)

### 4. Limits
- **Maximum 3 counter-offers** per negotiation
- After 3 counters, negotiation fails automatically
- Any unclear/invalid response is treated as rejection

## Example Negotiation Sequence

```
Turn 1: LLM1 proposes to LLM2
  LLM1 → LLM2: "Give me Boardwalk for Park Place + $200"
  
Turn 2: LLM2 counters (Counter #1)
  LLM2 → LLM1: "No, but I'll give you Boardwalk for Park Place + $500"
  
Turn 3: LLM1 counters (Counter #2)
  LLM1 → LLM2: "How about Boardwalk for Park Place + Baltic Avenue + $300"
  
Turn 4: LLM2 accepts
  LLM2: "TRADE_ACCEPT"
  ✓ Trade executes with final terms
```

## Format Details

### Cash Amounts
- **Positive cash**: Proposer gives cash to target
  - `TRADE_PROPOSE:LLM2:Park Place::300` = Give Park Place + $300, receive nothing
- **Negative cash**: Proposer receives cash from target
  - `TRADE_PROPOSE:LLM2::Boardwalk:-500` = Give nothing, receive Boardwalk + $500
- **Zero cash**: No cash exchange
  - `TRADE_PROPOSE:LLM2:Park Place:Boardwalk:0` = Straight property swap

### Multiple Properties
Use comma-separated property names:
```
TRADE_COUNTER:Park Place,Baltic Avenue:Boardwalk,Reading Railroad,Short Line:0
```

### Empty Properties
Use empty field (nothing between colons):
```
TRADE_PROPOSE:LLM2::Park Place:500
```
Means: Give $500, receive Park Place (no properties given)

## Improvements Over Old System

### Before (Discussion-based):
- ❌ LLMs could "discuss" indefinitely (up to 8 rounds)
- ❌ Responses were freeform and often confused with other actions
- ❌ "BUY", "PASS", "Thanks" treated as discussion
- ❌ High API call count (17+ calls per negotiation)
- ❌ Unclear when negotiation ended

### After (Structured counter-offers):
- ✅ Clear 3-action format (ACCEPT, REJECT, COUNTER)
- ✅ Maximum 3 counter-offers (predictable duration)
- ✅ Invalid/unclear responses = automatic rejection
- ✅ Lower API call count (2-8 calls per negotiation)
- ✅ Game state updates correctly after each counter

## Performance Impact

**API Calls per Negotiation:**
- Immediate accept/reject: 2 calls (proposal + response)
- 1 counter-offer: 4 calls
- 2 counter-offers: 6 calls
- 3 counter-offers (max): 8 calls

**Compared to old system:**
- Old system: 1 + (8 rounds × 2 messages) = up to 17 calls
- New system: Maximum 8 calls (53% reduction)
- Average case much better: most negotiations end in 2-4 calls

## Game State Management

After each counter-offer:
1. Roles swap internally (proposer ↔ responder)
2. New proposal becomes the active terms
3. Counter count increments
4. If accepted, final proposer/target are used for execution

When trade executes:
- Properties transfer ownership
- Cash transfers between players
- Board monopoly multipliers recalculate
- All players update their trade lists
- Event logged to game log

## Error Handling

- Unclear responses → treated as TRADE_REJECT
- Invalid counter format → treated as TRADE_REJECT
- Properties not owned → trade execution fails (logged)
- Insufficient cash → trade execution fails (logged)
- Max counters reached → negotiation fails
- Any exception → negotiation fails, player continues turn normally

