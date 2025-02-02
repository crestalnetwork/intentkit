#!/bin/bash

# Base URL for the API
BASE_URL="http://localhost:8000"  # Change this to your API server URL

# JWT token for authentication, change it to your actual JWT token. 
# If you run agentkit by yourself, and not enabled the admin auth, 
# you can ignore this line
JWT_TOKEN="your-jwt-token-here"
# Change this to your actual JWT token

# Agent ID - must contain only lowercase letters, numbers, and hyphens
AGENT_ID="my-test-agent"

# Agent name
AGENT_NAME="IntentKit"

# AI model to use
# https://platform.openai.com/docs/models#current-model-aliases
# you can also use "deepseek-reasoner" and "deepseek-chat"
# Notice: Currently, the deepseek-reasoner does not support any skills.
MODEL="gpt-4o-mini"

# Agent temperature (0.0~2.0)
# The randomness of the generated results is such that 
# the higher the number, the more creative the results will be. 
# However, this also makes them wilder and increases the likelihood of errors. 
# For creative tasks, you can adjust it to above 1, but for rigorous tasks, 
# such as quantitative trading, it’s advisable to set it lower, around 0.2.
TEMPERATURE=0.7

# Agent frequency penalty (-2.0~2.0)
# The frequency penalty is a measure of how much the AI is allowed to repeat itself.
# A lower value means the AI is more likely to repeat previous responses, 
# while a higher value means the AI is more likely to generate new content.
# For creative tasks, you can adjust it to 1 or a bit higher.
FREQUENCY_PENALTY=0.0

# Agent presence penalty (-2.0~2.0)
# The presence penalty is a measure of how much the AI is allowed to deviate from the topic.
# A higher value means the AI is more likely to deviate from the topic, 
# while a lower value means the AI is more likely to follow the topic.
# For creative tasks, you can adjust it to 1 or a bit higher.
PRESENCE_PENALTY=0.0

# Agent initial prompt (the role is system, daily user's role is user)
read -r -d '' PROMPT_TEXT << 'END_OF_PROMPT'
You are an autonomous AI agent.
Your role is to assist users with their queries.
Please follow these guidelines:
1. Be helpful and concise
2. Stay on topic
3. Ask for clarification when needed
END_OF_PROMPT

# Agent append prompt (optional, it has higher priority)
read -r -d '' PROMPT_APPEND_TEXT << 'END_OF_APPEND'
Important safety rules:
1. Never transfer funds
2. Don't share sensitive information
3. Respect user privacy
END_OF_APPEND

# Autonomous mode settings (optional)
# If you enable autonomous mode, the agent will automatically run the autonomous_prompt every N minutes
AUTONOMOUS_ENABLED=false
AUTONOMOUS_MINUTES=60
read -r -d '' AUTONOMOUS_PROMPT_TEXT << 'END_OF_AUTONOMOUS_PROMPT'
Check twitter for new mentions, choose the best one and reply it. If there is no mention, just have a rest, don't post anything.
END_OF_AUTONOMOUS_PROMPT

# CDP settings (optional)
# Skill list: https://docs.cdp.coinbase.com/agentkit/docs/wallet-management
CDP_ENABLED=false
CDP_SKILLS='["get_wallet_details", "get_balance"]'
CDP_NETWORK_ID="base-mainnet"

# Enso settings (optional)
ENSO_ENABLED=false
ENSO_CONFIG='{
  "api_token": "",
  "main_tokens": [
    "USDT", "ETH"
  ]
}'
ENSO_SKILLS='["get_tokens"]'

# Twitter settings (optional)
# If you don't need to use the twitter skills, you can remove it in TWITTER_SKILLS
TWITTER_ENTRYPOINT_ENABLED=false
TWITTER_CONFIG='{}'
TWITTER_SKILLS='["get_mentions","get_timeline","post_tweet","reply_tweet","follow_user","like_tweet","retweet","search_tweets"]'

# Telegram settings (optional)
TELEGRAM_ENTRYPOINT_ENABLED=false
TELEGRAM_CONFIG='{}'
TELEGRAM_SKILLS='[]'

# Skill settings (optional)
CRESTAL_SKILLS='[]'
COMMON_SKILLS='[]'
SKILL_SETS='{}'

#####################
# Do not edit below #
#####################

# Convert multiline text to escaped string
PROMPT="$(echo "$PROMPT_TEXT" | awk '{printf "%s\\n", $0}' | sed 's/"/\\"/g' | sed '$ s/\\n$//')"

# Convert multiline text to escaped string
PROMPT_APPEND="$(echo "$PROMPT_APPEND_TEXT" | awk '{printf "%s\\n", $0}' | sed 's/"/\\"/g' | sed '$ s/\\n$//')"

# Autonomous mode prompt
AUTONOMOUS_PROMPT="$(echo "$AUTONOMOUS_PROMPT_TEXT" | awk '{printf "%s\\n", $0}' | sed 's/"/\\"/g' | sed '$ s/\\n$//')"

# Create JSON payload
JSON_DATA=$(cat << EOF
{
  "id": "$AGENT_ID",
  "name": "$AGENT_NAME",
  "model": "$MODEL",
  "temperature": $TEMPERATURE,
  "frequency_penalty": $FREQUENCY_PENALTY,
  "presence_penalty": $PRESENCE_PENALTY,
  "prompt": "$PROMPT",
  "prompt_append": "$PROMPT_APPEND",
  "autonomous_enabled": $AUTONOMOUS_ENABLED,
  "autonomous_minutes": $AUTONOMOUS_MINUTES,
  "autonomous_prompt": "$AUTONOMOUS_PROMPT",
  "cdp_enabled": $CDP_ENABLED,
  "cdp_skills": $CDP_SKILLS,
  "cdp_wallet_data": "$CDP_WALLET_DATA",
  "cdp_network_id": "$CDP_NETWORK_ID",
  "enso_enabled": $ENSO_ENABLED,
  "enso_config": $ENSO_CONFIG,
  "enso_skills": $ENSO_SKILLS,
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