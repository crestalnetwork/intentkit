# X

IntentKit provides two ways to integrate with X: using it as an entrypoint for your agent, or incorporating X-specific skills into your agent's capabilities.

## X Skills

IntentKit provides a set of X-specific skills that can be added to your agent's toolkit. All skills are built on top of the `XBaseTool` base class which handles authentication and client initialization.

### Available Skills

The following X skills are available:

- **Follow User** (`follow_user`): Follow a specified X user
- **Get Mentions** (`get_mentions`): Retrieve mentions of the authenticated user
- **Get Timeline** (`get_timeline`): Fetch tweets from a user's timeline
- **Like Tweet** (`like_tweet`): Like a specific tweet
- **Post Tweet** (`post_tweet`): Post a new tweet
- **Reply Tweet** (`reply_tweet`): Reply to a specific tweet
- **Retweet** (`retweet`): Retweet a specific tweet
- **Search Tweets** (`search_tweets`): Search for tweets based on query

### Using X Skills

Add X skills to your agent:
Just configure the skills you need in your agent's config.
```python
agent.twitter_skills = ["get_mentions", "get_timeline", "post_tweet", "reply_tweet", "follow_user", "like_tweet", "retweet", "search_tweets"]
```

Before the first use, agent will request you to click the link to authorize the agent to access your twitter account.

If you want to use your own twitter developer account, you can set it as follows:
```python
agent.twitter_config = {
    "bearer_token": "your_bearer_token",
    "consumer_key": "your_consumer_key",
    "consumer_secret": "your_consumer_secret",
    "access_token": "your_access_token",
    "access_token_secret": "your_access_token_secret"
}
```

## X as an Entrypoint

Entrypoint is a type of conversational interface.

The X entrypoint allows your agent to automatically respond to X mentions. When enabled, the agent will monitor mentions every 15 minutes and respond to them all.

We suggest you only use twitter skills, not use it as an entrypoint.

### Configuration

1. Enable X Entrypoint for your agent:
```python
agent.twitter_enabled = True
```

2. Configure X credentials in your agent's config:
Get your X credentials from your [X developer portal](https://developer.x.com/en/portal/dashboard).
> Notice: Free accounts can only use post_tweet skill, if you want to use other skills, you need to upgrade your account.
```python
agent.twitter_config = {
    "bearer_token": "your_bearer_token",
    "consumer_key": "your_consumer_key",
    "consumer_secret": "your_consumer_secret",
    "access_token": "your_access_token",
    "access_token_secret": "your_access_token_secret"
}
```

3. Run the X entrypoint:
If you have use the docker-compose, it already run.
```bash
python -m app.entrypoints.twitter
```

### How it Works

The X entrypoint:
- Polls for new mentions every 15 minutes
- Uses both `since_id` and `start_time` for reliable mention tracking
- Maintains the last processed tweet ID in the agent's plugin data
- Automatically manages API rate limits and quotas
- Responds to mentions as threaded replies


## Rate Limits and Quotas

### X side

[Rate Limits](https://developer.x.com/en/docs/x-api/rate-limits)

### IntentKit
Only when use the OAuth2.0 authentication, intentkit has a built-in rate limit:

- post tweet: 20/day
- reply tweet: 20/day
- retweet: 5/15min
- follow: 5/15min
- like: 100/day
- get mentions: 1/4hr
- get timeline: 3/day
- search: 3/day

### Yourself
You can set the rate limit under the intentkit config in the future.
Not released yet.

## Best Practices

1. Error Handling
   - Always handle X API errors gracefully
   - Implement exponential backoff for rate limits
   - Log failed interactions for debugging

2. Content Guidelines
   - Keep responses within X's character limit
   - Handle thread creation for longer responses
   - Consider X's content policies

3. Security
   - Store X credentials securely
   - Use environment variables for sensitive data
   - Regularly rotate access tokens

## Example Use Cases

1. Social Media Manager Bot
   ```python
   from intentkit.models.agent import Agent
   
   # Create an agent with X skills
   agent = Agent(
       name="Social Media Manager",
       twitter_enabled=True,
       twitter_skills=["get_mentions", "post_tweet", "reply_tweet"],
       twitter_config={
           "bearer_token": "your_bearer_token",
           "consumer_key": "your_consumer_key",
           "consumer_secret": "your_consumer_secret",
           "access_token": "your_access_token",
           "access_token_secret": "your_access_token_secret"
       },
       prompt="You are a helpful social media manager. Monitor mentions and engage with users professionally."
   )
   ```

2. Content Aggregator with Timeline Analysis
   ```python
   # Create an agent that analyzes timeline content
   agent = Agent(
       name="Content Analyzer",
       twitter_enabled=True,
       twitter_skills=["get_timeline", "post_tweet"],
       twitter_config={...},  # X credentials
       prompt="""You are a content analyzer. Monitor the timeline for trending topics and provide insights.
       When you find interesting patterns, share them as tweets."""
   )
   ```

3. Interactive Support Assistant
   ```python
   # Create a support agent that handles user queries
   agent = Agent(
       name="Support Assistant",
       twitter_enabled=True,
       twitter_skills=["get_mentions", "reply_tweet"],
       twitter_config={...},  # X credentials
       prompt="""You are a support assistant. Monitor mentions for support queries.
       Respond helpfully and professionally to user questions.
       If you can't help, politely explain why and suggest alternatives."""
   )
   ```

Each example demonstrates:
- Proper agent configuration with X credentials
- Specific skill selection for the use case
- Custom prompts to guide agent behavior
- Integration with IntentKit's agent system

## Troubleshooting

Common issues and solutions:

1. Rate Limit Exceeded
   - Check your quota settings
   - Implement proper waiting periods
   - Use the built-in quota management

2. Authentication Errors
   - Verify credential configuration
   - Check token expiration
   - Ensure proper permission scopes

3. Missing Mentions
   - Verify `since_id` tracking
   - Check `start_time` configuration
   - Monitor the X entrypoint logs
