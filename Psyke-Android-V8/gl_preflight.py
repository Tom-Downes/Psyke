from __future__ import annotations

import ctypes
import os
import re
import sys
from ctypes import wintypes


GL_VERSION = 0x1F02
GL_VENDOR = 0x1F00
GL_RENDERER = 0x1F01

PFD_TYPE_RGBA = 0
PFD_MAIN_PLANE = 0
PFD_DRAW_TO_WINDOW = 0x00000004
PFD_SUPPORT_OPENGL = 0x00000020
PFD_DOUBLEBUFFER = 0x00000001

WS_OVERLAPPED = 0x00000000
WS_SYSMENU = 0x00080000
CW_USEDEFAULT = 0x80000000
MB_ICONERROR = 0x00000010
MB_OK = 0x00000000


HANDLE = wintypes.HANDLE
HINSTANCE = HANDLE
HICON = HANDLE
HCURSOR = HANDLE
HBRUSH = HANDLE


class WNDCLASSW(ctypes.Structure):
    _fields_ = [
        ("style", ctypes.c_uint),
        ("lpfnWndProc", ctypes.c_void_p),
        ("cbClsExtra", ctypes.c_int),
        ("cbWndExtra", ctypes.c_int),
        ("hInstance", HINSTANCE),
        ("hIcon", HICON),
        ("hCursor", HCURSOR),
        ("hbrBackground", HBRUSH),
        ("lpszMenuName", wintypes.LPCWSTR),
        ("lpszClassName", wintypes.LPCWSTR),
    ]


class PIXELFORMATDESCRIPTOR(ctypes.Structure):
    _fields_ = [
        ("nSize", wintypes.WORD),
        ("nVersion", wintypes.WORD),
        ("dwFlags", wintypes.DWORD),
        ("iPixelType", ctypes.c_ubyte),
        ("cColorBits", ctypes.c_ubyte),
        ("cRedBits", ctypes.c_ubyte),
        ("cRedShift", ctypes.c_ubyte),
        ("cGreenBits", ctypes.c_ubyte),
        ("cGreenShift", ctypes.c_ubyte),
        ("cBlueBits", ctypes.c_ubyte),
        ("cBlueShift", ctypes.c_ubyte),
        ("cAlphaBits", ctypes.c_ubyte),
        ("cAlphaShift", ctypes.c_ubyte),
        ("cAccumBits", ctypes.c_ubyte),
        ("cAccumRedBits", ctypes.c_ubyte),
        ("cAccumGreenBits", ctypes.c_ubyte),
        ("cAccumBlueBits", ctypes.c_ubyte),
        ("cAccumAlphaBits", ctypes.c_ubyte),
        ("cDepthBits", ctypes.c_ubyte),
        ("cStencilBits", ctypes.c_ubyte),
        ("cAuxBuffers", ctypes.c_ubyte),
        ("iLayerType", ctypes.c_ubyte),
        ("bReserved", ctypes.c_ubyte),
        ("dwLayerMask", wintypes.DWORD),
        ("dwVisibleMask", wintypes.DWORD),
        ("dwDamageMask", wintypes.DWORD),
    ]


def _decode_gl_text(value: bytes | None) -> str:
    if not value:
        return "unknown"
    try:
        return value.decode("ascii", errors="replace")
    except Exception:
        return str(value)


def _parse_gl_version(version_text: str) -> tuple[int, int]:
    match = re.search(r"(\d+)\.(\d+)", version_text)
    if not match:
        return (0, 0)
    return int(match.group(1)), int(match.group(2))


