# Elfa Skills - Social Media Intelligence

Integration with [Elfa AI API v2](https://api.elfa.ai/v2) providing real-time social media data analysis and processing capabilities for crypto and stock market sentiment tracking.

**Important: V2 API Changes**
- **No Raw Content**: V2 API removes raw tweet content for platform compliance
- **Sanitized Data**: Returns engagement metrics, timestamps, and account metadata only
- **New Endpoints**: Updated endpoints with consistent response format
- **Enhanced Pagination**: Different pagination patterns for search vs aggregation endpoints

## Setup

Add your Elfa API key to your environment:
```bash
ELFA_API_KEY=your_elfa_api_key_here
```

## Available Skills

### 1. Get Trending Tokens (`get_trending_tokens`)

Ranks the most discussed tokens based on smart mentions count for a given period, updated every 5 minutes.

**Endpoint**: `v2/aggregations/trending-tokens` - Direct Migration

**Example Prompts:**
```
"What are the trending crypto tokens in the last 24 hours?"
"Get trending tokens with minimum 50 mentions in the past week"
```

**Parameters:**
- `timeWindow`: "30m", "1h", "4h", "24h", "7d", "30d" (default: "7d")
- `page`: Page number for pagination (default: 1)
- `pageSize`: Number of items per page (default: 50)
- `minMentions`: Minimum mentions required (default: 5)

**V2 Changes:**
- Same functionality and parameters
- Enhanced response format with metadata
- Uses page+pageSize pagination for aggregations

---

### 2. Get Top Mentions (`get_top_mentions`)

Queries tweets mentioning a specific stock/crypto ticker, ranked by view count for market sentiment analysis.

**Endpoint**: `v2/data/top-mentions` - Breaking Changes

**Example Prompts:**
```
"Get the top mentions for Bitcoin in the last 24 hours"
"Show me engagement metrics for tweets about $ETH today"
```

**Parameters:**
- `ticker`: Stock/crypto symbol (e.g., "BTC", "$ETH", "AAPL") - required
- `timeWindow`: "1h", "24h", "7d" (default: "1h")
- `page`: Page number for pagination (default: 1)
- `pageSize`: Number of items per page (default: 10)

**V2 Changes:**
- **Removed**: Raw tweet content/text
- **Removed**: `includeAccountDetails` parameter (always included)
- **Preserved**: Engagement metrics (view_count, like_count, etc.)
- **Preserved**: Account information and verification status
- **Enhanced**: Account tags (e.g., "smart" accounts)

---

### 3. Search Mentions (`search_mentions`)

Searches tweets mentioning up to 5 keywords or from specific accounts with sanitized engagement data.

**Endpoint**: `v2/data/keyword-mentions` - Breaking Changes

**Example Prompts:**
```
"Search for engagement metrics of tweets mentioning 'DeFi, NFT, blockchain'"
"Find tweets from account 'elonmusk' about cryptocurrency"
```

**Parameters:**
- `keywords`: Up to 5 keywords (comma-separated, phrases accepted) - optional if accountName provided
- `accountName`: Account username to filter by - optional if keywords provided  
- `timeWindow`: Time window for search (default: "7d")
- `limit`: Number of results to return, max 30 (default: 20)
- `searchType`: Type of search - "and" or "or" (default: "or")
- `cursor`: Cursor for pagination (optional)

**V2 Changes:**
- **Removed**: Raw tweet content/text
- **Preserved**: Engagement metrics and sentiment analysis
- **Enhanced**: Account filtering with `accountName` parameter
- **Updated**: Uses limit+cursor pagination for search
- **Added**: Account tags and metadata

---

### 4. Get Smart Stats (`get_smart_stats`)

Retrieves key social media metrics for a specific username including engagement ratios and smart following count.

**Endpoint**: `v2/account/smart-stats` - Direct Migration

**Example Prompts:**
```
"Get smart stats for @elonmusk"
"Analyze the social metrics for username 'VitalikButerin'"
```

**Parameters:**
- `username`: Twitter username (with or without @) - required

**V2 Changes:**
- Same functionality and parameters
- Consistent response format with metadata

## V2 Response Format

All V2 endpoints return a consistent format:

```json
{
  "success": boolean,
  "data": [...], // Array or object with actual data
  "metadata": {  // Pagination and additional info
    "total": number,
    "page": number,
    "pageSize": number,
    "cursor": "string" // For search endpoints
  }
}
```

## Migration Notes

### What's Removed in V2:
- Raw tweet content/text (compliance requirement)
- Direct access to tweet body/message content
- `includeAccountDetails` parameter (always included)
- **Deprecated**: `get_mentions` skill (no v2 equivalent)

### What's Preserved:
- Engagement metrics (likes, views, reposts, replies)
- Account information and verification status
- Timestamps and metadata
- Sentiment analysis
- Core functionality for trend analysis


