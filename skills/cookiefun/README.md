# CookieFun Skills

This skill category provides access to CookieFun API for Twitter/X analytics and account insights.

### Features

The CookieFun skills allow you to:

- Get a list of all available sectors
- Get detailed information about Twitter accounts
- Get the feed of tweets from specific accounts
- Find smart followers for Twitter accounts
- Search for Twitter accounts matching specific criteria

### API Key

You need a CookieFun API key to use these skills. You can get one by signing up at [CookieFun](https://cookie.fun/).

### Skills

#### Get Sectors

Returns a list of all available sectors in the CookieFun system.

Example usage:
```
Call the get_sectors skill to fetch all sectors available in the CookieFun system.
```

Example prompts:
- "What sectors are available in CookieFun?"
- "Show me all the sectors in CookieFun"
- "Get a list of all sectors from CookieFun"

#### Get Account Details

Retrieves detailed information about a Twitter account including followers, following, posts, metrics, and engagement data.

Example usage:
```
Call the get_account_details skill with parameters:
- username: "elonmusk" 
```

or 

```
Call the get_account_details skill with parameters:
- userId: "1234567890"
```

Example prompts:
- "Get details about the Twitter account @elonmusk"
- "Fetch information about Elon Musk's Twitter profile"
- "Show me stats for the Twitter user elonmusk"
- "What's the engagement rate for @elonmusk?"

#### Get Account Smart Followers

Returns a list of top smart followers for a specific Twitter account, with detailed metrics about these followers.

Example usage:
```
Call the get_account_smart_followers skill with parameters:
- username: "elonmusk"
```

or

```
Call the get_account_smart_followers skill with parameters:
- userId: "1234567890"
```

Example prompts:
- "Who are the top smart followers of @elonmusk?"
- "Get me a list of the most influential followers of Elon Musk"
- "Show me the smart followers for Twitter user elonmusk"
- "Find the most engaged followers of @elonmusk"

#### Search Accounts

Searches for Twitter accounts that authored tweets matching specified search criteria.

Example usage:
```
Call the search_accounts skill with parameters:
- searchQuery: "bitcoin"
- type: 0  # Optional: 0 for Original, 1 for Reply, 2 for Quote
- sortBy: 0  # Optional: 0 for SmartEngagementPoints, 1 for Impressions, 2 for MatchingTweetsCount
- sortOrder: 1  # Optional: 0 for Ascending, 1 for Descending
```

Example prompts:
- "Find Twitter accounts talking about bitcoin"
- "Search for accounts that tweet about AI sorted by engagement"
- "Who are the top accounts posting original tweets about NFTs?"
- "Find Twitter users discussing climate change with the most impressions"

#### Get Account Feed

Retrieves a list of tweets for a specific Twitter account with various filtering options.

Example usage:
```
Call the get_account_feed skill with parameters:
- username: "elonmusk"
- startDate: "01/05/2023"  # Optional: Filter tweets after this date
- endDate: "31/05/2023"  # Optional: Filter tweets before this date
- type: 0  # Optional: 0 for Original, 1 for Reply, 2 for Quote
- hasMedia: true  # Optional: Filter to only tweets with media
- sortBy: 0  # Optional: 0 for CreatedDate, 1 for Impressions
- sortOrder: 1  # Optional: 0 for Ascending, 1 for Descending
```

Example prompts:
- "Show me Elon Musk's tweets from May 2023"
- "Get the most popular tweets from @elonmusk"
- "Fetch only original tweets (not replies) from elonmusk"
- "Show me tweets with media from @elonmusk posted in the last month"
- "What are the latest tweets from Elon Musk sorted by impressions?"
