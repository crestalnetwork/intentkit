#!/bin/sh
# Generate Caddyfile with optional basic auth, then start Caddy.

GENERATED="/tmp/Caddyfile"

# Start building the Caddyfile
{
  echo "${APP_DOMAIN} {"
  echo "	tls ${TLS_EMAIL}"

  # Add basicauth block if credentials are provided
  if [ -n "$BASIC_AUTH_USER" ] && [ -n "$BASIC_AUTH_PASSWORD" ]; then
    HASH=$(caddy hash-password --plaintext "$BASIC_AUTH_PASSWORD")
    echo "	basicauth * {"
    # Use printf to avoid shell interpretation of $ in bcrypt hash
    printf '		%s %s\n' "$BASIC_AUTH_USER" "$HASH"
    echo "	}"
  fi

  cat <<'ROUTES'
	handle /api/* {
		reverse_proxy api:8000
	}
	handle /static/* {
		reverse_proxy rustfs:9000
	}
	handle {
		reverse_proxy frontend:3000
	}
}
ROUTES
} > "$GENERATED"

exec caddy run --config "$GENERATED" --adapter caddyfile
