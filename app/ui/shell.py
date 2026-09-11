"""The desktop shell: the window, the hotkeys, the tray, the summon flow.

This replaces the tkinter panel. What stayed the same, deliberately:

  * the host window is snapshotted BEFORE any of our UI exists (OS primer
    §1.1), and selection capture runs before the panel shows, so the
    clipboard fallback's synthetic Ctrl+C lands in the host, not in us
  * one GUI loop for the life of the process -- pywebview's, on the main
    thread -- and no worker ever touches the UI (see bridge.py)

What is new:

  * the panel is a WebView2 window, the engine Tauri itself uses on Windows,
    so the frontend in ui/web/ carries over to the Tauri shell unchanged
  * the screenshot selector is a FROZEN FRAME: the screen is captured first
    and the region is drawn on that still, the way good screenshot tools
    work. Nothing moves under the cursor, no transparency tricks, and the crop
    comes from the full-resolution original rather than from what the overlay
    rendered, so DPI scaling cannot shift it
  * screenshots are read on-device with Windows OCR, so a text-only model can
    still answer about one
  * a tray icon, a single-instance guard, and a window that hides rather than
    closes: PERCH lives in the background, and that is the product
"""

from __future__ import annotations

import base64
import ctypes
import datetime as dt
import io
import json
import os
import queue
import threading
import time
from ctypes import wintypes
from pathlib import Path

import win32api
import win32con
import win32gui
import win32process
import webview

from .. import config
from .. import settings as settings_mod
from ..os_layer import capture, hotkey, ocr, winapi
from .bridge import Api

WEB = Path(__file__).resolve().parent / "web"
TITLE = "PERCH"
REGION_TITLE = "PERCH region"
COMPACT = (440, 700)              # logical px -- scaled by the monitor's DPI
EXPANDED = (1220, 800)
MIN_SIZE = (380, 520)
GEOMETRY_FILE = config.ROOT / "window.json"
CAPTURE_KEEP = 30                 # screenshots are private data; do not hoard them

# Separate library handles, so setting argtypes here cannot disturb the
# ctypes.windll globals the hotkey listener uses.
_user32 = ctypes.WinDLL("user32", use_last_error=True)
_kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
_dwm = ctypes.WinDLL("dwmapi")
_kernel32.OpenProcess.restype = wintypes.HANDLE
_kernel32.OpenProcess.argtypes = (wintypes.DWORD, wintypes.BOOL, wintypes.DWORD)
_kernel32.QueryFullProcessImageNameW.argtypes = (
    wintypes.HANDLE, wintypes.DWORD, wintypes.LPWSTR, ctypes.POINTER(wintypes.DWORD))
_kernel32.CloseHandle.argtypes = (wintypes.HANDLE,)
_user32.AttachThreadInput.argtypes = (wintypes.DWORD, wintypes.DWORD, wintypes.BOOL)
_dwm.DwmSetWindowAttribute.argtypes = (wintypes.HWND, wintypes.DWORD, ctypes.c_void_p,
                                       wintypes.DWORD)

_DWMWA_WINDOW_CORNER_PREFERENCE = 33
_DWMWA_BORDER_COLOR = 34
_DWMWCP_ROUND = 2
# COLORREF is 0x00BBGGRR.
_BORDER_DARK = 0x00423A3A          # #3a3a42
_BORDER_LIGHT = 0x00C6CFD3         # #d3cfc6
_BORDER_PRIVATE = 0x0048A7F0       # #f0a748 -- the private-mode amber

PRETTY = {
    "code": "VS Code", "chrome": "Chrome", "msedge": "Edge", "firefox": "Firefox",
    "brave": "Brave", "opera": "Opera", "winword": "Word", "excel": "Excel",
    "powerpnt": "PowerPoint", "outlook": "Outlook", "olk": "Outlook",
    "onenote": "OneNote", "notepad": "Notepad", "notepad++": "Notepad++",
    "windowsterminal": "Terminal", "cmd": "Command Prompt", "powershell": "PowerShell",
    "pwsh": "PowerShell", "explorer": "File Explorer", "acrobat": "Acrobat",
    "acrord32": "Acrobat Reader", "sumatrapdf": "SumatraPDF", "obsidian": "Obsidian",
    "notion": "Notion", "slack": "Slack", "discord": "Discord", "teams": "Teams",
    "ms-teams": "Teams", "whatsapp": "WhatsApp", "telegram": "Telegram",
    "idea64": "IntelliJ IDEA", "pycharm64": "PyCharm", "devenv": "Visual Studio",
    "cursor": "Cursor", "zed": "Zed",
}

