[app]

# Application title and package
title = Sanity Fear and Madness
package.name = sanityfearandmadness
package.domain = org.fsm

# Source
source.dir = .
source.include_exts = py,png,jpg,kv,atlas
source.exclude_dirs = __pycache__, .git, tests, .venv, .venv_buildozer_inspect, .github, .claude

version = 2.0

# Requirements: KivyMD 1.2.0 bundles a compatible Kivy version
requirements = python3,kivy==2.3.0,kivymd==1.2.0

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
