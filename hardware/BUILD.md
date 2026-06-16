# Lumen — Build Guide

Everything needed to build the physical dome and run the software against it: parts, wiring, firmware flashing, and software setup. If you only want to run the software against a webcam with no hardware, skip to [Software setup](#software-setup) — `main.py` runs fine with no dome connected.

## Parts

| Component | Part used | Approx. cost |
|---|---|---|
| Microcontroller | Freenove ESP32-S3-WROOM dev board + GPIO extension board | ~90 SEK |
| LED | NeoPixel ring, 16x WS2812B | ~40 SEK |
| Input | Momentary push-button, panel-mount | ~10 SEK |
| Enclosure | 3D-printed translucent PLA, ~10 cm | ~20 SEK filament |
| Cable | USB-C, ESP32-S3 to laptop | ~20 SEK |

The spec originally called for a XIAO ESP32-S3; the Freenove dev board is the same chip family and the firmware ports directly. No level shifter, capacitor, or inline resistor is needed — direct GPIO drive was verified stable.

## Wiring

| Signal | Pin |
|---|---|
| NeoPixel ring DI | GPIO 5 |
| Button (other leg to GND) | GPIO 4, `INPUT_PULLUP` |
| Ring power | 5V / GND rail |

Solder the ring's three wire pads (5V, GND, DI) rather than relying on friction contact — marginal joints held up fine hands-off but flickered under mechanical stress (handling, vibration) during testing.

## Firmware

1. Install the ESP32 board package in Arduino IDE (Espressif's board manager JSON) and the `Adafruit_NeoPixel` library.
2. Open `lumen_demo.ino` (in this folder). Arduino IDE will offer to move it into a matching `lumen_demo/` folder — accept that, it's just an IDE requirement.
3. Board settings (locked from testing on the Freenove dev board):
   - Board: `ESP32S3 Dev Module`
   - USB Mode: **Hardware CDC and JTAG** — not USB-OTG CDC, which was unreliable for the Serial Monitor due to CDC re-enumeration timing
   - Upload Mode: UART0 / Hardware CDC
   - USB CDC On Boot: Enabled
   - CPU Frequency: 240MHz, Flash Size: 4MB, Partition Scheme: Default 4MB with spiffs
   - Upload Speed: 921600
4. Plug in via the UART port (not OTG). On macOS it should enumerate as something like `/dev/cu.usbmodem101` — run `ls /dev/cu.usbmodem*` to confirm.
5. Flash. Open the Serial Monitor at 115200 baud — you should see `=== Lumen ===` on boot.
6. Sanity check without any Python involved: type `C`, `A`, or `B` into the Serial Monitor (no line ending needed) and confirm the ring switches between warm white, amber, and red. Tap the button — ring should go flat grey (paused). Hold the button (~1s) — ring should start the green 4-7-8 breathing cycle and return to the previous state after 2 cycles.

Color order is `NEO_GRB` (`NEO_RGB` produced visibly wrong colors on this ring). Rendering uses `strip.gamma32(strip.ColorHSV(...))` — raw RGB math caused color flips at low brightness, so don't swap that out for plain `strip.Color()`.

## Software setup

Requires Python 3.12 — MediaPipe 0.10.14 breaks on 3.13's `mp.solutions` API.

```bash
python3.12 -m venv lumen-env
source lumen-env/bin/activate
pip install -r requirements.txt
python main.py
```

This opens a webcam window with a live EAR/blink/risk overlay. With no dome connected it runs standalone — no changes needed.

To drive the physical dome: find the serial port (`ls /dev/tty.*` on macOS/Linux, or the Arduino IDE's port list on Windows), then open `main.py` and set:

```python
SERIAL_PORT = "/dev/tty.usbmodem1101"   # your port here
```

Re-run `python main.py`. You should see `Dome connected on <port>` printed at startup, and the ring should now track the on-screen state automatically as your blink rate and focus time change.

## Keyboard controls (software)

| Key | Action |
|---|---|
| `q` | Quit |
| `r` | Full session reset (blink counter, baseline, risk timer, override) |
| `d` | Toggle DEMO (fast, ~30s settle) / REAL (slow, ~30min settle) baseline speed |
| `1` / `2` / `3` | Force CALM / ATTENTION / BREAK, bypassing sensing |
| `0` | Clear override, return to automatic sensing |

## Troubleshooting

- **Serial Monitor unreliable / port disappears on upload**: you're probably on the OTG port. Switch to UART and re-select USB Mode as above.
- **Ring flickers only when touched**: solder joint, not code — reflow the three ring pads.
- **Colors look wrong (e.g. green where you expect red)**: check `NEO_GRB` vs `NEO_RGB` in the `Adafruit_NeoPixel` constructor.
- **`main.py` can't open the serial port**: it fails soft — check the printed error, confirm the port string, confirm nothing else (e.g. the Arduino Serial Monitor) has it open.
