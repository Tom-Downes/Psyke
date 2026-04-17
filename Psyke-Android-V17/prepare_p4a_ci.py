#!/usr/bin/env python3
from __future__ import annotations

import argparse
import shutil
import subprocess
from pathlib import Path


P4A_URL = "https://github.com/kivy/python-for-android.git"


def run(*args: str, cwd: Path | None = None) -> None:
    print(f"[prepare_p4a] > {' '.join(args)}")
    subprocess.run(args, cwd=cwd, check=True)


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


def insert_after(path: Path, marker: str, addition: str, label: str) -> None:
    text = path.read_text(encoding="utf-8")
    if addition.strip() in text:
        print(f"[prepare_p4a] {label}: already patched")
        return
    if marker not in text:
        raise RuntimeError(f"{label}: marker not found in {path}")
    path.write_text(text.replace(marker, marker + addition, 1), encoding="utf-8")
    print(f"[prepare_p4a] {label}: patched")


def append_once(path: Path, line: str, label: str) -> None:
    text = path.read_text(encoding="utf-8")
    if line in text:
        print(f"[prepare_p4a] {label}: already patched")
        return
    if not text.endswith("\n"):
        text += "\n"
    text += line + "\n"
    path.write_text(text, encoding="utf-8")
    print(f"[prepare_p4a] {label}: patched")


def clone_p4a(dest: Path, branch: str) -> None:
    if dest.exists():
        shutil.rmtree(dest)
    dest.parent.mkdir(parents=True, exist_ok=True)
    run("git", "clone", "--depth", "1", "--branch", branch, P4A_URL, str(dest))


def patch_pyproject_recipes(p4a_dir: Path) -> None:
    pyjnius = p4a_dir / "pythonforandroid" / "recipes" / "pyjnius" / "__init__.py"
    android = p4a_dir / "pythonforandroid" / "recipes" / "android" / "__init__.py"
    kivy = p4a_dir / "pythonforandroid" / "recipes" / "kivy" / "__init__.py"

    insert_after(
        pyjnius,
        "class PyjniusRecipe(PyProjectRecipe):\n",
        "    extra_build_args = ['--no-isolation']\n",
        "pyjnius no-isolation",
    )
    replace_once(
        pyjnius,
        '    hostpython_prerequisites = ["Cython<3.2"]\n',
        '    hostpython_prerequisites = ["Cython<3.2", "wheel"]\n',
        "pyjnius hostpython prerequisites",
    )

    insert_after(
        android,
        "class AndroidRecipe(IncludedFilesBehaviour, PyProjectRecipe):\n",
        "    extra_build_args = ['--no-isolation']\n",
        "android no-isolation",
    )
    replace_once(
        android,
        '    hostpython_prerequisites = ["Cython>=0.29,<3.1"]\n',
        '    hostpython_prerequisites = ["Cython>=0.29,<3.1", "wheel"]\n',
        "android hostpython prerequisites",
    )

    insert_after(
        kivy,
        "class KivyRecipe(PyProjectRecipe):\n",
        "    extra_build_args = ['--no-isolation']\n",
        "kivy no-isolation",
    )
    replace_once(
        kivy,
        '    hostpython_prerequisites = ["cython>=0.29.1,<=3.0.12"]\n',
        '    hostpython_prerequisites = ["cython>=0.29.1,<=3.0.12", "wheel"]\n',
        "kivy hostpython prerequisites",
    )


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
    parser = argparse.ArgumentParser(description="Clone and patch python-for-android for CI builds.")
    parser.add_argument("--source-dir", required=True, help="Destination directory for the patched p4a checkout.")
    parser.add_argument("--branch", default="develop", help="python-for-android git branch to clone.")
    args = parser.parse_args()

    p4a_dir = Path(args.source_dir).resolve()
    clone_p4a(p4a_dir, args.branch)
    patch_pyproject_recipes(p4a_dir)
    patch_sdl_page_size_support(p4a_dir)
    print(f"[prepare_p4a] ready: {p4a_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
