"""
p4a build hook — patches Lottie presplash template to disable looping.

Targets specific known paths instead of recursive glob to avoid
scanning the entire Android SDK/NDK cache.
"""
import os


def _patch_lottie(buildozer):
    # p4a installs to <app_dir>/.buildozer/android/platform/python-for-android/
    # We get the app dir from the hook context or fall back to cwd.
    try:
        app_dir = buildozer.root_dir
    except Exception:
        app_dir = os.getcwd()

    targets = [
        # Template file (used to generate the layout)
        os.path.join(
            app_dir,
            ".buildozer", "android", "platform", "python-for-android",
            "pythonforandroid", "bootstraps", "common", "build",
            "templates", "lottie.xml"
        ),
        # Rendered layout file (after bootstrap setup, before gradle)
        os.path.join(
            app_dir,
            ".buildozer", "android", "platform",
            "build-arm64-v8a_armeabi-v7a", "build",
            "bootstrap_builds", "sdl2", "src", "main", "res",
            "layout", "lottie.xml"
        ),
    ]

    patched = 0
    for path in targets:
        if not os.path.exists(path):
            print(f"[p4a_hook] Not found (skipping): {path}")
            continue
        try:
            with open(path) as f:
                content = f.read()
            if 'lottie_loop="true"' in content:
                content = content.replace('lottie_loop="true"', 'lottie_loop="false"')
                with open(path, "w") as f:
                    f.write(content)
                print(f"[p4a_hook] Patched lottie_loop -> false: {path}")
                patched += 1
            else:
                print(f"[p4a_hook] Already patched or not found in: {path}")
        except Exception as e:
            print(f"[p4a_hook] Error patching {path}: {e}")

    if patched == 0:
        print("[p4a_hook] WARNING: lottie_loop not patched in any target file")


def pre_build(buildozer):
    _patch_lottie(buildozer)


def before_apk_build(buildozer):
    _patch_lottie(buildozer)


def before_aab_build(buildozer):
    _patch_lottie(buildozer)