_SHELL_CLASSES = {"Shell_TrayWnd", "Shell_SecondaryTrayWnd", "Progman", "WorkerW",
                  "NotifyIconOverflowWindow"}


def _process_name(hwnd: int) -> str:
    """The host's executable stem, lowercased -- 'code', 'winword', 'keepassxc'.

    This, not the window title, is what privacy source rules match against
    ("keepass*"): a title is whatever the document happens to be called.
    """
    try:
        _tid, pid = win32process.GetWindowThreadProcessId(hwnd)
        handle = _kernel32.OpenProcess(0x1000, False, pid)   # QUERY_LIMITED_INFORMATION
        if not handle:
            return ""
        try:
            buf = ctypes.create_unicode_buffer(1024)
            size = wintypes.DWORD(len(buf))
            if _kernel32.QueryFullProcessImageNameW(handle, 0, buf, ctypes.byref(size)):
                return Path(buf.value).stem.lower()
        finally:
            _kernel32.CloseHandle(handle)
    except Exception:
        pass
    return ""


def _is_shell_surface(hwnd: int) -> bool:
    """The taskbar or the desktop: not a window anyone wants an answer pasted into."""
    try:
        return win32gui.GetClassName(hwnd) in _SHELL_CLASSES
    except Exception:
        return False


def _monitor_scale(hmon) -> float:
    try:
        x, y = ctypes.c_uint(), ctypes.c_uint()
        ctypes.windll.shcore.GetDpiForMonitor(int(hmon), 0, ctypes.byref(x), ctypes.byref(y))
        return max(1.0, x.value / 96.0)
    except Exception:
        return 1.0


def _system_uses_light_theme() -> bool:
    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER,
                            r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize") as k:
            return bool(winreg.QueryValueEx(k, "AppsUseLightTheme")[0])
    except OSError:
        return False


def _thumbnail(path: Path, max_w: int = 520) -> str:
    from PIL import Image
    with Image.open(path) as im:
        im = im.convert("RGB")
        im.thumbnail((max_w, 360))
        buf = io.BytesIO()
        im.save(buf, "JPEG", quality=82)
    return "data:image/jpeg;base64," + base64.b64encode(buf.getvalue()).decode("ascii")


