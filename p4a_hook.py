"""
p4a build hook — patches Lottie presplash template:
  - disables looping (lottie_loop false)
  - disables clip-to-composition-bounds (fixes spinner clipping on device)

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

            changed = False

            if 'lottie_loop="true"' in content:
                content = content.replace('lottie_loop="true"', 'lottie_loop="false"')
                print(f"[p4a_hook] Patched lottie_loop -> false: {path}")
                changed = True
            else:
                print(f"[p4a_hook] lottie_loop already patched or not found in: {path}")

            if 'lottie_clipToCompositionBounds' not in content:
                content = content.replace(
                    'lottie_loop="false"',
                    'lottie_loop="false"\n        app:lottie_clipToCompositionBounds="false"'
                )
                print(f"[p4a_hook] Patched lottie_clipToCompositionBounds -> false: {path}")
                changed = True
            else:
                print(f"[p4a_hook] lottie_clipToCompositionBounds already present in: {path}")

            if changed:
                with open(path, "w") as f:
                    f.write(content)
                patched += 1

        except Exception as e:
            print(f"[p4a_hook] Error patching {path}: {e}")

    if patched == 0:
        print("[p4a_hook] WARNING: no patches applied to any target file")


def pre_build(buildozer):
    _patch_lottie(buildozer)


def before_apk_build(buildozer):
    _patch_lottie(buildozer)


def before_aab_build(buildozer):
    _patch_lottie(buildozer)
