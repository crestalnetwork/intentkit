# Build stage
FROM golang:1.26-alpine AS builder

WORKDIR /app

RUN apk add --no-cache git

# Copy shared types package first
COPY types/ /app/types/

# Copy wechat module
COPY wechat/go.mod wechat/go.sum /app/wechat/
WORKDIR /app/wechat
RUN go mod download

COPY wechat/ /app/wechat/

RUN CGO_ENABLED=0 GOOS=linux go build -ldflags="-w -s" -o intent-wechat .

# Run stage
FROM alpine:latest

ARG RELEASE=local
ENV RELEASE=${RELEASE}

WORKDIR /app

RUN apk --no-cache add ca-certificates tzdata

COPY --from=builder /app/wechat/intent-wechat .

ENV WX_NEW_CHANNEL_POLL_INTERVAL=10

CMD ["./intent-wechat"]
