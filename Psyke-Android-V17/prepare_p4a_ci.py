#!/usr/bin/env python3
"""Clone python-for-android master and apply 16 KB page-size patches."""
from __future__ import annotations

import argparse
import shutil
import subprocess
from pathlib import Path


P4A_URL = "https://github.com/kivy/python-for-android.git"


def run(*args: str, cwd: Path | None = None) -> None:
    print(f"[prepare_p4a] > {' '.join(args)}")
    subprocess.run(args, cwd=cwd, check=True)


def append_once(path: Path, line: str, label: str) -> None:
    text = path.read_text(encoding="utf-8")
    if line in text:
        print(f"[prepare_p4a] {label}: already patched")
        return
    if not text.endswith("\n"):
        text += "\n"
    path.write_text(text + line + "\n", encoding="utf-8")
    print(f"[prepare_p4a] {label}: patched")


def replace_once(path: Path, old: str, new: str, label: str) -> None:
    text = path.read_text(encoding="utf-8")
    if new in text:
        print(f"[prepare_p4a] {label}: already patched")
        return
    if old not in text:
        raise RuntimeError(f"{label}: marker not found in {path}")
    path.write_text(text.replace(old, new, 1), encoding="utf-8")
    print(f"[prepare_p4a] {label}: patched")


def replace_first_match(path: Path, replacements: list[tuple[str, str]], label: str) -> None:
    text = path.read_text(encoding="utf-8")
    for _old, new in replacements:
        if new in text:
            print(f"[prepare_p4a] {label}: already patched")
            return
    for old, new in replacements:
        if old in text:
            path.write_text(text.replace(old, new, 1), encoding="utf-8")
            print(f"[prepare_p4a] {label}: patched")
            return
    raise RuntimeError(f"{label}: marker not found in {path}")


def clone_p4a(dest: Path, branch: str) -> None:
    if dest.exists():
        shutil.rmtree(dest)
    dest.parent.mkdir(parents=True, exist_ok=True)
    run("git", "clone", "--depth", "1", "--branch", branch, P4A_URL, str(dest))


def patch_lottie(p4a_dir: Path) -> None:
    lottie = (
        p4a_dir
        / "pythonforandroid"
        / "bootstraps"
        / "common"
        / "build"
        / "templates"
        / "lottie.xml"
    )
    if not lottie.exists():
        print(f"[prepare_p4a] lottie.xml not found at {lottie}, skipping")
        return
    text = lottie.read_text(encoding="utf-8")
    text = text.replace('lottie_loop="true"', 'lottie_loop="false"')
    if 'lottie_clipToCompositionBounds' not in text:
        text = text.replace(
            'app:lottie_loop="false"',
            'app:lottie_loop="false"\n        app:lottie_clipToCompositionBounds="false"',
        )
    if 'clipChildren' not in text:
        text = text.replace(
            'android:layout_height="fill_parent"',
            'android:layout_height="fill_parent"\n    android:clipChildren="false"',
        )
    lottie.write_text(text, encoding="utf-8")
    print(f"[prepare_p4a] lottie.xml patched")


def patch_sdl_page_size_support(p4a_dir: Path) -> None:
    application_mk = (
        p4a_dir
        / "pythonforandroid"
        / "bootstraps"
        / "_sdl_common"
        / "build"
        / "jni"
        / "Application.mk"
    )
    append_once(
        application_mk,
        "APP_SUPPORT_FLEXIBLE_PAGE_SIZES := true",
        "sdl flexible page size support",
    )

    sdl2_recipe = p4a_dir / "pythonforandroid" / "recipes" / "sdl2" / "__init__.py"
    if sdl2_recipe.exists():
        replace_once(
            sdl2_recipe,
            '                "NDK_DEBUG=" + ("1" if self.ctx.build_as_debuggable else "0"),\n'
            "                _env=env\n",
            '                "NDK_DEBUG=" + ("1" if self.ctx.build_as_debuggable else "0"),\n'
            '                "APP_SUPPORT_FLEXIBLE_PAGE_SIZES=true",\n'
            '                "APPLICATION_ADDITIONAL_LDFLAGS=-Wl,-z,max-page-size=16384",\n'
            "                _env=env\n",
            "sdl2 ndk-build flags",
        )

    sdl3_recipe = p4a_dir / "pythonforandroid" / "recipes" / "sdl3" / "__init__.py"
    if sdl3_recipe.exists():
        replace_first_match(
            sdl3_recipe,
            [
                (
                    '                "NDK_DEBUG=" + ("1" if self.ctx.build_as_debuggable else "0"),\n'
                    "                _env=env,\n",
                    '                "NDK_DEBUG=" + ("1" if self.ctx.build_as_debuggable else "0"),\n'
                    '                "APP_SUPPORT_FLEXIBLE_PAGE_SIZES=true",\n'
                    '                "APPLICATION_ADDITIONAL_LDFLAGS=-Wl,-z,max-page-size=16384",\n'
                    "                _env=env,\n",
                ),
                (
                    '                "NDK_DEBUG=" + ("1" if self.ctx.build_as_debuggable else "0"),\n'
                    "                _env=env\n",
                    '                "NDK_DEBUG=" + ("1" if self.ctx.build_as_debuggable else "0"),\n'
                    '                "APP_SUPPORT_FLEXIBLE_PAGE_SIZES=true",\n'
                    '                "APPLICATION_ADDITIONAL_LDFLAGS=-Wl,-z,max-page-size=16384",\n'
                    "                _env=env\n",
                ),
            ],
            "sdl3 ndk-build flags",
        )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-dir", required=True)
    parser.add_argument("--branch", default="master")
    args = parser.parse_args()

    p4a_dir = Path(args.source_dir).resolve()
    clone_p4a(p4a_dir, args.branch)
    patch_lottie(p4a_dir)
    patch_sdl_page_size_support(p4a_dir)
    print(f"[prepare_p4a] ready: {p4a_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
