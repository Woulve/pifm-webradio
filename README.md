# Pi FM Radio

Turn your Raspberry Pi into an FM radio transmitter that streams internet radio.

## Hardware Requirements

- Raspberry Pi (tested on Pi Zero 2W)
- A wire (~20cm) connected to **GPIO 4** as antenna

## Quick Install

```bash
git clone https://github.com/woulve/pifmwebradio.git
cd pifm-webradio
sudo ./install.sh
```

## Configuration

Edit `/etc/fm-radio/config` to customize:

```bash
sudo nano /etc/fm-radio/config
```

| Setting | Description | Default |
|---------|-------------|---------|
| `STREAM_URL` | URL to your web radio stream | (required) |
| `FM_FREQ` | FM frequency (87.5-108.0 MHz) | 107.9 |
| `PS_NAME` | Station name for RDS (max 8 chars) | PIRADIO |
| `RT_TEXT` | Radio text for RDS displays | Pi Radio |

## Usage

```bash
# Start the radio
sudo systemctl start fm-radio

# Stop the radio
sudo systemctl stop fm-radio

# Check status
sudo systemctl status fm-radio

# View logs
sudo journalctl -u fm-radio -f
```

## Web UI (Optional)

A simple web interface is included but disabled by default.

Enable during installation:

```bash
sudo ./install.sh --webui
```

Or enable after installation:

```bash
sudo systemctl enable --now fm-radio-webui
```

Then visit `http://<pi-ip>:8080` to:
- Change stream URL, FM frequency, station name, and radio text
- Start, stop, or restart the radio service

To disable the web UI:

```bash
sudo systemctl disable --now fm-radio-webui
```

## Legal Notice

FM transmission is regulated in most countries. Ensure you comply with local radio transmission laws.

## Credits

Uses [PiFmRds](https://github.com/ChristopheJacquet/PiFmRds) by Christophe Jacquet.

## License

MIT
