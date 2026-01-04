#!/bin/bash

# If you want to visit a remote server, modify it
BASE_URL="http://localhost:8000"

# Token is not required in local, if you set the ADMIN_AUTH_ENABLED and ADMIN_JWT_SECRET in a remote server, you put key here
TOKEN=""

print_usage() {
    echo "Usage: sh create.sh AGENT_ID"
    exit 1
}

# Check if correct number of arguments provided
if [ $# -ne 1 ]; then
    print_usage
fi

AGENT_ID="$1"
echo "Creating agent [${AGENT_ID}] ..."
# Using the provided create command with escaped JSON
HTTP_STATUS=$(curl -s -w "%{http_code}" \
    -X POST \
    -H "Authorization: Bearer ${TOKEN}" \
    -H "Content-Type: application/json" \
    -d "{\"id\":\"${AGENT_ID}\"}" \
    "${BASE_URL}/agents/v2" -o "${AGENT_ID}.response")

if [ $HTTP_STATUS -ge 400 ]; then
    echo "Create failed with HTTP status ${HTTP_STATUS}"
    cat "${AGENT_ID}.response"
    rm "${AGENT_ID}.response"
    exit 1
fi

rm "${AGENT_ID}.response"
echo "Create succeeded"
