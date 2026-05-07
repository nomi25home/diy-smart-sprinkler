# Wiring Guide

This project uses a Raspberry Pi 2 Model B to control a SainSmart 16-Channel 12V Relay Module. The relay board switches the existing 24VAC sprinkler zone wires.

## Important Safety Notes

- Do not connect Raspberry Pi GPIO pins to 24VAC.
- The Raspberry Pi should only connect to the relay board control/input side.
- The relay contacts switch the sprinkler valve wiring.
- Keep the Raspberry Pi and relay board protected from water.
- If you are not comfortable with wiring, hire a licensed electrician or irrigation professional.

## GPIO to Relay Input Mapping

| Zone | Raspberry Pi BCM GPIO | Physical Pin | Relay Input |
|---|---:|---:|---|
| Zone 1 | GPIO4 | Pin 7 | IN1 |
| Zone 2 | GPIO17 | Pin 11 | IN2 |
| Zone 3 | GPIO27 | Pin 13 | IN3 |
| Zone 4 | GPIO22 | Pin 15 | IN4 |
| Zone 5 | GPIO23 | Pin 16 | IN5 |
| Zone 6 | GPIO24 | Pin 18 | IN6 |

## Raspberry Pi to Relay Board Wiring

Connect the Raspberry Pi GPIO outputs to the relay board inputs:

```text
Pi GPIO4   -> Relay IN1
Pi GPIO17  -> Relay IN2
Pi GPIO27  -> Relay IN3
Pi GPIO22  -> Relay IN4
Pi GPIO23  -> Relay IN5
Pi GPIO24  -> Relay IN6
Pi GND     -> Relay GND / control reference
```

The relay board should be powered according to the relay board requirements. In this build, the SainSmart relay board is a 12V relay module and is powered separately from the Raspberry Pi.

## Sprinkler 24VAC Wiring

Each sprinkler valve normally has:

- One common wire
- One zone wire

Keep the common wire connected to all valves.

Switch the zone wire through the relay contacts:

```text
24VAC HOT     -> Relay COM
Relay NO      -> Zone wire
24VAC COMMON  -> Valve common bundle
```

Repeat this for each zone.

## Relay Contact Mapping

| Zone | Relay Contact |
|---|---|
| Zone 1 | Relay 1 COM / NO |
| Zone 2 | Relay 2 COM / NO |
| Zone 3 | Relay 3 COM / NO |
| Zone 4 | Relay 4 COM / NO |
| Zone 5 | Relay 5 COM / NO |
| Zone 6 | Relay 6 COM / NO |

## Example Zone Wiring

For Zone 1:

```text
24VAC HOT  -> Relay 1 COM
Relay 1 NO -> Zone 1 valve wire
24VAC COMMON remains connected to valve common bundle
```

For Zone 2:

```text
24VAC HOT  -> Relay 2 COM
Relay 2 NO -> Zone 2 valve wire
24VAC COMMON remains connected to valve common bundle
```

The same pattern is repeated for zones 3 through 6.

## Relay Behavior

The Python API uses open-drain style GPIO behavior:

```text
ON  = claim GPIO as output and drive LOW
OFF = release GPIO as input
```

This was required for reliable triggering with the relay board used in this build.

## Why OFF Releases the GPIO

Some optocoupler relay boards do not behave reliably when the Raspberry Pi drives the input HIGH at 3.3V.

This project turns a relay OFF by releasing the GPIO pin as an input instead of driving it HIGH.

That behavior is implemented in `raspberry-pi/server.py`.

## Testing One Zone

Test one zone at a time.

From another machine on the same network:

```bash
curl -X POST http://<PI_IP_ADDRESS>:5050/zone/1 -d "on"
curl http://<PI_IP_ADDRESS>:5050/zone/1
curl -X POST http://<PI_IP_ADDRESS>:5050/zone/1 -d "off"
```

Emergency all off:

```bash
curl -X POST http://<PI_IP_ADDRESS>:5050/alloff
```

## Safety Design

This project intentionally enables only one zone at a time.

When one zone is turned on, the API turns all other zones off first.

The `/alloff` endpoint should be used as the emergency stop.

## Notes About `/allon`

The API includes an `/allon` endpoint, but because of the one-zone safety logic, it is not recommended for normal sprinkler operation.

In this project, only one sprinkler zone should run at a time.
