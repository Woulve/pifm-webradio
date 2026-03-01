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
from urllib.parse import urlparse

CONFIG_PATH = "/etc/fm-radio/config"
SERVICE_NAME = "fm-radio"
PORT = 8080
LOG_LINES = 100

HTML_TEMPLATE = """<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Pi FM Radio</title>
    <style>
        * {{ box-sizing: border-box; }}
        body {{
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
            max-width: 500px;
            margin: 40px auto;
            padding: 20px;
            background: #1a1a2e;
            color: #eee;
        }}
        h1 {{ color: #00d4ff; margin-bottom: 5px; }}
        .subtitle {{ color: #888; margin-bottom: 30px; }}
        .status {{
            padding: 15px;
            border-radius: 8px;
            margin-bottom: 20px;
        }}
        .status.running {{ background: #1e4620; border: 1px solid #2e7d32; }}
        .status.stopped {{ background: #4a1e1e; border: 1px solid #c62828; }}
        .status.unknown {{ background: #3d3d00; border: 1px solid #888; }}
        form {{ background: #16213e; padding: 20px; border-radius: 8px; }}
        label {{ display: block; margin-bottom: 5px; color: #aaa; font-size: 14px; }}
        input[type="text"] {{
            width: 100%;
            padding: 10px;
            margin-bottom: 15px;
            border: 1px solid #333;
            border-radius: 4px;
            background: #0f0f23;
            color: #fff;
            font-size: 16px;
        }}
        input[type="text"]:focus {{ outline: none; border-color: #00d4ff; }}
        .hint {{ font-size: 12px; color: #666; margin-top: -10px; margin-bottom: 15px; }}
        .buttons {{ display: flex; gap: 10px; margin-top: 20px; flex-wrap: wrap; }}
        button {{
            padding: 12px 20px;
            border: none;
            border-radius: 4px;
            cursor: pointer;
            font-size: 14px;
            font-weight: 500;
        }}
        .btn-save {{ background: #00d4ff; color: #000; }}
        .btn-start {{ background: #2e7d32; color: #fff; }}
        .btn-stop {{ background: #c62828; color: #fff; }}
        .btn-restart {{ background: #f57c00; color: #fff; }}
        button:hover {{ opacity: 0.9; }}
        .message {{
            padding: 10px;
            border-radius: 4px;
            margin-bottom: 20px;
        }}
        .message.success {{ background: #1e4620; border: 1px solid #2e7d32; }}
        .message.error {{ background: #4a1e1e; border: 1px solid #c62828; }}
        .logs-section {{
            margin-top: 20px;
            background: #16213e;
            border-radius: 8px;
            overflow: hidden;
        }}
        .logs-header {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding: 15px 20px;
            background: #1a2744;
            border-bottom: 1px solid #333;
        }}
        .logs-header h3 {{
            margin: 0;
            color: #00d4ff;
            font-size: 16px;
        }}
        .btn-refresh {{
            background: #333;
            color: #fff;
            padding: 8px 15px;
            font-size: 12px;
        }}
        .logs-content {{
            padding: 15px;
            max-height: 400px;
            overflow-y: auto;
        }}
        .logs-content pre {{
            margin: 0;
            font-family: "Monaco", "Menlo", "Ubuntu Mono", monospace;
            font-size: 11px;
            line-height: 1.5;
            color: #ccc;
            white-space: pre-wrap;
            word-wrap: break-word;
        }}
        .logs-content::-webkit-scrollbar {{
            width: 8px;
        }}
        .logs-content::-webkit-scrollbar-track {{
            background: #0f0f23;
        }}
        .logs-content::-webkit-scrollbar-thumb {{
            background: #333;
            border-radius: 4px;
        }}
        .no-logs {{
            color: #666;
            font-style: italic;
        }}
        .validating {{
            opacity: 0.7;
            pointer-events: none;
        }}
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

    <div class="logs-section">
        <div class="logs-header">
            <h3>Service Logs</h3>
            <a href="/?refresh_logs=1"><button type="button" class="btn-refresh">Refresh Logs</button></a>
        </div>
        <div class="logs-content">
            <pre>{logs}</pre>
        </div>
    </div>
</body>
</html>
"""


