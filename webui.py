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
import json
from urllib.parse import urlparse

CONFIG_PATH = "/etc/fm-radio/config"
PRESETS_PATH = "/etc/fm-radio/presets.json"
SERVICE_NAME = "fm-radio"
PORT = 8080
LOG_LINES = 100

SCRIPT_DIR = os.path.dirname(os.path.realpath(__file__))
TEMPLATES_DIR = os.path.join(SCRIPT_DIR, "templates")
STATIC_DIR = os.path.join(SCRIPT_DIR, "static")

MIME_TYPES = {
    '.css': 'text/css',
    '.js': 'application/javascript',
    '.html': 'text/html',
    '.png': 'image/png',
    '.jpg': 'image/jpeg',
    '.jpeg': 'image/jpeg',
    '.gif': 'image/gif',
    '.svg': 'image/svg+xml',
    '.ico': 'image/x-icon',
}


def load_template(name):
    """Load an HTML template from the templates directory."""
    template_path = os.path.join(TEMPLATES_DIR, name)
    with open(template_path, 'r', encoding='utf-8') as f:
        return f.read()


def validate_stream_url(url):
    """Validate stream URL format."""
    if not url:
        return False, "Stream URL is required"

    parsed = urlparse(url)
    if parsed.scheme not in ('http', 'https'):
        return False, "URL must start with http:// or https://"
    if not parsed.netloc:
        return False, "Invalid URL format"

    return True, None


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
            capture_output=True, text=True, timeout=10
        )
        status = result.stdout.strip()
        if status == "active":
            return "Running", "running"
        elif status == "inactive":
            return "Stopped", "stopped"
        else:
            return status.capitalize(), "unknown"
    except subprocess.TimeoutExpired:
        return "Timeout", "unknown"
    except OSError as e:
        return f"Error: {e}", "unknown"
    except Exception as e:
        print(f"[ERROR] get_service_status: {e}")
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
        with open(CONFIG_PATH, 'r', encoding='utf-8') as f:
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
    except PermissionError as e:
        print(f"[ERROR] read_config: Permission denied reading {CONFIG_PATH}: {e}")
    except OSError as e:
        print(f"[ERROR] read_config: OS error reading {CONFIG_PATH}: {e}")
    except UnicodeDecodeError as e:
        print(f"[ERROR] read_config: Invalid encoding in {CONFIG_PATH}: {e}")
    except Exception as e:
        print(f"[ERROR] read_config: Unexpected error: {e}")

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


def read_presets():
    """Read presets from JSON file."""
    if not os.path.exists(PRESETS_PATH):
        return []

    try:
        with open(PRESETS_PATH, 'r', encoding='utf-8') as f:
            data = json.load(f)
            return data.get('presets', [])
    except (json.JSONDecodeError, PermissionError, OSError) as e:
        print(f"[ERROR] read_presets: {e}")
        return []


def write_presets(presets):
    """Write presets to JSON file."""
    data = {'presets': presets}
    with open(PRESETS_PATH, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2)


def control_service(action):
    """Control the fm-radio service."""
    try:
        subprocess.run(
            ["systemctl", action, SERVICE_NAME],
            check=True, capture_output=True, timeout=30
        )
        return True, f"Service {action}ed successfully"
    except subprocess.CalledProcessError as e:
        stderr_msg = ""
        if e.stderr:
            try:
                stderr_msg = e.stderr.decode('utf-8', errors='replace')
            except Exception:
                stderr_msg = "unknown error"
        return False, f"Failed to {action} service: {stderr_msg or 'unknown error'}"
    except subprocess.TimeoutExpired:
        return False, f"Timeout while trying to {action} service"
    except OSError as e:
        return False, f"System error: {e}"


