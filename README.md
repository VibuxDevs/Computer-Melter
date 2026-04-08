# Computer Melter

A harmless visual prank: a **melting screen** effect on top of a screenshot of your desktop. It does not modify files, install persistence, or touch anything beyond grabbing pixels for display.

## Setup

Use a virtual environment (required on Arch and other distros with **PEP 668** — system `pip` is blocked).

```bash
cd /path/to/PCMelter
python -m venv .venv
.venv/bin/pip install -r requirements.txt PySide6 pynput
```

- **default (overlay):** PySide6, pygame (downscaling), mss, numpy, **pynput** (global **ESC** to quit).
- **`--window` mode:** pygame + mss + numpy only (no PySide6 or pynput needed for basic use).

Then run:

```bash
./run.sh
```

`run.sh` always uses `.venv/bin/python`. Pass arguments through: `./run.sh --window`, etc.

## How to run

| Command | What it does |
|--------|----------------|
| `./run.sh` | Fullscreen **overlay**: melt on top; mouse is meant to pass through to apps below. **ESC** quits (via `pynput`). |
| `./run.sh --window` | Resizable **pygame** window; use the rest of the desktop outside it. **ESC** quits. |
| `./run.sh --window --fullscreen` | Pygame fullscreen (blocks what is behind the window). **ESC** quits. |

### Overlay options

- **`--refresh-ms N`** — Re-capture the desktop every *N* milliseconds so the melt follows a live screen. Causes a short visible blink when capturing (`N = 0` by default: one frozen snapshot, no flicker).

### Window options

- **`--size F`** — Initial size as a fraction of the screen (default `0.68`, only with `--window`).

## Exiting

- **Overlay:** **ESC** anywhere (needs `pynput`), or **Ctrl+C** in the terminal you started from, or kill the process from another session.
- **Pygame:** **ESC** (also **Ctrl+Q**).

## Troubleshooting

- **Clicks or typing don’t reach apps behind the melt (Wayland):** Qt input pass-through is unreliable on some setups. Try forcing X11 for Qt:

  ```bash
  QT_QPA_PLATFORM=xcb ./run.sh
  ```

- **ESC does nothing in overlay:** Install **`pynput`** in the same venv. On some Wayland setups global key hooks are limited; use **Ctrl+C** in the terminal.

- **`ModuleNotFoundError` / `externally-managed-environment`:** You are not using the venv. Run `./run.sh` or `.venv/bin/python computer_melter.py`.

## Requirements

- Python 3.10+ (what your environment provides).
- A graphical session with working screen capture for **mss** (X11 or Wayland depending on OS).

## Files

- `computer_melter.py` — entrypoint and effect implementation.
- `run.sh` — launcher that uses `.venv`.
- `requirements.txt` — pygame, mss, numpy; overlay also needs **PySide6** and **pynput** (install as in Setup).
# Computer-Melter
