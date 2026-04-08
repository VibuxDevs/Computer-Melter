#!/usr/bin/env python3
"""
Computer Melter — harmless visual prank. Melt effect on a screen capture (not malware).

Modes:
  default     Fullscreen pass-through overlay (PySide6): mouse goes to apps below; ESC quits (needs pynput).
  --window    Resizable pygame window, or --fullscreen for old-style full capture (ESC exits).
"""
from __future__ import annotations

import argparse
import os
import sys
import time

import mss
import numpy as np
import pygame


def grab_screen_bgr(monitor: int = 1) -> tuple[np.ndarray, tuple[int, int]]:
    """monitor 1 = primary in mss (0 is all monitors combined)."""
    with mss.mss() as sct:
        mon = sct.monitors[monitor]
        shot = sct.grab(mon)
        arr = np.asarray(shot, dtype=np.uint8)[:, :, :3][:, :, ::-1].copy()
        return arr, (arr.shape[1], arr.shape[0])


def downscale_if_wide(rgb: np.ndarray, max_w: int = 1280) -> np.ndarray:
    h, w, _ = rgb.shape
    if w <= max_w:
        return rgb
    scale = max_w / w
    nw = max_w
    nh = int(h * scale)
    surf = pygame.surfarray.make_surface(np.transpose(rgb, (1, 0, 2)))
    surf = pygame.transform.smoothscale(surf, (nw, nh))
    return pygame.surfarray.array3d(surf).transpose(1, 0, 2)


def resize_rgb_to(rgb: np.ndarray, tw: int, th: int) -> np.ndarray:
    """Scale (H,W,3) to (th,tw,3) for live capture matching fixed melt width."""
    surf = pygame.surfarray.make_surface(np.transpose(rgb, (1, 0, 2)))
    surf = pygame.transform.smoothscale(surf, (tw, th))
    return pygame.surfarray.array3d(surf).transpose(1, 0, 2)


def vertical_sample_bilinear(src: np.ndarray, y_src: np.ndarray) -> np.ndarray:
    h, w, _ = src.shape
    y_src = np.clip(y_src, 0.0, h - 1 - 1e-6)
    y0 = np.floor(y_src).astype(np.int32)
    y1 = np.minimum(y0 + 1, h - 1)
    t = (y_src - y0.astype(np.float32))[..., np.newaxis]
    jj = np.broadcast_to(np.arange(w, dtype=np.int32), (h, w))
    c0 = src[y0, jj].astype(np.float32)
    c1 = src[y1, jj].astype(np.float32)
    return np.clip((1.0 - t) * c0 + t * c1, 0, 255).astype(np.uint8)


def apply_column_melt(
    src: np.ndarray,
    col_slip: np.ndarray,
    t: float,
    intensity: float,
    rng: np.random.Generator,
) -> np.ndarray:
    h, w, _ = src.shape
    hh = max(h - 1, 1)
    yn = np.arange(h, dtype=np.float32)[:, np.newaxis] / hh
    bottom_curve = yn**2.4

    slip = col_slip[np.newaxis, :] * bottom_curve * (0.35 + 0.65 * intensity)
    wobble = (
        2.0 * np.sin(np.arange(w, dtype=np.float32) * 0.11 + t * 1.8) * intensity
        + 1.2 * np.sin(np.arange(h, dtype=np.float32)[:, np.newaxis] * 0.07 + t * 2.3)
    )
    y_src = np.arange(h, dtype=np.float32)[:, np.newaxis] - slip + wobble * bottom_curve
    out = vertical_sample_bilinear(src, y_src)

    sm = 0.12 + 0.55 * intensity
    for _ in range(2):
        above = np.roll(out, 1, axis=0)
        above[0, :, :] = out[0, :, :]
        out = (out.astype(np.float32) * (1.0 - sm) + above.astype(np.float32) * sm).astype(np.uint8)

    if intensity > 0.18:
        sh = int(1 + intensity * 16)
        o = out.copy()
        o[:, :, 0] = np.roll(out[:, :, 0], sh, axis=1)
        o[:, :, 2] = np.roll(out[:, :, 2], -sh, axis=1)
        out = o

    if intensity > 0.25:
        mask = rng.random((h, w)) < (0.0015 + intensity * 0.012)
        noise = rng.integers(0, 256, size=(h, w, 3), dtype=np.uint8)
        out[mask] = noise[mask]

    return out


