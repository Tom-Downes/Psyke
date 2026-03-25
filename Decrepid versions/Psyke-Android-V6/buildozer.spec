[app]

# Application title and package
title = Psyke
package.name = psyke
package.domain = org.fsm

# Source
source.dir = .
source.include_exts = py,png,jpg,kv,atlas
icon.filename = %(source.dir)s/icon.png
android.presplash_filename = %(source.dir)s/icon.png
android.presplash_color = #111111
source.exclude_dirs = __pycache__, .git, tests, .venv, .venv_buildozer_inspect, .github, .claude, .push-worktree, .release_tmp, .release_tmp2

version = 6.0.0

# Android requires a monotonically increasing integer versionCode for updates.
# GitHub Actions overwrites this per-run (see .github/workflows/build-apk.yml).
android.numeric_version = 60000

# Requirements: Kivy + KivyMD UI stack and Plyer (Android file chooser)
requirements = python3,kivy==2.3.0,kivymd==1.2.0,plyer

# Orientation — portrait only on mobile
orientation = portrait
fullscreen = 0

# Android target
android.api = 33
android.minapi = 26
android.archs = arm64-v8a, armeabi-v7a

# CI/automation: accept Android SDK licenses non-interactively (GitHub Actions).
android.accept_sdk_license = True

# Soft keyboard: resize mode so ScrollViews move up correctly
android.manifest.activity_attributes = android:windowSoftInputMode=adjustResize

# Permissions (none required for local JSON save)
# android.permissions = WRITE_EXTERNAL_STORAGE

[buildozer]
log_level = 2
warn_on_root = 1
