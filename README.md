# DIY Smart Sprinkler

A Raspberry Pi + Home Assistant DIY irrigation controller using GPIO-controlled relay outputs, a local Flask API, and Home Assistant automations/dashboard controls.

This project turns a Raspberry Pi 2 running Raspberry Pi OS Bookworm into a local sprinkler controller for a 6-zone irrigation system using a SainSmart 16-channel 12V relay board.

## Features

- Raspberry Pi GPIO control
- 6 sprinkler zones
- Local Flask API
- Home Assistant integration using `rest_command`
- Home Assistant dashboard card
- Manual zone control
- Run-all-zones script
- Emergency all-off command
- Rain skip toggle
- Weather-adjusted runtime support
- Last run / next run display
- Per-zone runtime display
- Safety logic: only one zone is enabled at a time

## Hardware Used

This build was tested with:

- Raspberry Pi 2 Model B
- Raspberry Pi OS Bookworm
- [SainSmart 16-Channel 12V Relay Module](https://www.sainsmart.com/products/16-channel-12v-relay-module)
- Existing 24VAC sprinkler transformer
- Existing sprinkler valves / solenoids
- Home Assistant

Notes:

- The relay board is powered separately from the Raspberry Pi.
- The Raspberry Pi controls only the relay input pins.
- The sprinkler valves are switched through the relay contacts using the existing 24VAC sprinkler transformer.
- This setup uses 6 of the 16 available relay channels.

## GPIO Mapping

| Zone | BCM GPIO | Raspberry Pi Physical Pin |
|---|---:|---:|
| Zone 1 | GPIO4 | Pin 7 |
| Zone 2 | GPIO17 | Pin 11 |
| Zone 3 | GPIO27 | Pin 13 |
| Zone 4 | GPIO22 | Pin 15 |
| Zone 5 | GPIO23 | Pin 16 |
| Zone 6 | GPIO24 | Pin 18 |

## Relay Behavior

This relay board is controlled using an open-drain style pattern:

| Action | GPIO Behavior |
|---|---|
| Zone ON | Drive GPIO LOW |
| Zone OFF | Release GPIO as input |

The Python API uses `lgpio` directly so that OFF releases the GPIO instead of driving it HIGH.

## Install Path Assumption

This guide assumes the Raspberry Pi app is installed at:

```text
/root/sprinkler
```

The included `sprinkler.service` file uses that path.

Advanced users may prefer installing to:

```text
/opt/sprinkler
```

and using `network-online.target` instead of `network.target` in the systemd service.

## Raspberry Pi Setup

Install required packages:

```bash
sudo apt update
sudo apt install -y python3-flask python3-lgpio
```

Create the app directory:

```bash
sudo mkdir -p /root/sprinkler
```

Copy the API server:

```bash
sudo cp raspberry-pi/server.py /root/sprinkler/server.py
```

Copy the systemd service:

```bash
sudo cp raspberry-pi/sprinkler.service /etc/systemd/system/sprinkler.service
```

Enable and start the service:

```bash
sudo systemctl daemon-reload
sudo systemctl enable sprinkler
sudo systemctl start sprinkler
sudo systemctl status sprinkler
```

## API Endpoints

The Flask API listens on port `5050`.

Replace `<PI_IP_ADDRESS>` with the Raspberry Pi IP address.

### Get API info

```bash
curl http://<PI_IP_ADDRESS>:5050/
```

### Get zone state

```bash
curl http://<PI_IP_ADDRESS>:5050/zone/1
```

### Turn a zone on

```bash
curl -X POST http://<PI_IP_ADDRESS>:5050/zone/1 -d "on"
```

### Turn a zone off

```bash
curl -X POST http://<PI_IP_ADDRESS>:5050/zone/1 -d "off"
```

### Emergency all off

```bash
curl -X POST http://<PI_IP_ADDRESS>:5050/alloff
```

## Home Assistant Setup

Sample Home Assistant YAML files are in:

```text
home-assistant/
```

At minimum, you will need:

- `rest_command.yaml`
- `scripts.yaml`
- `automations.yaml`
- `sensors.yaml`
- `template.yaml`
- `input_boolean.yaml`
- `input_datetime.yaml`
- `dashboard.yaml`

Make sure your `configuration.yaml` includes the relevant split files, for example:

```yaml
rest_command: !include rest_command.yaml
script: !include scripts.yaml
sensor: !include sensors.yaml
template: !include template.yaml
input_boolean: !include input_boolean.yaml
input_datetime: !include input_datetime.yaml
```

If you already use split files, merge the examples into your existing files.

## Home Assistant Commands

The project uses `rest_command` instead of REST switches.

This avoids Home Assistant accidentally sending OFF commands during state refresh.

Example:

```yaml
sprinkler_zone_1_on:
  url: "http://<PI_IP_ADDRESS>:5050/zone/1"
  method: POST
  payload: "on"

sprinkler_zone_1_off:
  url: "http://<PI_IP_ADDRESS>:5050/zone/1"
  method: POST
  payload: "off"

sprinkler_all_off:
  url: "http://<PI_IP_ADDRESS>:5050/alloff"
  method: POST
```

## Dashboard

The included dashboard YAML uses:

- Bubble Card
- Button Card

Install these through HACS before using the dashboard:

- `custom:bubble-card`
- `custom:button-card`

The dashboard supports:

- Hero image
- Active zone status
- Last run
- Next run
- Rain skip
- Adjusted runtime
- Zone controls
- Runtime per zone
- Emergency all off

## Wiring Overview

Sprinkler relay contact wiring per zone:

```text
24VAC HOT  -> Relay COM
Relay NO   -> Zone wire
24VAC COMMON stays connected to all valves
```

Do not switch the valve common wire.

Do not connect Raspberry Pi GPIO to 24VAC.

See:

```text
docs/wiring.md
```

for more wiring detail.

## Safety Notes

- This project switches sprinkler valve control wiring.
- The Raspberry Pi should never be connected directly to sprinkler 24VAC.
- Use relay isolation.
- Keep the Raspberry Pi and relay board dry.
- Only one zone is enabled at a time by the API.
- Use the emergency all-off command if anything behaves unexpectedly.
- This project has no authentication by default.
- Run it only on a trusted local network.
- If you are not comfortable, hire a licensed electrician and plumber/landscaper for help.

## Troubleshooting

### The relay clicks once but does not toggle

The board may require open-drain style control.

This project handles that by:

- ON: GPIO output LOW
- OFF: GPIO input / released

### Zone turns off after a short time

If curl testing works but Home Assistant turns the zone off, avoid REST switches and use `rest_command`.

### API does not start after reboot

Check:

```bash
sudo systemctl status sprinkler
sudo journalctl -u sprinkler -f
```

### Test the API locally on the Pi

```bash
curl http://localhost:5050/
```

### Test the API from another machine

```bash
curl http://<PI_IP_ADDRESS>:5050/
```

## Project Structure

```text
diy-smart-sprinkler/
├── README.md
├── LICENSE
├── raspberry-pi/
│   ├── server.py
│   ├── sprinkler.service
│   └── requirements.txt
├── home-assistant/
│   ├── rest_command.yaml
│   ├── scripts.yaml
│   ├── automations.yaml
│   ├── sensors.yaml
│   ├── template.yaml
│   ├── input_boolean.yaml
│   ├── input_datetime.yaml
│   └── dashboard.yaml
└── docs/
    ├── wiring.md
    └── screenshots/
        ├── phone-view.png
        └── web-view.png
```

## License

MIT License.