def rgb_to_surface(rgb: np.ndarray) -> pygame.Surface:
    arr = np.transpose(rgb, (1, 0, 2))
    return pygame.surfarray.make_surface(arr)


def run_pygame(
    *,
    fullscreen: bool,
    window_fraction: float,
) -> None:
    os.environ.setdefault("SDL_VIDEO_CENTERED", "1")
    pygame.init()
    pygame.display.set_caption("Computer Melter — ESC to exit · drag window to use desktop")

    try:
        rgb0, _ = grab_screen_bgr()
    except Exception as e:
        print("Could not capture screen:", e, file=sys.stderr)
        sys.exit(1)

    rgb0 = downscale_if_wide(rgb0)
    h, w, _ = rgb0.shape

    info = pygame.display.Info()
    wf = max(320, int(info.current_w * window_fraction))
    hf = max(240, int(info.current_h * window_fraction))

    if fullscreen:
        flags = pygame.FULLSCREEN | pygame.SCALED
        screen = pygame.display.set_mode((w, h), flags)
    else:
        flags = pygame.RESIZABLE
        screen = pygame.display.set_mode((wf, hf), flags)

    clock = pygame.time.Clock()
    rng = np.random.default_rng()
    font = pygame.font.SysFont("consolas", 20, bold=True)

    start = time.perf_counter()
    col_slip = np.zeros(w, dtype=np.float32)
    col_rate = rng.uniform(0.35, 1.2, size=w).astype(np.float32)
    running = True
    rgb = rgb0

    while running:
        dt = clock.tick(60) / 1000.0
        now = time.perf_counter() - start
        intensity = float(np.clip(now / 45.0, 0.0, 1.0))

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            elif event.type == pygame.KEYDOWN:
                if event.key in (pygame.K_ESCAPE, pygame.K_q) and (
                    pygame.key.get_mods() & pygame.KMOD_CTRL or event.key == pygame.K_ESCAPE
                ):
                    running = False
            elif event.type == pygame.VIDEORESIZE and not fullscreen:
                screen = pygame.display.set_mode((max(320, event.w), max(240, event.h)), pygame.RESIZABLE)

        col_slip += dt * col_rate * (10.0 + 140.0 * intensity * intensity)
        col_slip += rng.normal(0, 0.15 * intensity, size=w).astype(np.float32) * dt * 40.0
        col_slip = np.maximum(col_slip, 0.0)

        blended = apply_column_melt(rgb, col_slip, now, intensity, rng)
        surf = rgb_to_surface(blended)

        sw, sh_ = screen.get_size()
        if (sw, sh_) != (w, h):
            surf = pygame.transform.smoothscale(surf, (sw, sh_))

        screen.blit(surf, (0, 0))

        hint = font.render("COMPUTER MELTER — ESC to exit", True, (255, 80, 80))
        bg = pygame.Surface((hint.get_width() + 12, hint.get_height() + 8), pygame.SRCALPHA)
        bg.fill((0, 0, 0, 160))
        screen.blit(bg, (6, 6))
        screen.blit(hint, (9, 8))
        if not fullscreen and now < 5.0:
            sub = font.render("Resize / move this window — desktop stays usable around it.", True, (210, 210, 210))
            screen.blit(sub, (9, 30))

        pygame.display.flip()

    pygame.quit()


