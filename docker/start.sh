#!/bin/bash

set -euo pipefail

HOST=${HOST:-0.0.0.0}
PORT=${PORT:-8000}
WORKERS=${WORKERS:-1}
LOG_LEVEL=${LOG_LEVEL:-info}
MAX_FILE_SIZE_MB=${MAX_FILE_SIZE_MB:-50}

setup_logging() {
    mkdir -p /app/logs
    echo "$(date '+%Y-%m-%d %H:%M:%S') - Starting Poe Wrapper" >> /app/logs/startup.log
}

validate_required_env() {
    [ -n "${POE_API_KEY:-}" ] || {
        echo "ERROR: POE_API_KEY environment variable is required"
        echo "Please set your Poe API key from https://poe.com/api_key"
        exit 1
    }
    
    [ -n "${LOCAL_API_KEY:-}" ] || {
        echo "Error: LOCAL_API_KEY not set. Please set it in the .env file or run setup.sh"
        exit 1
    }
}

validate_numeric_config() {
    [[ "$WORKERS" =~ ^[0-9]+$ ]] && [ "$WORKERS" -ge 1 ] || {
        echo "WARNING: Invalid WORKERS value, using default: 1"
        WORKERS=1
    }
    
    [[ "$MAX_FILE_SIZE_MB" =~ ^[0-9]+$ ]] && [ "$MAX_FILE_SIZE_MB" -ge 1 ] || {
        echo "WARNING: Invalid MAX_FILE_SIZE_MB value, using default: 50"
        MAX_FILE_SIZE_MB=50
    }
}

cleanup_port() {
    command -v lsof >/dev/null 2>&1 || return 0
    
    local pids
    pids=$(lsof -ti:$PORT 2>/dev/null || true)
    [ -n "$pids" ] || return 0
    
    echo "Killing processes on port $PORT: $pids"
    kill $pids 2>/dev/null || true
    sleep 2
    
    local remaining_pids
    remaining_pids=$(lsof -ti:$PORT 2>/dev/null || true)
    [ -n "$remaining_pids" ] && kill -9 $remaining_pids 2>/dev/null || true
}

print_startup_banner() {
    cat << EOF
=====================================
  Poe Wrapper v0.0.1
=====================================
Host: $HOST
Port: $PORT
Workers: $WORKERS
Log Level: $LOG_LEVEL
Max File Size: ${MAX_FILE_SIZE_MB}MB
POE_API_KEY: ${POE_API_KEY:0:10}...
LOCAL_API_KEY: ${LOCAL_API_KEY:0:10}...
=====================================
EOF
}

setup_signal_handlers() {
    trap 'handle_shutdown' SIGTERM SIGINT
}

handle_shutdown() {
    echo "Received shutdown signal, gracefully stopping..."
    [ -n "${UVICORN_PID:-}" ] && kill -TERM "$UVICORN_PID" 2>/dev/null || true
    wait "${UVICORN_PID:-}" 2>/dev/null || true
    echo "Server stopped gracefully"
    exit 0
}

start_server() {
    uvicorn app.main:app \
        --host "$HOST" \
        --port "$PORT" \
        --workers "$WORKERS" \
        --log-level "$LOG_LEVEL" \
        --access-log \
        --use-colors \
        --loop uvloop \
        --http httptools &
    
    UVICORN_PID=$!
    wait "$UVICORN_PID"
}

main() {
    setup_logging
    validate_required_env
    validate_numeric_config
    cleanup_port
    print_startup_banner
    setup_signal_handlers
    start_server
}

[ "${BASH_SOURCE[0]}" = "${0}" ] && main "$@"