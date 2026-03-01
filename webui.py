#!/usr/bin/env python3
"""
Simple Web UI for Pi FM Radio
Allows configuration changes and service control via browser.
"""

import http.server
import subprocess
import urllib.parse
import os
import re
import html

CONFIG_PATH = "/etc/fm-radio/config"
SERVICE_NAME = "fm-radio"
PORT = 8080

HTML_TEMPLATE = """<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Pi FM Radio</title>
    <style>
        * { box-sizing: border-box; }
        body {
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
            max-width: 500px;
            margin: 40px auto;
            padding: 20px;
            background: #1a1a2e;
            color: #eee;
        }
        h1 { color: #00d4ff; margin-bottom: 5px; }
        .subtitle { color: #888; margin-bottom: 30px; }
        .status {
            padding: 15px;
            border-radius: 8px;
            margin-bottom: 20px;
        }
        .status.running { background: #1e4620; border: 1px solid #2e7d32; }
        .status.stopped { background: #4a1e1e; border: 1px solid #c62828; }
        .status.unknown { background: #3d3d00; border: 1px solid #888; }
        form { background: #16213e; padding: 20px; border-radius: 8px; }
        label { display: block; margin-bottom: 5px; color: #aaa; font-size: 14px; }
        input[type="text"] {
            width: 100%;
            padding: 10px;
            margin-bottom: 15px;
            border: 1px solid #333;
            border-radius: 4px;
            background: #0f0f23;
            color: #fff;
            font-size: 16px;
        }
        input[type="text"]:focus { outline: none; border-color: #00d4ff; }
        .hint { font-size: 12px; color: #666; margin-top: -10px; margin-bottom: 15px; }
        .buttons { display: flex; gap: 10px; margin-top: 20px; flex-wrap: wrap; }
        button {
            padding: 12px 20px;
            border: none;
            border-radius: 4px;
            cursor: pointer;
            font-size: 14px;
            font-weight: 500;
        }
        .btn-save { background: #00d4ff; color: #000; }
        .btn-start { background: #2e7d32; color: #fff; }
        .btn-stop { background: #c62828; color: #fff; }
        .btn-restart { background: #f57c00; color: #fff; }
        button:hover { opacity: 0.9; }
        .message {
            padding: 10px;
            border-radius: 4px;
            margin-bottom: 20px;
        }
        .message.success { background: #1e4620; border: 1px solid #2e7d32; }
        .message.error { background: #4a1e1e; border: 1px solid #c62828; }
    </style>
</head>
<body>
    <h1>Pi FM Radio</h1>
    <p class="subtitle">Web Control Panel</p>

    {message}

    <div class="status {status_class}">
        <strong>Status:</strong> {status}
    </div>

    <form method="POST">
        <label for="stream_url">Stream URL</label>
        <input type="text" id="stream_url" name="stream_url" value="{stream_url}" placeholder="https://...">

        <label for="fm_freq">FM Frequency (MHz)</label>
        <input type="text" id="fm_freq" name="fm_freq" value="{fm_freq}" placeholder="107.9">
        <p class="hint">Range: 87.5 - 108.0</p>

        <label for="ps_name">Station Name (RDS)</label>
        <input type="text" id="ps_name" name="ps_name" value="{ps_name}" maxlength="8" placeholder="PIRADIO">
        <p class="hint">Max 8 characters</p>

        <label for="rt_text">Radio Text (RDS)</label>
        <input type="text" id="rt_text" name="rt_text" value="{rt_text}" placeholder="Pi Radio">

        <div class="buttons">
            <button type="submit" name="action" value="save" class="btn-save">Save Config</button>
            <button type="submit" name="action" value="start" class="btn-start">Start</button>
            <button type="submit" name="action" value="stop" class="btn-stop">Stop</button>
            <button type="submit" name="action" value="restart" class="btn-restart">Restart</button>
        </div>
    </form>
</body>
</html>
"""


