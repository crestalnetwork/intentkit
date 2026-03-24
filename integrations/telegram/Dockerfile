# Build stage
FROM golang:1.26-alpine AS builder

WORKDIR /app

RUN apk add --no-cache git

# Copy shared types package first
COPY types/ /app/types/

# Copy telegram module
COPY telegram/go.mod telegram/go.sum /app/telegram/
WORKDIR /app/telegram
RUN go mod download

COPY telegram/ /app/telegram/

RUN CGO_ENABLED=0 GOOS=linux go build -ldflags="-w -s" -o intent-telegram .

# Run stage
FROM alpine:latest

ARG RELEASE=local
ENV RELEASE=${RELEASE}

WORKDIR /app

RUN apk --no-cache add ca-certificates tzdata

COPY --from=builder /app/telegram/intent-telegram .

ENV TG_NEW_AGENT_POLL_INTERVAL=10

CMD ["./intent-telegram"]
