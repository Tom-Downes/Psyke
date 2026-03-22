import ctypes
import os
import platform
import sys
import traceback
from ctypes import wintypes

LPARAM = getattr(wintypes, "LPARAM", ctypes.c_ssize_t)
WPARAM = getattr(wintypes, "WPARAM", ctypes.c_size_t)
LRESULT = getattr(wintypes, "LRESULT", ctypes.c_ssize_t)
HINSTANCE = getattr(wintypes, "HINSTANCE", wintypes.HANDLE)
HICON = getattr(wintypes, "HICON", wintypes.HANDLE)
HCURSOR = getattr(wintypes, "HCURSOR", wintypes.HANDLE)
HBRUSH = getattr(wintypes, "HBRUSH", wintypes.HANDLE)
HMODULE = getattr(wintypes, "HMODULE", wintypes.HANDLE)
WNDPROC = ctypes.WINFUNCTYPE(LRESULT, wintypes.HWND, wintypes.UINT, WPARAM, LPARAM)


GL_VENDOR = 0x1F00
GL_RENDERER = 0x1F01
GL_VERSION = 0x1F02
SM_REMOTESESSION = 0x1000
SM_CMONITORS = 80
PFD_TYPE_RGBA = 0
PFD_MAIN_PLANE = 0
PFD_DOUBLEBUFFER = 0x00000001
PFD_DRAW_TO_WINDOW = 0x00000004
PFD_SUPPORT_OPENGL = 0x00000020


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


class WNDCLASSW(ctypes.Structure):
    _fields_ = [
        ("style", wintypes.UINT),
        ("lpfnWndProc", WNDPROC),
        ("cbClsExtra", ctypes.c_int),
        ("cbWndExtra", ctypes.c_int),
        ("hInstance", HINSTANCE),
        ("hIcon", HICON),
        ("hCursor", HCURSOR),
        ("hbrBackground", HBRUSH),
        ("lpszMenuName", wintypes.LPCWSTR),
        ("lpszClassName", wintypes.LPCWSTR),
    ]


def _decode_gl_string(ptr):
    if not ptr:
        return "None"
    return ctypes.cast(ptr, ctypes.c_char_p).value.decode("utf-8", errors="replace")


def _print_session_details():
    user32 = ctypes.WinDLL("user32", use_last_error=True)
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    current_pid = os.getpid()
    current_session = wintypes.DWORD()
    kernel32.ProcessIdToSessionId(current_pid, ctypes.byref(current_session))
    active_console = kernel32.WTSGetActiveConsoleSessionId()

    print("=== System ===")
    print(f"Python: {sys.version.split()[0]} ({sys.executable})")
    print(f"Platform: {platform.platform()}")
    print(f"Machine: {platform.machine()}")
    print("=== Session ===")
    print(f"SESSIONNAME env: {os.environ.get('SESSIONNAME', '<unset>')}")
    print(f"Remote session (SM_REMOTESESSION): {bool(user32.GetSystemMetrics(SM_REMOTESESSION))}")
    print(f"Process Session ID: {current_session.value}")
    print(f"Active Console Session ID: {active_console}")
    print(f"Monitors detected: {user32.GetSystemMetrics(SM_CMONITORS)}")
    print("=== GPU preference env ===")
    print(f"CUDA_VISIBLE_DEVICES: {os.environ.get('CUDA_VISIBLE_DEVICES', '<unset>')}")
    print(f"__NV_PRIME_RENDER_OFFLOAD: {os.environ.get('__NV_PRIME_RENDER_OFFLOAD', '<unset>')}")
    print(f"__GLX_VENDOR_LIBRARY_NAME: {os.environ.get('__GLX_VENDOR_LIBRARY_NAME', '<unset>')}")


