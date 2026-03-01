#!/bin/bash

CONFIG_FILE="/etc/fm-radio/config"

if [ ! -f "$CONFIG_FILE" ]; then
    echo "Error: Config file not found at $CONFIG_FILE"
    echo "Run the install script or copy config.example to $CONFIG_FILE"
    exit 1
fi

source "$CONFIG_FILE"

if [ -z "$STREAM_URL" ]; then
    echo "Error: STREAM_URL not set in config"
    exit 1
fi

FM_FREQ="${FM_FREQ:-107.9}"
PS_NAME="${PS_NAME:-PIRADIO}"
RT_TEXT="${RT_TEXT:-Pi Radio}"

curl -s "$STREAM_URL" | \
sox -t mp3 - -t wav -r 44100 -c 1 - | \
/usr/local/bin/pi_fm_rds -freq "$FM_FREQ" -ps "$PS_NAME" -rt "$RT_TEXT" -audio -
