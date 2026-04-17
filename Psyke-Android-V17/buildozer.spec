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

# Keep the Android recipe ahead of the UI deps so p4a resolves the
# Android-specific bindings correctly. Pin both Python recipes so
# p4a develop doesn't silently jump to 3.14, which broke pyjnius in CI.
requirements = python3,android,kivy==2.3.0,kivymd==1.2.0,plyer,pyjnius

orientation = portrait
fullscreen = 0

android.api = 35
android.minapi = 26
android.ndk_api = 26
# CI can override this to a patched local python-for-android checkout.
p4a.source_dir =
android.archs = arm64-v8a,armeabi-v7a
android.accept_sdk_license = True
android.release_artifact = apk
android.manifest.activity_attributes = android:windowSoftInputMode=adjustResize android:configChanges="keyboard|keyboardHidden|orientation|screenSize|uiMode"
p4a.hook = p4a_hook.py


[buildozer]
log_level = 2
warn_on_root = 1
