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
                    'app:lottie_loop="false"',
                    'app:lottie_loop="false"\n        app:lottie_clipToCompositionBounds="false"'
                )
                print(f"[p4a_hook] Patched lottie_clipToCompositionBounds -> false: {path}")
                changed = True
            else:
                print(f"[p4a_hook] lottie_clipToCompositionBounds already present in: {path}")

            if 'clipChildren' not in content:
                content = content.replace(
                    'android:layout_height="fill_parent"',
                    'android:layout_height="fill_parent"\n    android:clipChildren="false"'
                )
                print(f"[p4a_hook] Patched clipChildren -> false: {path}")
                changed = True
            else:
                print(f"[p4a_hook] clipChildren already present in: {path}")

            if changed:
                with open(path, "w") as f:
                    f.write(content)
                patched += 1

        except Exception as e:
            print(f"[p4a_hook] Error patching {path}: {e}")

    if patched == 0:
        print("[p4a_hook] WARNING: no patches applied to any target file")


def _patch_pyproject_recipes(buildozer):
    try:
        app_dir = buildozer.root_dir
    except Exception:
        app_dir = os.getcwd()

    recipe_fixes = [
        (
            os.path.join(
                app_dir,
                ".buildozer", "android", "platform", "python-for-android",
                "pythonforandroid", "recipes", "pyjnius", "__init__.py",
            ),
            "class PyjniusRecipe(PyProjectRecipe):",
            'hostpython_prerequisites = ["Cython<3.2"]',
            'hostpython_prerequisites = ["Cython<3.2", "wheel"]',
        ),
        (
            os.path.join(
                app_dir,
                ".buildozer", "android", "platform", "python-for-android",
                "pythonforandroid", "recipes", "kivy", "__init__.py",
            ),
            "class KivyRecipe(PyProjectRecipe):",
            'hostpython_prerequisites = ["cython>=0.29.1,<=3.0.12"]',
            'hostpython_prerequisites = ["cython>=0.29.1,<=3.0.12", "wheel"]',
        ),
    ]

    for path, class_marker, prereq_old, prereq_new in recipe_fixes:
        if not os.path.exists(path):
            print(f"[p4a_hook] Recipe patch target not found (skipping): {path}")
            continue

        try:
            with open(path, encoding="utf-8") as f:
                content = f.read()

            changed = False

            if "--no-isolation" not in content and class_marker in content:
                content = content.replace(
                    class_marker,
                    class_marker + "\n    extra_build_args = ['--no-isolation']",
                    1,
                )
                print(f"[p4a_hook] Enabled --no-isolation for recipe: {path}")
                changed = True
            else:
                print(f"[p4a_hook] --no-isolation already present or class missing in: {path}")

            if '"wheel"' not in content and prereq_old in content:
                content = content.replace(prereq_old, prereq_new, 1)
                print(f"[p4a_hook] Added wheel to hostpython prerequisites: {path}")
                changed = True
            else:
                print(f"[p4a_hook] wheel already present or prerequisites not found in: {path}")

            if changed:
                with open(path, "w", encoding="utf-8") as f:
                    f.write(content)

        except Exception as e:
            print(f"[p4a_hook] Error patching recipe {path}: {e}")


def pre_build(buildozer):
    _patch_pyproject_recipes(buildozer)
    _patch_lottie(buildozer)


def before_apk_build(buildozer):
    _patch_pyproject_recipes(buildozer)
    _patch_lottie(buildozer)


def before_aab_build(buildozer):
    _patch_pyproject_recipes(buildozer)
    _patch_lottie(buildozer)