def _tray_image():
    """A bird on a branch, legible at 16 px."""
    from PIL import Image, ImageDraw
    s = 64
    im = Image.new("RGBA", (s, s), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    d.rounded_rectangle((2, 2, s - 3, s - 3), radius=15, fill=(22, 22, 26, 255))
    teal = (94, 200, 192, 255)
    d.line((12, 47, 52, 47), fill=(150, 146, 138, 255), width=4)
    d.ellipse((17, 22, 43, 46), fill=teal)                      # body
    d.ellipse((33, 14, 49, 30), fill=teal)                      # head
    d.polygon([(48, 20), (56, 23), (48, 26)], fill=(242, 193, 78, 255))   # beak
    d.polygon([(19, 36), (8, 32), (18, 42)], fill=teal)         # tail
    d.ellipse((41, 19, 45, 23), fill=(22, 22, 26, 255))         # eye
    return im


_MUTEX = None


def acquire_single_instance() -> bool:
    """Two PERCHes would fight over the same hotkeys, and the loser's chords
    silently stop working. One per user session."""
    global _MUTEX
    import win32event
    import winerror
    _MUTEX = win32event.CreateMutex(None, False, "Local\\PERCH-single-instance")
    return win32api.GetLastError() != winerror.ERROR_ALREADY_EXISTS


class RegionApi:
    """The screenshot selector's API -- three methods and nothing else. The
    overlay page has no business reaching memory, sessions or settings."""

    def __init__(self, shell: "Shell") -> None:
        self._shell = shell

    def frame(self) -> dict:
        return self._shell._region_frame()

    def done(self, rect: dict) -> bool:
        self._shell._region_finish(rect)
        return True

    def cancel(self) -> bool:
        self._shell._region_finish(None)
        return True


class Shell:
    def __init__(self) -> None:
        self.api = Api(shell=self)
        self.window = None
        self.mode = "compact"
        self.visible = False
        self._hwnd = 0
        self._host = None
        self._triggers: "queue.Queue[str | None]" = queue.Queue()
        self._listener = hotkey.HotkeyListener()
        self._tray = None
        self._quitting = False
        self._frame = None
        self._frame_url = ""
        self._region_rect = None
        self._region_event = threading.Event()
        self._grip_origin = None
        self._quiet_until = 0.0           # ignore move/resize events we caused
        self._geo_timer = None
        self._private_border = False

    # ================================================================ lifecycle

    def run(self, open_on_start: bool = False) -> None:
        config.ensure_dirs()
        settings_mod.apply()
        self.window = webview.create_window(
            TITLE, url=(WEB / "index.html").as_uri(), js_api=self.api,
            width=COMPACT[0], height=COMPACT[1], min_size=MIN_SIZE,
            frameless=True, easy_drag=False, on_top=True, hidden=True,
            background_color="#141417" if not _system_uses_light_theme() else "#fbfaf7",
            shadow=True, focus=True, text_select=True, zoomable=False)
        self.window.events.closing += self._on_closing
        self.window.events.moved += self._on_geometry
        self.window.events.resized += self._on_geometry
        webview.start(self._started, (open_on_start,), gui="edgechromium",
                      debug=bool(os.environ.get("PERCH_DEBUG")))
        self._shutdown()

    def _started(self, open_on_start: bool) -> None:
        try:
            for _ in range(60):             # the native window appears a beat after start
                self._hwnd = self._find_hwnd(TITLE)
                if self._hwnd:
                    break
                time.sleep(0.05)
            self._style(self._hwnd)
            self._bind_hotkeys()
            threading.Thread(target=self._trigger_loop, daemon=True,
                             name="perch-triggers").start()
            self._start_tray()
            self._banner()
            if open_on_start:
                self.summon("app")
        except Exception as exc:                              # noqa: BLE001
            print(f"[shell] startup error: {type(exc).__name__}: {exc}")

    def _bind_hotkeys(self) -> None:
        triggers = [
            ("selection", config.HOTKEY_SELECTION, config.HOTKEY_SELECTION_FALLBACKS),
            ("screenshot", config.HOTKEY_SCREENSHOT, config.HOTKEY_SCREENSHOT_FALLBACKS),
            ("plain", config.HOTKEY_PLAIN, config.HOTKEY_PLAIN_FALLBACKS),
        ]
        for label, (mods, vk), fallbacks in triggers:
            self._listener.bind(mods, vk, lambda k=label: self.summon(k),
                                label=label, fallbacks=fallbacks)
        self._listener.start()

    def hotkeys(self) -> dict:
        return {label: (config.describe_combo(*won) if won else None)
                for label, won in self._listener.assigned.items()}

    def _banner(self) -> None:
        st = self.api._status()
        print(f"PERCH {config.APP_VERSION} -- running in the system tray")
        print(f"  memory      {st['memory']} items")
        print(f"  embeddings  {st['embeddings']}"
              f"{'' if st['semantic'] else '   (fallback -- recall is degraded)'}")
        print(f"  model       {st['model']['label']}")
        print(f"  ocr         {ocr.available() or 'unavailable'}")
        for label, combo in self.hotkeys().items():
            print(f"  {combo or 'NOT REGISTERED':<22} {label}")
        for w in st["warnings"]:
            print(f"  !! {w['text']}  {w['fix']}")
        print("  Quit from the tray icon, or Ctrl+C here.\n")

    def quit(self) -> None:
        self._quitting = True
        self._triggers.put(None)
        self._listener.stop()
        if self._tray is not None:
            try:
                self._tray.stop()
            except Exception:
                pass
        for w in list(webview.windows):
            try:
                w.destroy()
            except Exception:
                pass

    def _shutdown(self) -> None:
        self._quitting = True
        self._listener.stop()
        if self._tray is not None:
            try:
                self._tray.stop()
            except Exception:
                pass

    def _on_closing(self, *_args):
        """Alt+F4 or a stray close hides the panel; only Quit ends PERCH."""
        if self._quitting:
            return True
        self.hide()
        return False

    # ================================================================ triggers

    def summon(self, kind: str) -> None:
        self._triggers.put(kind)

    def _trigger_loop(self) -> None:
        # UI Automation is COM, and COM wants initialising on the thread that
        # uses it. Held for the life of the thread.
        try:
            import uiautomation as auto
            _com = auto.UIAutomationInitializerInThread()          # noqa: F841
        except Exception:
            try:
                import pythoncom
                pythoncom.CoInitialize()
            except Exception:
                pass
        while not self._quitting:
            kind = self._triggers.get()
            if kind is None:
                break
            # Coalesce a burst: holding the chord summons once, not five times.
            try:
                while True:
                    extra = self._triggers.get_nowait()
                    if extra is None:
                        return
                    kind = extra
            except queue.Empty:
                pass
            try:
                self._summon(kind)
            except Exception as exc:                          # noqa: BLE001
                print(f"[trigger] {kind} failed: {type(exc).__name__}: {exc}")

    def _summon(self, kind: str) -> None:
        started = time.perf_counter()
        # Snapshot FIRST. One instant after our own window appears,
        # GetForegroundWindow would return us.
        fg = winapi.foreground_window()
        own = bool(fg and self._hwnd and fg.hwnd == self._hwnd)
        if own and kind in ("selection", "plain"):
            # The chord pressed inside PERCH: nothing new to capture, and
            # resetting would throw the conversation away.
            self._js("window.perch && perch.focusComposer()")
            return

        tray = kind.startswith("tray-") or kind == "app"
        kind = {"tray-plain": "plain", "tray-screenshot": "screenshot"}.get(kind, kind)
        host = None if tray else (self._host if own else fg)
        if host is not None and _is_shell_surface(host.hwnd):
            host = None
        app = _process_name(host.hwnd) if host else ""
        ctx = {"kind": kind, "selection": "", "method": "none", "image": "", "thumb": "",
               "ocr": None, "source_title": host.title if host else "", "source_app": app,
               "app_label": PRETTY.get(app, app.title() if app else ""),
               "has_host": host is not None}

        if kind == "selection" and host is not None:
            sel = capture.capture_selection(host)
            ctx["selection"], ctx["method"] = sel.text, sel.method
        elif kind == "screenshot":
            was_visible = self.visible
            if was_visible:
                self.hide()
                time.sleep(0.22)              # out of the frame before it is taken
            shot = self._capture_region()
            if shot is None:
                if was_visible:
                    self.show(self._host)
                print("[trigger] screenshot cancelled")
                return
            result = ocr.read_image(shot)
            ctx.update(image=str(shot), method="screenshot", selection=result.text,
                       thumb=_thumbnail(shot),
                       ocr={"engine": result.engine, "lang": result.language,
                            "ms": result.ms, "note": result.note, "chars": len(result.text)})

        self.mode = "expanded" if kind == "app" else "compact"
        self._host = host
        self.api._open(ctx, host)
        self.show(host)
        print(f"[trigger] {kind:<10} app={app or '-':<14} method={ctx['method']:<10} "
              f"chars={len(ctx['selection']):<5} "
              f"({(time.perf_counter() - started) * 1000:.0f} ms to panel)")

    # ================================================================ window

    def show(self, host=None) -> None:
        if not self._hwnd:
            self._hwnd = self._find_hwnd(TITLE)
        x, y, w, h = self._placement(host)
        self._quiet_until = time.time() + 0.8
        self.window.show()
        if self._hwnd:
            win32gui.SetWindowPos(self._hwnd, win32con.HWND_TOPMOST, x, y, w, h,
                                  win32con.SWP_SHOWWINDOW)
            self._style(self._hwnd)
            self._force_foreground(self._hwnd)
        self.visible = True
        self._js(f"window.perch && perch.setMode({json.dumps(self.mode)}, false)")
        self.nudge()
        self._js("window.perch && perch.focusComposer()")

    def hide(self) -> None:
        self.api._deny_all()
        self.visible = False
        try:
            self.window.hide()
        except Exception:
            pass

    def set_mode(self, mode: str) -> None:
        if mode not in ("compact", "expanded") or mode == self.mode:
            return
        self.mode = mode
        if self.visible and self._hwnd:
            x, y, w, h = self._placement(self._host if mode == "compact" else None)
            self._quiet_until = time.time() + 0.8
            win32gui.SetWindowPos(self._hwnd, 0, x, y, w, h,
                                  win32con.SWP_NOZORDER | win32con.SWP_NOACTIVATE)

    def grip(self, dx: float, dy: float, phase: str) -> None:
        if not self._hwnd:
            return
        if phase == "start":
            self._grip_origin = win32gui.GetWindowRect(self._hwnd)
            return
        if self._grip_origin is None:
            return
        l, t, r, b = self._grip_origin
        hmon = win32api.MonitorFromPoint(((l + r) // 2, (t + b) // 2),
                                         win32con.MONITOR_DEFAULTTONEAREST)
        s = _monitor_scale(hmon)
        w = max(int(MIN_SIZE[0] * s), (r - l) + int(float(dx) * s))
        h = max(int(MIN_SIZE[1] * s), (b - t) + int(float(dy) * s))
        win32gui.SetWindowPos(self._hwnd, 0, 0, 0, w, h,
                              win32con.SWP_NOMOVE | win32con.SWP_NOZORDER
                              | win32con.SWP_NOACTIVATE)
        if phase == "end":
            self._grip_origin = None
            self._save_geo()

    def set_border(self, private: bool) -> None:
        self._private_border = private
        self._style(self._hwnd)

    def nudge(self) -> None:
        self._js("window.perch && perch.pump()")

    def pick_file(self) -> str:
        dialog = getattr(getattr(webview, "FileDialog", None), "OPEN", None)
        if dialog is None:
            dialog = webview.OPEN_DIALOG
        try:
            res = self.window.create_file_dialog(
                dialog, allow_multiple=False,
                file_types=("Conversation exports (*.zip;*.json)", "All files (*.*)"))
        except Exception as exc:                              # noqa: BLE001
            print(f"[shell] file dialog failed: {exc}")
            return ""
        if not res:
            return ""
        return str(res[0] if isinstance(res, (list, tuple)) else res)

    def save_file(self, filename: str) -> str:
        dialog = getattr(getattr(webview, "FileDialog", None), "SAVE", None)
        if dialog is None:
            dialog = webview.SAVE_DIALOG
        try:
            res = self.window.create_file_dialog(dialog, save_filename=filename,
                                                 file_types=("Zip archive (*.zip)",))
        except Exception as exc:                              # noqa: BLE001
            print(f"[shell] save dialog failed: {exc}")
            return ""
        if not res:
            return ""
        return str(res[0] if isinstance(res, (list, tuple)) else res)

    # ------------------------------------------------------------ placement

    def _remember(self) -> bool:
        return bool(settings_mod.load().get("remember_position", True))

    def _anchor(self, host) -> tuple[int, int]:
        if host is not None:
            return ((host.left + host.right) // 2, (host.top + host.bottom) // 2)
        if self._hwnd and self.visible:
            l, t, r, b = win32gui.GetWindowRect(self._hwnd)
            return ((l + r) // 2, (t + b) // 2)
        return win32api.GetCursorPos()

    def _placement(self, host) -> tuple[int, int, int, int]:
        """Physical pixels throughout: the host's rect comes from Win32 and the
        panel is positioned with Win32, so DPI can never mix two unit systems.

        Order of preference, as before:
          1. where the user last put it -- a deliberate choice beats any rule
          2. in the free space beside the host window
          3. hugging the screen edge when the host is maximised
        """
        saved = self._load_geo().get(self.mode) if self._remember() else None
        anchor = ((saved[0] + saved[2] // 2, saved[1] + saved[3] // 2) if saved
                  else self._anchor(host))
        hmon = win32api.MonitorFromPoint(anchor, win32con.MONITOR_DEFAULTTONEAREST)
        l, t, r, b = win32api.GetMonitorInfo(hmon)["Work"]
        s = _monitor_scale(hmon)

        if saved:
            x, y, w, h = saved
            w = min(max(w, int(MIN_SIZE[0] * s)), r - l)
            h = min(max(h, int(MIN_SIZE[1] * s)), b - t)
        elif self.mode == "expanded":
            w = min(int(EXPANDED[0] * s), r - l - int(40 * s))
            h = min(int(EXPANDED[1] * s), b - t - int(40 * s))
            x, y = l + (r - l - w) // 2, t + (b - t - h) // 2
        else:
            w = int(COMPACT[0] * s)
            h = min(int(COMPACT[1] * s), b - t - int(32 * s))
            gap = int(12 * s)
            if host is not None:
                if host.right + gap + w <= r:
                    x = host.right + gap
                elif host.left - gap - w >= l:
                    x = host.left - gap - w
                else:
                    x = r - w - int(16 * s)
                y = host.top + int(24 * s)
            else:
                x, y = r - w - int(24 * s), t + int(24 * s)
        x = max(l, min(x, r - w))
        y = max(t, min(y, b - h))
        return int(x), int(y), int(w), int(h)

    def _on_geometry(self, *_args) -> None:
        if not self.visible or time.time() < self._quiet_until:
            return
        if self._geo_timer is not None:
            self._geo_timer.cancel()
        self._geo_timer = threading.Timer(0.4, self._save_geo)
        self._geo_timer.daemon = True
        self._geo_timer.start()

    def _load_geo(self) -> dict:
        try:
            data = json.loads(GEOMETRY_FILE.read_text(encoding="utf-8"))
            return data if isinstance(data, dict) else {}
        except (OSError, ValueError):
            return {}

    def _save_geo(self) -> None:
        if not self._hwnd:
            return
        try:
            l, t, r, b = win32gui.GetWindowRect(self._hwnd)
        except Exception:
            return
        data = self._load_geo()
        data[self.mode] = [l, t, r - l, b - t]
        try:
            GEOMETRY_FILE.write_text(json.dumps(data), encoding="utf-8")
        except OSError:
            pass

    # ------------------------------------------------------------ win32 details

    def _js(self, code: str) -> None:
        try:
            self.window.run_js(code)
        except Exception:
            pass

    def _find_hwnd(self, title: str) -> int:
        pid = os.getpid()
        found: list[int] = []

        def visit(h, _):
            try:
                if (win32gui.GetWindowText(h) == title
                        and win32process.GetWindowThreadProcessId(h)[1] == pid):
                    found.append(h)
            except Exception:
                pass
            return True

        try:
            win32gui.EnumWindows(visit, None)
        except Exception:
            pass
        return found[0] if found else 0

    def _style(self, hwnd: int) -> None:
        """Windows 11 rounded corners, and a border that turns amber in
        private mode -- the window itself says where the request can go.
        Windows 10 has neither attribute; the page draws its own edge."""
        if not hwnd:
            return
        try:
            pref = ctypes.c_int(_DWMWCP_ROUND)
            _dwm.DwmSetWindowAttribute(hwnd, _DWMWA_WINDOW_CORNER_PREFERENCE,
                                       ctypes.byref(pref), ctypes.sizeof(pref))
            colour = (_BORDER_PRIVATE if self._private_border
                      else _BORDER_LIGHT if _system_uses_light_theme() else _BORDER_DARK)
            value = ctypes.c_uint(colour)
            _dwm.DwmSetWindowAttribute(hwnd, _DWMWA_BORDER_COLOR,
                                       ctypes.byref(value), ctypes.sizeof(value))
        except Exception:
            pass

    def _force_foreground(self, hwnd: int) -> bool:
        try:
            win32gui.SetForegroundWindow(hwnd)
            return True
        except Exception:
            pass
        # Windows refuses to hand focus to a background process unless it is
        # attached to the thread that currently has it.
        try:
            fg = win32gui.GetForegroundWindow()
            other, _ = win32process.GetWindowThreadProcessId(fg)
            me = win32api.GetCurrentThreadId()
            _user32.AttachThreadInput(other, me, True)
            try:
                win32gui.BringWindowToTop(hwnd)
                win32gui.SetForegroundWindow(hwnd)
            finally:
                _user32.AttachThreadInput(other, me, False)
            return True
        except Exception:
            return False

    # ------------------------------------------------------------ screenshot

    def _capture_region(self) -> Path | None:
        from PIL import ImageGrab
        frame = ImageGrab.grab()            # the primary monitor, full resolution
        self._frame = frame
        buf = io.BytesIO()
        frame.convert("RGB").save(buf, "JPEG", quality=80)
        self._frame_url = "data:image/jpeg;base64," + base64.b64encode(buf.getvalue()).decode()
        self._region_rect = None
        self._region_event.clear()

        win = webview.create_window(
            REGION_TITLE, url=(WEB / "region.html").as_uri(), js_api=RegionApi(self),
            fullscreen=True, frameless=True, on_top=True, focus=True,
            background_color="#000000")
        for _ in range(60):
            h = self._find_hwnd(REGION_TITLE)
            if h:
                self._force_foreground(h)
                break
            time.sleep(0.05)
        self._region_event.wait(180)
        try:
            win.destroy()
        except Exception:
            pass
        self._frame_url = ""

        rect = self._region_rect
        if not rect:
            return None
        vw, vh = float(rect.get("vw") or 1), float(rect.get("vh") or 1)
        sx, sy = frame.width / vw, frame.height / vh
        box = (int(rect["x"] * sx), int(rect["y"] * sy),
               int((rect["x"] + rect["w"]) * sx), int((rect["y"] + rect["h"]) * sy))
        if box[2] - box[0] < 4 or box[3] - box[1] < 4:
            return None
        config.CAPTURES.mkdir(parents=True, exist_ok=True)
        path = config.CAPTURES / f"capture-{dt.datetime.now():%Y%m%d-%H%M%S}.png"
        frame.crop(box).save(path)
        self._prune_captures()
        return path

    def _region_frame(self) -> dict:
        f = self._frame
        return {"src": self._frame_url, "w": f.width if f else 0, "h": f.height if f else 0}

    def _region_finish(self, rect) -> None:
        self._region_rect = rect
        self._region_event.set()

    def _prune_captures(self) -> None:
        shots = sorted(config.CAPTURES.glob("capture-*.png"))
        for old in shots[:-CAPTURE_KEEP]:
            old.unlink(missing_ok=True)

    # ------------------------------------------------------------ tray

    def _start_tray(self) -> None:
        try:
            import pystray
        except ImportError:
            print("[shell] pystray not installed -- no tray icon")
            return
        keys = self.hotkeys()

        def item(text, fn, default=False):
            return pystray.MenuItem(text, lambda _icon, _item: fn(), default=default)

        menu = pystray.Menu(
            item("Open PERCH", lambda: self.summon("app"), default=True),
            item(f"Ask anything\t{keys.get('plain') or ''}", lambda: self.summon("tray-plain")),
            item(f"Screenshot and ask\t{keys.get('screenshot') or ''}",
                 lambda: self.summon("tray-screenshot")),
            pystray.Menu.SEPARATOR,
            item("Quit PERCH", self.quit),
        )
        self._tray = pystray.Icon("perch", _tray_image(), "PERCH -- your own AI", menu)
        self._tray.run_detached()
