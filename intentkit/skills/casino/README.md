# Casino Skills for IntentKit

The Casino skills provide comprehensive gambling and gaming capabilities for AI agents, enabling interactive card games, dice games, and casino-style entertainment.

## 🎯 Overview

This skill set includes three main functions:
- **Deck Shuffling**: Create and shuffle card decks with customizable options
- **Card Drawing**: Draw cards with visual PNG/SVG images 
- **Quantum Dice Rolling**: True random dice using quantum number generation

## 🛠️ Available Skills

### 1. `casino_deck_shuffle`
Creates and shuffles new card decks with options for multiple decks and jokers.

**Parameters:**
- `deck_count` (int): Number of decks (1-6, default: 1)
- `jokers_enabled` (bool): Include jokers (default: false)

### 2. `casino_deck_draw` 
Draws cards from the current deck with detailed information and images.

**Parameters:**
- `count` (int): Number of cards to draw (1-10, default: 1)

### 3. `casino_dice_roll`
Rolls quantum random dice with visual representation.

**Parameters:**
- `dice_count` (int): Number of dice to roll (1-10, default: 1)

## 🎮 Game Examples

### 🃏 Blackjack (21)

**Setup:**
```
Agent: I'll set up a Blackjack game for you! Let me shuffle a fresh deck.
[Calls casino_deck_shuffle with deck_count=1]
```

**Dealing Cards:**
```
Agent: Dealing your cards...
[Calls casino_deck_draw with count=2 for player]
[Calls casino_deck_draw with count=1 for dealer, 1 face down]

Result: You have: King♠️ (image) + 7♥️ (image) = 17
Dealer shows: Ace♣️ (image) + [hidden card]
```

**Player Actions:**
```
User: "Hit me"
Agent: [Calls casino_deck_draw with count=1]
Result: You drew 3♦️ (image). Total: 20

User: "Stand"
Agent: Revealing dealer's hidden card...
[Calls casino_deck_draw for dealer's hidden card and additional cards as needed]
```

### 🎲 Craps

**Come Out Roll:**
```
Agent: Welcome to the Craps table! Place your bets and let's roll!
[Calls casino_dice_roll with dice_count=2]

Result: 🎲 Rolled: ⚂ ⚃ (3 + 4 = 7) - WINNER! 
The shooter made their point on the come out roll!
```

**Point Phase:**
```
Agent: Point is 6. Rolling again...
[Calls casino_dice_roll with dice_count=2]

Result: 🎲 Rolled: ⚁ ⚄ (2 + 5 = 7) - Seven out! 
New shooter coming up.
```

### 🃏 Texas Hold'em Poker

**Pre-flop:**
```
Agent: Dealing pocket cards...
[Calls casino_deck_shuffle with deck_count=1]
[Calls casino_deck_draw with count=2 for each player]

Your cards: A♠️ (image) K♠️ (image) - Ace-King suited!
```

**The Flop:**
```
Agent: Dealing the flop...
[Calls casino_deck_draw with count=3]

Flop: A♦️ (image) K♣️ (image) 7♠️ (image)
You have two pair - Aces and Kings!
```

**Turn and River:**
```
Agent: Turn card...
[Calls casino_deck_draw with count=1]
Turn: Q♠️ (image)

River card...
[Calls casino_deck_draw with count=1] 
River: J♠️ (image)

Final board: A♦️ K♣️ 7♠️ Q♠️ J♠️
You have a straight! A-K-Q-J-10
```

### 🎯 Yahtzee

**First Roll:**
```
Agent: Rolling all 5 dice for Yahtzee!
[Calls casino_dice_roll with dice_count=5]

Result: ⚀ ⚃ ⚃ ⚄ ⚅ (1, 4, 4, 5, 6)
Which dice would you like to keep?
```

**Rerolls:**
```
User: "Keep the two 4s"
Agent: Rerolling 3 dice...
[Calls casino_dice_roll with dice_count=3]

Result: ⚃ ⚃ ⚃ (4, 4, 4) - Combined with your kept dice: ⚃ ⚃ ⚃ ⚃ ⚃
YAHTZEE! Five of a kind - 4s! 🎉
```

### 🎲 Liar's Dice

**Round Start:**
```
Agent: Everyone roll your dice under the cup!
[Each player calls casino_dice_roll with dice_count=5]

Your dice (hidden): ⚁ ⚁ ⚂ ⚄ ⚅ (2, 2, 3, 5, 6)
```

**Bidding:**
```
User: "I bid three 2s"
Agent: Player 2 bids four 3s...
Player 3 calls "Liar!" on Player 2.

Revealing all dice...
[Shows all dice rolled by each player]
Total 3s on table: 2 dice
Player 2 bid four 3s but there were only 2. Player 2 loses a die!
```

### 🃏 War (Card Game)

**Battle:**
```
Agent: Time for War! Each player draws one card.
[Calls casino_deck_draw with count=1 for each player]

You: Q♦️ (image) - Queen of Diamonds
Opponent: 8♣️ (image) - Eight of Clubs

Queen beats 8 - You win this round!
```

**War Declaration:**
```
Agent: Both players drew Kings! It's WAR! 
[Calls casino_deck_draw with count=4 for each player - 3 face down, 1 face up]

Your war card: A♠️ (image) - Ace of Spades
Opponent's war card: 10♥️ (image) - Ten of Hearts

Ace beats 10 - You win the entire war pile!
```

## 🎨 Visual Features

### Card Images
Each card comes with both PNG and SVG images:
```json
{
  "value": "ACE",
  "suit": "SPADES", 
  "code": "AS",
  "image": "https://deckofcardsapi.com/static/img/AS.png",
  "svg_image": "https://deckofcardsapi.com/static/img/AS.svg"
}
```

### Dice Visualization
Dice results include emoji representation:
- ⚀ (1) ⚁ (2) ⚂ (3) ⚃ (4) ⚄ (5) ⚅ (6)

### Game State Persistence
- Deck state maintained between draws
- Remaining cards tracked automatically  
- Each agent has independent game sessions

## 🛡️ Built-in Features

### Rate Limiting
- **Deck Shuffle**: 20 requests/minute
- **Card Draw**: 30 requests/minute  
- **Dice Roll**: 15 requests/minute

### Error Handling
- Automatic deck creation if none exists
- Graceful API failure handling
- Input validation and sanitization

### Quantum Randomness
Dice rolling uses true quantum random number generation from QRandom.io for authentic unpredictability, complete with quantum signatures for verification.

## 🚀 Getting Started

1. Enable Casino skills in your agent configuration
2. Set skill states (public/private/disabled) for each function
3. Start gaming! The agent will automatically manage decks and game state

## 🎪 Advanced Gaming Scenarios

### Multi-Table Casino
```
Agent: Welcome to the Nation Casino! I'm managing 3 tables:
- Table 1: Blackjack (6-deck shoe)
- Table 2: Poker Tournament 
- Table 3: Craps with side bets

Which table interests you?
```

### Tournament Mode
```
Agent: Poker Tournament - Round 1 of 3
Blinds: 50/100 chips
[Manages multiple hands, tracks chip counts, advances rounds]
```

### Live Dealer Experience  
```
Agent: 🎭 Good evening! I'm your live dealer tonight.
[Maintains casino atmosphere, explains rules, manages multiple players]
```

The Casino skills transform your AI agent into a comprehensive gaming companion capable of hosting authentic casino experiences with visual cards, quantum dice, and persistent game management! 🎰🎲🃏
