# Build stage
FROM golang:1.23-alpine AS builder

WORKDIR /app

# Install git and build tools if necessary
RUN apk add --no-cache git

# Copy module files and download dependencies
COPY go.mod go.sum ./
RUN go mod download

# Copy source code
COPY . .

# Build the binary
# CGO_ENABLED=0 creates a statically linked binary
RUN CGO_ENABLED=0 GOOS=linux go build -ldflags="-w -s" -o intent-telegram .

# Run stage
FROM alpine:latest

WORKDIR /app

# Install ca-certificates for HTTPS requests (required for Telegram API and Core API)
RUN apk --no-cache add ca-certificates tzdata

# Copy the binary from the builder stage
COPY --from=builder /app/intent-telegram .

# Set default environment variables (can be overridden at runtime)
ENV TG_NEW_AGENT_POLL_INTERVAL=10

# Command to run the application
CMD ["./intent-telegram"]
