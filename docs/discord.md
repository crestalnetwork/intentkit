# Discord Integration

Complete guide for Discord bot integration in IntentKit.

## Overview

Discord integration allows IntentKit agents to interact with users on Discord. Each agent can have its own Discord bot that responds to messages in servers and DMs.

**Architecture**: Follows the same pattern as Telegram with per-agent bot management, but uses WebSocket Gateway instead of HTTP webhooks.

## Quick Start

### 1. Create Discord Bot

1. Go to [Discord Developer Portal](https://discord.com/developers/applications)
2. Click **"New Application"** and give it a name
3. Go to **"Bot"** section in the left sidebar
4. Click **"Add Bot"** or **"Reset Token"** to get your bot token
5. **Critical**: Enable **"MESSAGE CONTENT INTENT"** under Privileged Gateway Intents
6. Copy the bot token (keep it secret!)

### 2. Configure Agent

**Important**: Discord bot tokens are stored per-agent in the database, not in environment variables.

#### Via API:
```bash
curl -X PATCH "http://localhost:8000/agents/YOUR_AGENT_ID" \
  -H "Content-Type: application/json" \
  -d '{
    "discord_entrypoint_enabled": true,
    "discord_config": {
      "token": "YOUR_DISCORD_BOT_TOKEN",
      "respond_to_mentions": true,
      "respond_to_replies": true,
      "respond_to_dm": true
    }
  }'
```

#### Via Export/Import:
```bash
# Export agent
cd scripts
sh export.sh YOUR_AGENT_ID

# Edit YOUR_AGENT_ID.yaml and add:
discord_entrypoint_enabled: true
discord_config:
  token: "YOUR_DISCORD_BOT_TOKEN"
  respond_to_mentions: true
  respond_to_replies: true
  respond_to_dm: true

# Import back
sh import.sh YOUR_AGENT_ID
```

### 3. Run Discord Service

```bash
# Using uv
uv run python -m app.discord

# Or with Docker
docker-compose up intent-discord
```

### 4. Invite Bot to Server

1. Go to Discord Developer Portal → OAuth2 → URL Generator
2. Select scope: **bot**
3. Select permissions:
   - Send Messages
   - Read Message History
   - Add Reactions (optional)
4. Copy the generated URL and open in browser
5. Select server and authorize

Or use this URL (replace CLIENT_ID):
```
https://discord.com/oauth2/authorize?client_id=YOUR_CLIENT_ID&permissions=68608&scope=bot
```

### 5. Test

- **DM the bot**: It will respond to every message
- **In server**: @mention the bot or reply to its messages

## Configuration

### Discord Config Structure

```json
{
  "token": "MTIzNDU2...",              // Required: Discord bot token
  "respond_to_mentions": true,         // Respond when @mentioned in servers
  "respond_to_replies": true,          // Respond when someone replies to bot
  "respond_to_dm": true,               // Respond to all DM messages
  "guild_whitelist": [123, 456],       // Optional: only respond in these servers
  "channel_whitelist": [789, 012],     // Optional: only respond in these channels
  "guild_memory_public": false,        // Share memory across guild or per-channel
  "greeting_server": "Hello!",         // Greeting message for servers
  "greeting_dm": "Hello!",             // Greeting message for DMs
  "owner_discord_id": "123456789"      // Agent owner's Discord user ID
}
```

### Environment Variables

```bash
# .env or example.env
DISCORD_NEW_AGENT_POLL_INTERVAL=30  # How often to sync agents (seconds)
```

## Behavior

### In Discord Servers (Groups)
- ✅ Responds when **@mentioned**
- ✅ Responds when someone **replies to bot's message**
- ✅ Shows typing indicator while processing
- ✅ Replies to the original message (shows reply arrow)
- ✅ Handles 2000 character limit (auto-splits long messages)
- ✅ Optional guild/channel whitelist
- ✅ Configurable memory (public or per-channel)

### In DMs
- ✅ Responds to **every message**
- ✅ No mention needed
- ✅ Per-user memory
- ✅ Shows typing indicator

### Common Features
- ✅ Owner detection (special user_id handling)
- ✅ Attachment support
- ✅ Error handling
- ✅ Automatic reconnection
- ✅ Dynamic config updates

## Architecture

### File Structure
```
app/
├── discord.py                    # Main runner
├── entrypoints/
│   └── discord.py               # Discord server entrypoint
└── services/
    └── discord/
        └── bot/
            ├── pool.py          # Bot pool management
            ├── handlers.py      # Message handlers
            └── types/
                ├── agent.py     # Agent metadata
                └── bot.py       # Bot instance
```

### How It Works

1. **Startup**: Discord service connects to database
2. **Agent Scheduler**: Polls database every 30 seconds for discord-enabled agents
3. **Bot Pool**: Creates Discord bot instance for each agent
4. **WebSocket Connection**: Each bot maintains persistent connection to Discord Gateway
5. **Message Handling**: Discord pushes events → handlers → execute_agent() → response
6. **Dynamic Updates**: Detects agent changes and updates bots automatically

### Comparison with Telegram

| Aspect | Telegram | Discord |
|--------|----------|---------|
| Transport | HTTP webhooks | WebSocket Gateway |
| Connection | Stateless | Stateful (persistent) |
| Token Storage | Database | Database |
| Bot Management | Per-agent | Per-agent |
| Message Flow | Telegram POSTs | Discord pushes |
| Resource Usage | Low | Higher (1 WS/bot) |

## Troubleshooting

### Bot doesn't respond to messages

**Check 1: Message Content Intent**
- Go to Developer Portal → Bot → Privileged Gateway Intents
- Ensure "MESSAGE CONTENT INTENT" is enabled
- Restart Discord service after enabling

**Check 2: Bot has permissions**
- Ensure bot has "Send Messages" permission in the channel
- Check channel permissions and role hierarchy

**Check 3: Bot is online**
- Check if bot shows as online in Discord
- Check IntentKit logs for errors

### Bot receives messages but content is empty

**Solution**: Enable "MESSAGE CONTENT INTENT" in Developer Portal
- This is a privileged intent that must be explicitly enabled
- Without it, `message.content` will be empty

### Bot doesn't respond in servers

**Check 1: Mention or Reply**
- By default, bot only responds to @mentions or replies in servers
- Try: `@YourBotName hello`

**Check 2: Whitelist**
- If `guild_whitelist` or `channel_whitelist` is set, bot only responds in those
- Remove whitelist or add your server/channel ID

### "Invalid Token" error

**Solution**: 
- Token may have been regenerated
- Get a new token from Developer Portal
- Update agent's `discord_config.token`
- Restart Discord service

### Bot goes offline randomly

**Check 1: Network issues**
- Discord Gateway requires stable connection
- Check network connectivity

**Check 2: Rate limiting**
- Discord has rate limits (50 requests/second per bot)
- Check logs for rate limit errors

**Check 3: Token invalidated**
- Token may have been reset in Developer Portal
- Generate new token and update config

### Multiple responses to one message

**Solution**: Multiple agents using the same bot token
- Each agent should have its own unique Discord bot
- Or disable Discord for duplicate agents:
```bash
curl -X PATCH "http://localhost:8000/agents/AGENT_ID" \
  -H "Content-Type: application/json" \
  -d '{"discord_entrypoint_enabled": false}'
```

## Production Deployment

### Docker Compose

```yaml
intent-discord:
  image: crestal/intentkit:latest
  depends_on:
    db:
      condition: service_healthy
  environment:
    - ENV=${ENV:-local}
    - DB_USERNAME=${POSTGRES_USER:-postgres}
    - DB_PASSWORD=${POSTGRES_PASSWORD:-postgres}
    - DB_HOST=db
    - DB_PORT=5432
    - DB_NAME=${POSTGRES_DB:-intentkit}
    - OPENAI_API_KEY=${OPENAI_API_KEY}
    - DISCORD_NEW_AGENT_POLL_INTERVAL=30
  command: python -m app.discord
```

### Resource Considerations

- **Memory**: ~10-20MB per bot
- **CPU**: Minimal when idle
- **Network**: 1 WebSocket connection per bot
- **Scaling**: For 100+ bots, consider horizontal scaling

### Monitoring

Check logs for:
- Bot connection status
- Message processing errors
- Rate limit warnings
- Reconnection events

```bash
# View logs
docker-compose logs -f intent-discord

# Or if running directly
uv run python -m app.discord
```

## Best Practices

### Security
- ✅ Never commit bot tokens to version control
- ✅ Use environment variables or secrets management for sensitive data
- ✅ Regenerate token if accidentally exposed
- ✅ Use `owner_discord_id` to restrict sensitive operations

### Performance
- ✅ Use whitelists to limit bot to specific servers/channels
- ✅ Set `guild_memory_public: false` for better memory isolation
- ✅ Monitor resource usage (one WebSocket per bot)

### User Experience
- ✅ Set clear greeting messages
- ✅ Use `respond_to_mentions: true` to avoid spam in busy servers
- ✅ Test in a private server first
- ✅ Set appropriate bot username and avatar in Discord Developer Portal

## Discord API Limits

Be aware of Discord's rate limits:
- **Global**: 50 requests per second per bot
- **Per-channel**: 5 messages per 5 seconds
- **Gateway**: 120 events per minute

IntentKit handles these automatically, but be aware when scaling.

## Additional Resources

- [Discord Developer Portal](https://discord.com/developers/applications)
- [Discord.py Documentation](https://discordpy.readthedocs.io/)
- [Discord API Documentation](https://discord.com/developers/docs)
- [Discord Gateway Intents](https://discord.com/developers/docs/topics/gateway#gateway-intents)

## Support

For issues or questions:
1. Check this guide's troubleshooting section
2. Verify all intents are enabled in Developer Portal
3. Check IntentKit logs: `python -m app.discord`
4. Ensure bot has proper permissions in Discord server
5. Test with a simple message in DMs first

## Database Schema

The following fields are added to support Discord:

**agents table:**
- `discord_entrypoint_enabled` (boolean) - Enable/disable Discord for agent
- `discord_config` (jsonb) - Discord bot configuration

**agent_data table:**
- `discord_id` (string) - Discord bot user ID
- `discord_username` (string) - Discord bot username
- `discord_name` (string) - Discord bot display name

These are automatically created via database migration on first run.
