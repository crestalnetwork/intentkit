#!/bin/bash

# Base URL for the API
BASE_URL="http://localhost:8000"  # Change this to your API server URL

# JWT token for authentication, if you run agentkit by yourself, and not
# enabled the admin auth, you can ignore this
JWT_TOKEN="your-jwt-token-here"  # Change this to your actual JWT token

# Agent ID - must contain only lowercase letters, numbers, and hyphens
AGENT_ID="my-test-agent"

# Agent name
AGENT_NAME="IntentKit"

# AI model to use
# https://platform.openai.com/docs/models#current-model-aliases
MODEL="gpt-4o-mini"

# Agent initial prompt (the role is system, daily user's role is user)
read -r -d '' PROMPT << END_OF_PROMPT
You are an autonomous AI agent. Respond to user queries.
END_OF_PROMPT

# Agent append prompt (optional, it has higher priority)
read -r -d '' PROMPT_APPEND << END_OF_PROMPT_APPEND
Remember, don't transfer funds to others.
END_OF_PROMPT_APPEND

# Autonomous mode settings (optional)
# If you enable autonomous mode, the agent will automatically run the autonomous_prompt every N minutes
AUTONOMOUS_ENABLED=false
AUTONOMOUS_MINUTES=60
AUTONOMOUS_PROMPT="Autonomous mode prompt"

# CDP settings (optional)
# Skill list: https://docs.cdp.coinbase.com/agentkit/docs/wallet-management
CDP_ENABLED=false
CDP_SKILLS='["get_wallet_details", "get_balance"]'
CDP_NETWORK_ID="base-sepolia"

# Twitter settings (optional)
TWITTER_ENTRYPOINT_ENABLED=false
TWITTER_CONFIG='{
  "consumer_key": "",
  "consumer_secret": "",
  "access_token": "",
  "access_token_secret": "",
  "bearer_token": ""
}'
TWITTER_SKILLS='["get_mentions","get_timeline","post_tweet","reply_tweet"]'

# Telegram settings (optional)
TELEGRAM_ENTRYPOINT_ENABLED=false
TELEGRAM_CONFIG='{}'
TELEGRAM_SKILLS='[]'

# Skill settings (optional)
CRESTAL_SKILLS='[]'
COMMON_SKILLS='[]'
SKILL_SETS='{}'

# Create JSON payload
JSON_DATA=$(cat << EOF
{
  "id": "$AGENT_ID",
  "name": "$AGENT_NAME",
  "model": "$MODEL",
  "prompt": "$PROMPT",
  "prompt_append": "$PROMPT_APPEND",
  "autonomous_enabled": $AUTONOMOUS_ENABLED,
  "autonomous_minutes": $AUTONOMOUS_MINUTES,
  "autonomous_prompt": "$AUTONOMOUS_PROMPT",
  "cdp_enabled": $CDP_ENABLED,
  "cdp_skills": $CDP_SKILLS,
  "cdp_wallet_data": "$CDP_WALLET_DATA",
  "cdp_network_id": "$CDP_NETWORK_ID",
  "twitter_enabled": $TWITTER_ENTRYPOINT_ENABLED,
  "twitter_entrypoint_enabled": $TWITTER_ENTRYPOINT_ENABLED,
  "twitter_config": $TWITTER_CONFIG,
  "twitter_skills": $TWITTER_SKILLS,
  "telegram_enabled": $TELEGRAM_ENTRYPOINT_ENABLED,
  "telegram_entrypoint_enabled": $TELEGRAM_ENTRYPOINT_ENABLED,
  "telegram_config": $TELEGRAM_CONFIG,
  "telegram_skills": $TELEGRAM_SKILLS,
  "crestal_skills": $CRESTAL_SKILLS,
  "common_skills": $COMMON_SKILLS,
  "skill_sets": $SKILL_SETS
}
EOF
)

# Make the API call
curl -X POST "$BASE_URL/agents" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $JWT_TOKEN" \
  -d "$JSON_DATA"