def _create_gl_context_and_query():
    user32 = ctypes.WinDLL("user32", use_last_error=True)
    gdi32 = ctypes.WinDLL("gdi32", use_last_error=True)
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    opengl32 = ctypes.WinDLL("opengl32", use_last_error=True)

    user32.DefWindowProcW.restype = LRESULT
    user32.DefWindowProcW.argtypes = [wintypes.HWND, wintypes.UINT, WPARAM, LPARAM]
    user32.RegisterClassW.restype = wintypes.ATOM
    user32.RegisterClassW.argtypes = [ctypes.POINTER(WNDCLASSW)]
    user32.CreateWindowExW.restype = wintypes.HWND
    user32.CreateWindowExW.argtypes = [
        wintypes.DWORD,
        wintypes.LPCWSTR,
        wintypes.LPCWSTR,
        wintypes.DWORD,
        ctypes.c_int,
        ctypes.c_int,
        ctypes.c_int,
        ctypes.c_int,
        wintypes.HWND,
        wintypes.HMENU,
        HINSTANCE,
        wintypes.LPVOID,
    ]
    user32.GetDC.restype = wintypes.HDC
    user32.GetDC.argtypes = [wintypes.HWND]
    user32.ReleaseDC.restype = ctypes.c_int
    user32.ReleaseDC.argtypes = [wintypes.HWND, wintypes.HDC]
    user32.DestroyWindow.restype = wintypes.BOOL
    user32.DestroyWindow.argtypes = [wintypes.HWND]
    user32.UnregisterClassW.restype = wintypes.BOOL
    user32.UnregisterClassW.argtypes = [wintypes.LPCWSTR, HINSTANCE]

    gdi32.ChoosePixelFormat.restype = ctypes.c_int
    gdi32.ChoosePixelFormat.argtypes = [wintypes.HDC, ctypes.POINTER(PIXELFORMATDESCRIPTOR)]
    gdi32.SetPixelFormat.restype = wintypes.BOOL
    gdi32.SetPixelFormat.argtypes = [wintypes.HDC, ctypes.c_int, ctypes.POINTER(PIXELFORMATDESCRIPTOR)]

    opengl32.wglCreateContext.restype = wintypes.HANDLE
    opengl32.wglCreateContext.argtypes = [wintypes.HDC]
    opengl32.wglMakeCurrent.restype = wintypes.BOOL
    opengl32.wglMakeCurrent.argtypes = [wintypes.HDC, wintypes.HANDLE]
    opengl32.wglDeleteContext.restype = wintypes.BOOL
    opengl32.wglDeleteContext.argtypes = [wintypes.HANDLE]
    kernel32.GetModuleHandleW.restype = HMODULE
    kernel32.GetModuleHandleW.argtypes = [wintypes.LPCWSTR]
    kernel32.GetModuleFileNameW.restype = wintypes.DWORD
    kernel32.GetModuleFileNameW.argtypes = [HMODULE, wintypes.LPWSTR, wintypes.DWORD]

    @WNDPROC
    def wnd_proc(hwnd, msg, wparam, lparam):
        return user32.DefWindowProcW(hwnd, msg, wparam, lparam)
    class_name = "OpenGLDiagWindow"
    h_instance = kernel32.GetModuleHandleW(None)
    wc = WNDCLASSW()
    wc.lpfnWndProc = wnd_proc
    wc.hInstance = h_instance
    wc.lpszClassName = class_name
    atom = user32.RegisterClassW(ctypes.byref(wc))
    if not atom:
        raise ctypes.WinError(ctypes.get_last_error())

    hwnd = user32.CreateWindowExW(
        0,
        class_name,
        "diag",
        0,
        0,
        0,
        8,
        8,
        0,
        None,
        h_instance,
        None,
    )
    if not hwnd:
        raise ctypes.WinError(ctypes.get_last_error())

    hdc = user32.GetDC(hwnd)
    if not hdc:
        raise ctypes.WinError(ctypes.get_last_error())

    pfd = PIXELFORMATDESCRIPTOR()
    pfd.nSize = ctypes.sizeof(PIXELFORMATDESCRIPTOR)
    pfd.nVersion = 1
    pfd.dwFlags = PFD_DRAW_TO_WINDOW | PFD_SUPPORT_OPENGL | PFD_DOUBLEBUFFER
    pfd.iPixelType = PFD_TYPE_RGBA
    pfd.cColorBits = 24
    pfd.cDepthBits = 24
    pfd.iLayerType = PFD_MAIN_PLANE

    pixel_format = gdi32.ChoosePixelFormat(hdc, ctypes.byref(pfd))
    if not pixel_format:
        raise ctypes.WinError(ctypes.get_last_error())
    if not gdi32.SetPixelFormat(hdc, pixel_format, ctypes.byref(pfd)):
        raise ctypes.WinError(ctypes.get_last_error())

    hglrc = opengl32.wglCreateContext(hdc)
    if not hglrc:
        raise ctypes.WinError(ctypes.get_last_error())
    if not opengl32.wglMakeCurrent(hdc, hglrc):
        raise ctypes.WinError(ctypes.get_last_error())

    opengl32.glGetString.restype = ctypes.c_void_p
    vendor = _decode_gl_string(opengl32.glGetString(GL_VENDOR))
    renderer = _decode_gl_string(opengl32.glGetString(GL_RENDERER))
    version = _decode_gl_string(opengl32.glGetString(GL_VERSION))
    module_path = ctypes.create_unicode_buffer(260)
    hmod = kernel32.GetModuleHandleW("opengl32.dll")
    module_len = kernel32.GetModuleFileNameW(hmod, module_path, 260) if hmod else 0

    print("=== OpenGL (raw WGL context) ===")
    print(f"GL_VENDOR: {vendor}")
    print(f"GL_RENDERER: {renderer}")
    print(f"GL_VERSION: {version}")
    print(f"Loaded opengl32.dll: {module_path.value if module_len else '<unavailable>'}")

    opengl32.wglMakeCurrent(None, None)
    opengl32.wglDeleteContext(hglrc)
    user32.ReleaseDC(hwnd, hdc)
    user32.DestroyWindow(hwnd)
    user32.UnregisterClassW(class_name, h_instance)


if __name__ == "__main__":
    _print_session_details()
    try:
        _create_gl_context_and_query()
    except Exception as exc:
        print("=== OpenGL diagnostic failed ===")
        print(f"{type(exc).__name__}: {exc}")
        traceback.print_exc()
