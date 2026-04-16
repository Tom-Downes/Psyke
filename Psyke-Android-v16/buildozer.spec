[app]

# Application title and package
title = Psyke
package.name = psyke
package.domain = org.fsm

# Source
source.dir = .
source.include_exts = py,png,jpg,kv,atlas,json
icon.filename = %(source.dir)s/icon.png
android.presplash_lottie = %(source.dir)s/psyke_splash.json
android.presplash_color = #10131a
source.exclude_dirs = __pycache__, .git, tests, .venv, .venv_buildozer_inspect, .github, .claude, .push-worktree, .release_tmp, .release_tmp2

version = 16.0.0

# Android requires a monotonically increasing integer versionCode for updates.
# GitHub Actions overwrites this per-run (see .github/workflows/build-apk.yml).
android.numeric_version = 160000

# Requirements: Kivy + KivyMD UI stack and Plyer (Android file chooser)
requirements = python3,kivy==2.3.0,kivymd==1.2.0,plyer,pyjnius

# Orientation — portrait only on mobile
orientation = portrait
fullscreen = 0

# Android target
android.api = 35
android.minapi = 26
android.archs = arm64-v8a, armeabi-v7a

# CI/automation: accept Android SDK licenses non-interactively (GitHub Actions).
android.accept_sdk_license = True

# Soft keyboard: resize mode so ScrollViews move up correctly
android.manifest.activity_attributes = android:windowSoftInputMode=adjustResize

# Permissions (none required for local JSON save)
# android.permissions = WRITE_EXTERNAL_STORAGE

# Hook: patches p4a lottie.xml template to set lottie_loop=false
# so splash intro plays once then spinner runs until app loads
p4a.hook = %(source.dir)s/p4a_hook.py

[buildozer]
log_level = 2
warn_on_root = 1