class RequestHandler(http.server.BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        print(f"[{self.address_string()}] {args[0]}")

    def do_GET(self):
        if self.path == '/logs':
            self.send_logs()
        elif self.path == '/presets':
            self.send_presets()
        elif self.path.startswith('/static/'):
            self.send_static_file()
        else:
            self.send_page()

    def send_static_file(self):
        """Serve static files (CSS, JS, images)."""
        relative_path = self.path[len('/static/'):]
        if '..' in relative_path or relative_path.startswith('/'):
            self.send_error(403, "Forbidden")
            return

        file_path = os.path.join(STATIC_DIR, relative_path)

        if not os.path.exists(file_path) or not os.path.isfile(file_path):
            self.send_error(404, "File not found")
            return

        _, ext = os.path.splitext(file_path)
        content_type = MIME_TYPES.get(ext.lower(), 'application/octet-stream')

        try:
            with open(file_path, 'rb') as f:
                content = f.read()
            self.send_response(200)
            self.send_header('Content-Type', content_type)
            self.send_header('Content-Length', str(len(content)))
            self.end_headers()
            self.wfile.write(content)
        except (PermissionError, OSError) as e:
            self.send_error(500, f"Error reading file: {e}")

    def send_presets(self):
        presets = read_presets()
        self.send_response(200)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.end_headers()
        self.wfile.write(json.dumps(presets).encode('utf-8'))

    def handle_add_preset(self):
        try:
            content_length = int(self.headers.get('Content-Length', '0'))
            post_data = self.rfile.read(content_length).decode('utf-8')
            preset = json.loads(post_data)

            if not preset.get('name') or not preset.get('url'):
                self.send_error(400, "Name and URL are required")
                return

            presets = read_presets()
            presets.append({
                'name': preset['name'][:50],
                'url': preset['url'],
                'ps_name': preset.get('ps_name', '')[:8],
                'rt_text': preset.get('rt_text', '')
            })
            write_presets(presets)

            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(b'{"success": true}')
        except (json.JSONDecodeError, ValueError) as e:
            self.send_error(400, f"Invalid request: {e}")
        except (PermissionError, OSError) as e:
            self.send_error(500, f"Failed to save preset: {e}")

    def send_logs(self):
        logs = get_service_logs()
        self.send_response(200)
        self.send_header('Content-Type', 'text/plain; charset=utf-8')
        self.end_headers()
        self.wfile.write(logs.encode('utf-8'))

    def do_DELETE(self):
        if self.path.startswith('/presets/'):
            try:
                index = int(self.path.split('/')[-1])
                presets = read_presets()
                if 0 <= index < len(presets):
                    presets.pop(index)
                    write_presets(presets)
                    self.send_response(200)
                    self.send_header('Content-Type', 'application/json')
                    self.end_headers()
                    self.wfile.write(b'{"success": true}')
                else:
                    self.send_error(404, "Preset not found")
            except (ValueError, PermissionError, OSError) as e:
                self.send_error(500, str(e))
        else:
            self.send_error(404, "Not found")

    def do_POST(self):
        if self.path == '/presets':
            self.handle_add_preset()
            return

        try:
            content_length_str = self.headers.get('Content-Length', '0')
            content_length = int(content_length_str)
        except (ValueError, TypeError):
            self.send_error(400, "Invalid Content-Length header")
            return

        if content_length > 1024 * 1024:  # 1MB limit
            self.send_error(413, "Request body too large")
            return

        try:
            post_data = self.rfile.read(content_length).decode('utf-8')
        except UnicodeDecodeError:
            self.send_error(400, "Invalid UTF-8 in request body")
            return
        except Exception as e:
            self.send_error(500, f"Error reading request: {e}")
            return

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

            url_valid, url_error = validate_stream_url(stream_url)
            if not url_valid:
                validation_errors.append(url_error)

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
                    message = "Configuration saved successfully"
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
        presets = read_presets()

        message_html = ""
        if message:
            message_html = f'<div class="message {message_type}">{html.escape(message)}</div>'

        if presets:
            presets_html = ""
            for i, preset in enumerate(presets):
                escaped_name = html.escape(preset.get('name', 'Unnamed'))
                presets_html += f'''<div class="preset-item" onclick="loadPreset({i})">
                    <span class="preset-name" title="{escaped_name}">{escaped_name}</span>
                    <button class="preset-delete" onclick="deletePreset({i}, event)">&times;</button>
                </div>'''
        else:
            presets_html = '<div class="no-presets">No presets saved</div>'

        try:
            template = load_template('index.html')
        except (FileNotFoundError, PermissionError, OSError) as e:
            self.send_error(500, f"Failed to load template: {e}")
            return

        page = template.format(
            message=message_html,
            status=status_text,
            status_class=status_class,
            stream_url=html.escape(config['stream_url']),
            fm_freq=html.escape(config['fm_freq']),
            ps_name=html.escape(config['ps_name']),
            rt_text=html.escape(config['rt_text']),
            logs=html.escape(logs),
            presets_html=presets_html,
            presets_json=json.dumps(presets)
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