def probe_opengl() -> dict[str, object]:
    if sys.platform != "win32":
        return {"ok": True, "reason": "not-windows"}

    user32 = ctypes.windll.user32
    gdi32 = ctypes.windll.gdi32
    kernel32 = ctypes.windll.kernel32
    opengl32 = ctypes.windll.opengl32

    class_name = "PsykeGLProbeWindow"
    wnd_proc = user32.DefWindowProcW
    hinstance = kernel32.GetModuleHandleW(None)

    wc = WNDCLASSW()
    wc.lpfnWndProc = ctypes.cast(wnd_proc, ctypes.c_void_p).value
    wc.hInstance = hinstance
    wc.lpszClassName = class_name
    atom = user32.RegisterClassW(ctypes.byref(wc))
    if not atom and ctypes.GetLastError() != 1410:
        raise ctypes.WinError()

    hwnd = None
    hdc = None
    hglrc = None
    try:
        hwnd = user32.CreateWindowExW(
            0,
            class_name,
            "Psyke GL Probe",
            WS_OVERLAPPED | WS_SYSMENU,
            CW_USEDEFAULT,
            CW_USEDEFAULT,
            1,
            1,
            None,
            None,
            hinstance,
            None,
        )
        if not hwnd:
            raise ctypes.WinError()

        hdc = user32.GetDC(hwnd)
        if not hdc:
            raise ctypes.WinError()

        pfd = PIXELFORMATDESCRIPTOR()
        pfd.nSize = ctypes.sizeof(PIXELFORMATDESCRIPTOR)
        pfd.nVersion = 1
        pfd.dwFlags = PFD_DRAW_TO_WINDOW | PFD_SUPPORT_OPENGL | PFD_DOUBLEBUFFER
        pfd.iPixelType = PFD_TYPE_RGBA
        pfd.cColorBits = 24
        pfd.cDepthBits = 16
        pfd.iLayerType = PFD_MAIN_PLANE

        pixel_format = gdi32.ChoosePixelFormat(hdc, ctypes.byref(pfd))
        if not pixel_format:
            raise ctypes.WinError()
        if not gdi32.SetPixelFormat(hdc, pixel_format, ctypes.byref(pfd)):
            raise ctypes.WinError()

        hglrc = opengl32.wglCreateContext(hdc)
        if not hglrc:
            raise ctypes.WinError()
        if not opengl32.wglMakeCurrent(hdc, hglrc):
            raise ctypes.WinError()

        opengl32.glGetString.restype = ctypes.c_char_p
        version = _decode_gl_text(opengl32.glGetString(GL_VERSION))
        vendor = _decode_gl_text(opengl32.glGetString(GL_VENDOR))
        renderer = _decode_gl_text(opengl32.glGetString(GL_RENDERER))
        major, minor = _parse_gl_version(version)

        return {
            "ok": (major, minor) >= (2, 0) and "gdi generic" not in renderer.lower(),
            "version": version,
            "vendor": vendor,
            "renderer": renderer,
            "major": major,
            "minor": minor,
        }
    finally:
        if hglrc:
            opengl32.wglMakeCurrent(None, None)
            opengl32.wglDeleteContext(hglrc)
        if hdc and hwnd:
            user32.ReleaseDC(hwnd, hdc)
        if hwnd:
            user32.DestroyWindow(hwnd)
        user32.UnregisterClassW(class_name, hinstance)


def ensure_compatible_opengl() -> None:
    if sys.platform != "win32":
        return
    if os.environ.get("PSYKE_SKIP_GL_PREFLIGHT"):
        return

    try:
        info = probe_opengl()
    except Exception as exc:
        print(f"OpenGL preflight probe failed: {exc}", file=sys.stderr)
        return

    if info.get("ok"):
        return

    version = info.get("version", "unknown")
    vendor = info.get("vendor", "unknown")
    renderer = info.get("renderer", "unknown")
    message = (
        "This machine is exposing an OpenGL driver that is too old for Kivy.\n\n"
        f"OpenGL version: {version}\n"
        f"Vendor: {vendor}\n"
        f"Renderer: {renderer}\n\n"
        "Kivy requires OpenGL 2.0 or newer.\n\n"
        "Most common fixes:\n"
        "- run the app in the local desktop session instead of software-rendered remote graphics\n"
        "- install or update the real GPU driver from Intel, NVIDIA, or AMD\n"
        "- enable 3D acceleration if this is a virtual machine\n\n"
        "Set PSYKE_SKIP_GL_PREFLIGHT=1 to bypass this check."
    )
    print(message, file=sys.stderr)
    ctypes.windll.user32.MessageBoxW(
        None,
        message,
        "Psyke OpenGL Preflight",
        MB_OK | MB_ICONERROR,
    )
    raise SystemExit(1)
