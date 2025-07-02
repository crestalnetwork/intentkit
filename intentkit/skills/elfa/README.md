# Elfa Skills - Social Media Intelligence

Integration with [Elfa AI API](https://api.elfa.ai) providing real-time social media data analysis and processing capabilities for crypto and stock market sentiment tracking.

## Setup

Add your Elfa API key to your environment:
```bash
ELFA_API_KEY=your_elfa_api_key_here
```

## Available Skills

### 1. Get Trending Tokens (`get_trending_tokens`)

Ranks the most discussed tokens based on smart mentions count for a given period, updated every 5 minutes.

**Example Prompts:**
```
"What are the trending crypto tokens in the last 24 hours?"
"Show me the most discussed tokens today with at least 10 mentions"
"Get trending tokens for the past week"
"Which tokens are gaining attention on social media?"
```

**Parameters:**
- `timeWindow`: "1h", "24h", "7d" (default: "24h")
- `minMentions`: Minimum mentions required (default: 5)

---

### 2. Get Top Mentions (`get_top_mentions`)

Queries tweets mentioning a specific stock/crypto ticker, ranked by view count for market sentiment analysis.

**Example Prompts:**
```
"Get the top mentions for Bitcoin in the last 24 hours"
"Show me the most viewed tweets about $ETH today"
"What are people saying about TSLA stock on Twitter?"
"Find viral tweets mentioning $SOL with account details"
```

**Parameters:**
- `ticker`: Stock/crypto symbol (e.g., "BTC", "$ETH", "AAPL")
- `timeWindow`: "24h", "7d" (default: "24h") 
- `includeAccountDetails`: Include account info (default: false)

---

### 3. Search Mentions (`search_mentions`)

Searches tweets mentioning up to 5 keywords. Can access 30 days of recent data (updated every 5 minutes) or 6 months of historical data.

**Example Prompts:**
```
"Search for tweets mentioning 'DeFi, NFT, blockchain'"
"Find recent mentions of 'AI, artificial intelligence, machine learning'"
"Search historical tweets about 'bitcoin, cryptocurrency' from last month"
"Look for discussions about 'climate change, renewable energy'"
```

**Parameters:**
- `keywords`: Up to 5 keywords (comma-separated, phrases accepted)
- `from_`: Start timestamp (default: 24 hours ago)
- `to`: End timestamp (default: yesterday)

---

### 4. Get Mentions (`get_mentions`)

Retrieves hourly-updated tweets from "smart accounts" (influential accounts) that have received at least 10 interactions.

**Example Prompts:**
```
"Get the latest mentions from smart accounts"
"Show me recent tweets from influential crypto accounts"
"What are the smart accounts talking about?"
"Get the latest buzz from verified influencers"
```

**Parameters:** None (uses default limits)

---

### 5. Get Smart Stats (`get_smart_stats`)

Retrieves key social media metrics for a specific username including engagement ratios and smart following count.

**Example Prompts:**
```
"Get smart stats for @elonmusk"
"Analyze the social metrics for username 'VitalikButerin'"
"Show me engagement stats for @cz_binance"
"What are the social media metrics for @jack?"
```

**Parameters:**
- `username`: Twitter username (with or without @)

