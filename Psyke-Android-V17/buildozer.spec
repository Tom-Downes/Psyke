[app]
title = Psyke
package.name = psyke
package.domain = org.fsm

source.dir = .
source.include_exts = py,png,jpg,kv,atlas,json
source.exclude_dirs = __pycache__,.git,tests,.venv,.github,.claude,.idea,.vscode

icon.filename = %(source.dir)s/icon.png
android.presplash_lottie = %(source.dir)s/psyke_splash.json
android.presplash_color = #10131a

version = 17.5.0
android.numeric_version = 170500

# android listed first so p4a picks up Android-specific bindings
requirements = python3,android,kivy==2.3.0,kivymd==1.2.0,plyer,pyjnius

orientation = portrait
fullscreen = 0

android.api = 35
android.minapi = 26
android.ndk_api = 26
# Build with a modern NDK so native libs default to 16 KB page-size support.
android.ndk = 29
# Use the current p4a branch for modern Play/NDK compatibility fixes.
p4a.branch = develop
android.archs = arm64-v8a,armeabi-v7a
android.accept_sdk_license = True
android.release_artifact = apk
android.manifest.activity_attributes = android:windowSoftInputMode=adjustResize android:configChanges="keyboard|keyboardHidden|orientation|screenSize|uiMode"
p4a.hook = p4a_hook.py


[buildozer]
log_level = 2
warn_on_root = 1
