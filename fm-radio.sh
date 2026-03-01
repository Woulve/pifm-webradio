#!/bin/bash

set -o pipefail

CONFIG_FILE="/etc/fm-radio/config"

# Retry configuration
MAX_RETRIES=0          # 0 = infinite retries
INITIAL_RETRY_DELAY=5  # seconds
MAX_RETRY_DELAY=60     # seconds (cap for exponential backoff)
CONNECT_TIMEOUT=10     # curl connection timeout
MAX_TIME=0             # 0 = no limit on stream duration

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1"
}

log_error() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] ERROR: $1" >&2
}

if [ ! -f "$CONFIG_FILE" ]; then
    log_error "Config file not found at $CONFIG_FILE"
    echo "Run the install script or copy config.example to $CONFIG_FILE"
    exit 1
fi

source "$CONFIG_FILE"

if [ -z "$STREAM_URL" ]; then
    log_error "STREAM_URL not set in config"
    exit 1
fi

FM_FREQ="${FM_FREQ:-107.9}"
PS_NAME="${PS_NAME:-PIRADIO}"
RT_TEXT="${RT_TEXT:-Pi Radio}"

if ! awk -v freq="$FM_FREQ" 'BEGIN { exit !(freq >= 87.5 && freq <= 108.0) }'; then
    log_error "FM_FREQ must be between 87.5 and 108.0 MHz (got: $FM_FREQ)"
    exit 1
fi

for cmd in curl sox /usr/local/bin/pi_fm_rds; do
    if ! command -v "$cmd" &> /dev/null && [ ! -x "$cmd" ]; then
        log_error "Required command not found: $cmd"
        exit 1
    fi
done

log "Starting broadcast on $FM_FREQ MHz..."
log "Stream: $STREAM_URL"

retry_count=0
retry_delay=$INITIAL_RETRY_DELAY

stream_audio() {
    local curl_opts="-sL --fail --connect-timeout $CONNECT_TIMEOUT"

    if [ "$MAX_TIME" -gt 0 ]; then
        curl_opts="$curl_opts --max-time $MAX_TIME"
    fi

    curl $curl_opts "$STREAM_URL" 2>&1 | \
        sox -t mp3 - -t wav -r 44100 -c 1 - 2>&1 | \
        /usr/local/bin/pi_fm_rds -freq "$FM_FREQ" -ps "$PS_NAME" -rt "$RT_TEXT" -audio -

    return $?
}

while true; do
    log "Connecting to stream..."

    if stream_audio; then
        log "Stream ended normally"
        retry_count=0
        retry_delay=$INITIAL_RETRY_DELAY
    else
        exit_code=$?
        log_error "Stream failed with exit code $exit_code"

        ((retry_count++))

        if [ "$MAX_RETRIES" -gt 0 ] && [ "$retry_count" -ge "$MAX_RETRIES" ]; then
            log_error "Max retries ($MAX_RETRIES) exceeded, giving up"
            exit 1
        fi

        log "Retry $retry_count: waiting ${retry_delay}s before reconnecting..."
        sleep "$retry_delay"

        retry_delay=$((retry_delay * 2))
        if [ "$retry_delay" -gt "$MAX_RETRY_DELAY" ]; then
            retry_delay=$MAX_RETRY_DELAY
        fi
    fi
done