def validate_stream_url(url):
    """Validate stream URL format and accessibility."""
    errors = []

    if not url:
        return False, ["Stream URL is required"]

    parsed = urlparse(url)
    if parsed.scheme not in ('http', 'https'):
        errors.append("URL must start with http:// or https://")
    if not parsed.netloc:
        errors.append("Invalid URL format")

    if errors:
        return False, errors

    try:
        result = subprocess.run(
            ["curl", "-s", "--head", "--max-time", "5", "-o", "/dev/null", "-w", "%{http_code}", url],
            capture_output=True, text=True, timeout=10
        )
        http_code = result.stdout.strip()
        if http_code in ('200', '301', '302', '303', '307', '308'):
            return True, []
        elif http_code == '000':
            errors.append(f"Cannot connect to stream (connection failed)")
        else:
            errors.append(f"Stream returned HTTP {http_code} (expected 200 or redirect)")
    except subprocess.TimeoutExpired:
        errors.append("Connection timed out (server not responding)")
    except Exception as e:
        errors.append(f"Connection test failed: {str(e)}")

    return False, errors


def validate_fm_frequency(freq_str):
    """Validate FM frequency is within valid range."""
    try:
        freq = float(freq_str)
        if freq < 87.5 or freq > 108.0:
            return False, "Frequency must be between 87.5 and 108.0 MHz"
        return True, None
    except ValueError:
        return False, "Frequency must be a valid number"


def validate_ps_name(name):
    """Validate RDS PS name."""
    if not name:
        return True, None 
    if len(name) > 8:
        return False, "Station name must be 8 characters or less"
    if not re.match(r'^[A-Za-z0-9 \-_.]+$', name):
        return False, "Station name can only contain letters, numbers, spaces, and -_."
    return True, None


def get_service_logs(lines=LOG_LINES):
    """Fetch recent service logs from journalctl."""
    try:
        result = subprocess.run(
            ["journalctl", "-u", SERVICE_NAME, "-n", str(lines), "--no-pager", "-o", "short-iso"],
            capture_output=True, text=True, timeout=5
        )
        if result.returncode == 0:
            return result.stdout or "No logs available"
        return f"Failed to fetch logs: {result.stderr}"
    except subprocess.TimeoutExpired:
        return "Timeout fetching logs"
    except Exception as e:
        return f"Error fetching logs: {str(e)}"


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
            stream_url = params.get('stream_url', [''])[0].strip()
            fm_freq = params.get('fm_freq', ['107.9'])[0].strip()
            ps_name = params.get('ps_name', ['PIRADIO'])[0].strip()[:8]
            rt_text = params.get('rt_text', ['Pi Radio'])[0].strip()

            validation_errors = []

            url_valid, url_errors = validate_stream_url(stream_url)
            if not url_valid:
                validation_errors.extend(url_errors)

            freq_valid, freq_error = validate_fm_frequency(fm_freq)
            if not freq_valid:
                validation_errors.append(freq_error)

            ps_valid, ps_error = validate_ps_name(ps_name)
            if not ps_valid:
                validation_errors.append(ps_error)

            if validation_errors:
                message = "Validation failed: " + "; ".join(validation_errors)
                message_type = "error"
            else:
                config = {
                    'stream_url': stream_url,
                    'fm_freq': fm_freq,
                    'ps_name': ps_name or 'PIRADIO',
                    'rt_text': rt_text or 'Pi Radio'
                }
                try:
                    write_config(config)
                    message = "Configuration saved successfully (stream URL verified)"
                    message_type = "success"
                except PermissionError:
                    message = f"Permission denied: Cannot write to {CONFIG_PATH}"
                    message_type = "error"
                except OSError as e:
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
        logs = get_service_logs()

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
            rt_text=html.escape(config['rt_text']),
            logs=html.escape(logs)
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