def numpy_rgb_to_qimage(rgb: np.ndarray):
    """RGB uint8 (H,W,3) -> QImage copy (safe lifetime)."""
    from PySide6.QtGui import QImage

    if rgb.dtype != np.uint8:
        rgb = rgb.astype(np.uint8)
    hh, ww, _ = rgb.shape
    buf = np.ascontiguousarray(rgb)
    bpl = 3 * ww
    return QImage(buf.data, ww, hh, bpl, QImage.Format.Format_RGB888).copy()


def _start_global_esc_quit(app) -> object | None:
    """Register ESC anywhere to quit (overlay ignores focus / input). Returns listener or None."""
    try:
        from pynput import keyboard
        from PySide6.QtCore import QObject, Signal
    except ImportError:
        print(
            "Install pynput for ESC to quit the overlay: pip install pynput",
            file=sys.stderr,
        )
        return None

    class _EscBridge(QObject):
        quit_requested = Signal()

    bridge = _EscBridge()
    bridge.quit_requested.connect(app.quit)

    def on_press(key: object) -> None:
        if key == keyboard.Key.esc:
            bridge.quit_requested.emit()

    listener = keyboard.Listener(on_press=on_press, suppress=False)
    listener.start()
    return listener


def run_qt_overlay(*, max_w: int = 1280, live_refresh_ms: int = 0) -> None:
    try:
        from PySide6.QtCore import Qt, QTimer
        from PySide6.QtGui import QPixmap
        from PySide6.QtWidgets import QApplication, QLabel, QWidget
    except ImportError:
        print(
            "Overlay mode needs PySide6. Install with: pip install PySide6",
            file=sys.stderr,
        )
        sys.exit(1)

    pygame.init()

    app = QApplication(sys.argv)
    screen = app.primaryScreen()
    if screen is None:
        print("No primary screen.", file=sys.stderr)
        sys.exit(1)
    geo = screen.geometry()
    sw, sh = geo.width(), geo.height()

    try:
        raw, _ = grab_screen_bgr()
    except Exception as e:
        print("Could not capture screen:", e, file=sys.stderr)
        sys.exit(1)

    raw = downscale_if_wide(raw, max_w=max_w)
    h, w, _ = raw.shape

    # WindowTransparentForInput is often broken on Wayland / some X11 WMs. Prefer mouse-event
    # pass-through + no activation so clicks/typing hit the real desktop (X11: try QT_QPA_PLATFORM=xcb).
    flags = (
        Qt.WindowType.FramelessWindowHint
        | Qt.WindowType.WindowStaysOnTopHint
        | Qt.WindowType.Tool
    )
    dfa = getattr(Qt.WindowType, "WindowDoesNotAcceptFocus", None)
    if dfa is not None:
        flags |= dfa

    class Overlay(QWidget):
        def __init__(self) -> None:
            super().__init__()
            self.setWindowFlags(flags)
            self.setGeometry(geo)
            self.setFocusPolicy(Qt.FocusPolicy.NoFocus)
            self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, False)
            self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating, True)
            self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)

            self.label = QLabel(self)
            self.label.setGeometry(0, 0, sw, sh)
            self.label.setScaledContents(True)
            self.label.setFocusPolicy(Qt.FocusPolicy.NoFocus)
            self.label.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)

            hint_msg = (
                "PASS-THROUGH — ESC to quit (global) · re-grab every "
                f"{live_refresh_ms / 1000:.1f}s (--refresh-ms)"
                if live_refresh_ms > 0
                else "PASS-THROUGH — ESC to quit (global) · frozen snapshot (--refresh-ms 0)"
            )
            self._hint = QLabel(hint_msg, self)
            self._hint.setFocusPolicy(Qt.FocusPolicy.NoFocus)
            self._hint.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
            self._hint.setStyleSheet(
                "color: rgb(255,90,90); background: rgba(0,0,0,140); padding: 6px; font: 13px monospace;"
            )
            self._hint.adjustSize()
            self._hint.move(8, sh - self._hint.height() - 10)

        def resizeEvent(self, event) -> None:  # noqa: N802
            self.label.setGeometry(0, 0, self.width(), self.height())
            self._hint.move(8, self.height() - self._hint.height() - 10)

    win = Overlay()
    win.showFullScreen()

    if sys.platform.startswith("linux") and os.environ.get("WAYLAND_DISPLAY"):
        print(
            "Wayland: if clicks/keys don't reach apps behind the melt, try forcing X11 Qt: "
            "QT_QPA_PLATFORM=xcb ./run.sh",
            file=sys.stderr,
        )

    esc_listener = _start_global_esc_quit(app)

    rng = np.random.default_rng()
    start = time.perf_counter()
    col_slip = np.zeros(w, dtype=np.float32)
    col_rate = rng.uniform(0.35, 1.2, size=w).astype(np.float32)
    src_rgb = raw.copy()
    last_capture = time.perf_counter()
    last_tick = time.perf_counter()

    def capture_desktop_behind() -> None:
        """Briefly hide overlay so mss sees the real desktop (infrequent: limits flicker)."""
        nonlocal src_rgb, last_capture
        win.setWindowOpacity(0.0)
        app.processEvents()
        app.sendPostedEvents(None, 0)
        time.sleep(0.02)
        try:
            cap, _ = grab_screen_bgr()
        except Exception:
            cap = None
        finally:
            win.setWindowOpacity(1.0)
            app.processEvents()
        if cap is None:
            return
        cap = downscale_if_wide(cap, max_w=max_w)
        if cap.shape[0] != h or cap.shape[1] != w:
            cap = resize_rgb_to(cap, w, h)
        src_rgb = cap
        last_capture = time.perf_counter()

    def tick() -> None:
        nonlocal col_slip, last_tick, src_rgb
        tnow = time.perf_counter()
        dt = min(0.05, max(0.0, tnow - last_tick))
        last_tick = tnow
        now = tnow - start
        intensity = float(np.clip(now / 40.0, 0.0, 1.0))

        if live_refresh_ms > 0 and (tnow - last_capture) * 1000.0 >= live_refresh_ms:
            capture_desktop_behind()

        rgb = src_rgb
        if rgb.shape[0] != h or rgb.shape[1] != w:
            rgb = resize_rgb_to(rgb, w, h)
            src_rgb = rgb

        col_slip = col_slip + dt * col_rate * (14.0 + 150.0 * intensity * intensity)
        col_slip = col_slip + rng.normal(0, 0.15 * intensity, size=w).astype(np.float32) * dt * 40.0
        col_slip = np.maximum(col_slip, 0.0)

        blended = apply_column_melt(rgb, col_slip, now, intensity, rng)
        win.label.setPixmap(QPixmap.fromImage(numpy_rgb_to_qimage(blended)))

    timer = QTimer()
    timer.timeout.connect(tick)
    timer.start(16)
    tick()

    try:
        exit_code = app.exec()
    finally:
        if esc_listener is not None:
            esc_listener.stop()
    raise SystemExit(exit_code)


def main() -> None:
    p = argparse.ArgumentParser(description="Computer Melter (harmless prank)")
    p.add_argument(
        "--window",
        action="store_true",
        help="Pygame window instead of default pass-through fullscreen overlay",
    )
    p.add_argument(
        "--fullscreen",
        action="store_true",
        help="With --window: pygame fullscreen (blocks desktop behind window)",
    )
    p.add_argument(
        "--refresh-ms",
        type=int,
        default=0,
        metavar="MS",
        help="Overlay only: re-grab desktop every N ms (causes brief flicker). Default 0 = frozen snapshot.",
    )
    p.add_argument(
        "--size",
        type=float,
        default=0.68,
        metavar="F",
        help="With --window: size as fraction of screen (default 0.68)",
    )
    args = p.parse_args()

    if args.window:
        frac = float(np.clip(args.size, 0.25, 0.95))
        run_pygame(fullscreen=args.fullscreen, window_fraction=frac)
    else:
        ms = max(0, int(args.refresh_ms))
        run_qt_overlay(live_refresh_ms=ms)


if __name__ == "__main__":
    main()