def get_service_status():
    """Get the current status of the fm-radio service."""
    try:
        result = subprocess.run(
            ["systemctl", "is-active", SERVICE_NAME],
            capture_output=True, text=True
        )
        status = result.stdout.strip()
        if status == "active":
            return "Running", "running"
        elif status == "inactive":
            return "Stopped", "stopped"
        else:
            return status.capitalize(), "unknown"
    except Exception:
        return "Unknown", "unknown"


def read_config():
    """Read current configuration values."""
    config = {
        "stream_url": "",
        "fm_freq": "107.9",
        "ps_name": "PIRADIO",
        "rt_text": "Pi Radio"
    }

    if not os.path.exists(CONFIG_PATH):
        return config

    try:
        with open(CONFIG_PATH, 'r') as f:
            content = f.read()

        patterns = {
            "stream_url": r'STREAM_URL="([^"]*)"',
            "fm_freq": r'FM_FREQ="([^"]*)"',
            "ps_name": r'PS_NAME="([^"]*)"',
            "rt_text": r'RT_TEXT="([^"]*)"'
        }

        for key, pattern in patterns.items():
            match = re.search(pattern, content)
            if match:
                config[key] = match.group(1)
    except Exception:
        pass

    return config


def write_config(config):
    """Write configuration to file."""
    content = f'''# FM Radio Configuration

# Web radio stream URL (required)
STREAM_URL="{config.get('stream_url', '')}"

# FM frequency to broadcast on (87.5 - 108.0 MHz)
FM_FREQ="{config.get('fm_freq', '107.9')}"

# Station name shown on RDS-capable radios (max 8 characters)
PS_NAME="{config.get('ps_name', 'PIRADIO')}"

# Radio text shown on RDS displays
RT_TEXT="{config.get('rt_text', 'Pi Radio')}"
'''
    with open(CONFIG_PATH, 'w') as f:
        f.write(content)


def control_service(action):
    """Control the fm-radio service."""
    try:
        subprocess.run(
            ["systemctl", action, SERVICE_NAME],
            check=True, capture_output=True
        )
        return True, f"Service {action}ed successfully"
    except subprocess.CalledProcessError as e:
        return False, f"Failed to {action} service: {e.stderr.decode() if e.stderr else 'unknown error'}"


class RequestHandler(http.server.BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        print(f"[{self.address_string()}] {args[0]}")

    def do_GET(self):
        self.send_page()

    def do_POST(self):
        content_length = int(self.headers.get('Content-Length', 0))
        post_data = self.rfile.read(content_length).decode('utf-8')
        params = urllib.parse.parse_qs(post_data)

        message = ""
        message_type = ""

        action = params.get('action', [''])[0]

        if action == 'save':
            config = {
                'stream_url': params.get('stream_url', [''])[0],
                'fm_freq': params.get('fm_freq', ['107.9'])[0],
                'ps_name': params.get('ps_name', ['PIRADIO'])[0][:8],
                'rt_text': params.get('rt_text', ['Pi Radio'])[0]
            }
            try:
                write_config(config)
                message = "Configuration saved successfully"
                message_type = "success"
            except Exception as e:
                message = f"Failed to save config: {e}"
                message_type = "error"

        elif action in ['start', 'stop', 'restart']:
            success, msg = control_service(action)
            message = msg
            message_type = "success" if success else "error"

        self.send_page(message, message_type)

    def send_page(self, message="", message_type=""):
        config = read_config()
        status_text, status_class = get_service_status()

        message_html = ""
        if message:
            message_html = f'<div class="message {message_type}">{html.escape(message)}</div>'

        page = HTML_TEMPLATE.format(
            message=message_html,
            status=status_text,
            status_class=status_class,
            stream_url=html.escape(config['stream_url']),
            fm_freq=html.escape(config['fm_freq']),
            ps_name=html.escape(config['ps_name']),
            rt_text=html.escape(config['rt_text'])
        )

        self.send_response(200)
        self.send_header('Content-Type', 'text/html; charset=utf-8')
        self.end_headers()
        self.wfile.write(page.encode('utf-8'))


def main():
    server = http.server.HTTPServer(('0.0.0.0', PORT), RequestHandler)
    print(f"Pi FM Radio Web UI running on http://0.0.0.0:{PORT}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down...")
        server.shutdown()


if __name__ == '__main__':
    main()
