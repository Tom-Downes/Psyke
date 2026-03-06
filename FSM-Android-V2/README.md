# FSM (Android v2) - Sanity, Fear & Madness Tracker

Android + desktop companion app (Kivy/KivyMD) for tracking **Sanity**, **Fears** (with desensitization), **Madness**, **Wounds**, and **Spells**.

This repo targets **rules + numbers parity** with the desktop reference script `FSM-6.py` (source of truth). See `DEPLOYMENT_PLAN_2.md` for parity notes.

## Important features (and how I use them in Curse of Strahd)

- **Sanity pool + threshold events** - Track current/max sanity and automatically handle "crossed a threshold" moments. I use this whenever the party hits major horror beats (visions, discoveries, Ravenloft moments) so consequences are fast and consistent.
- **Fear encounters + desensitization ladder** - Each fear has a "rung" that can improve with exposure. I use this for character-specific triggers (mists, blood, confinement, undead) to make fear feel like a system instead of a vibe.
- **Madness tables (short/long/indefinite)** - Named d20 results with durations and quick rules text. I roll straight from the app when sanity drops past a threshold or when I need an immediate roleplay complication.
- **Wounds + wound encounter flow** - Track lingering injuries and resolve wound events cleanly. I use this when combat turns brutal (big crits, nasty drops to 0, or whenever I want survival-horror pressure without adding tons of bookkeeping).
- **Spells tab (quick reference/tracking)** - Keeps spell info and state close at hand. I use it to speed up combat and reduce "wait, what does that do again?" moments.
- **Local saves (JSON)** - Persists between sessions with a desktop-compatible schema (`save_v6.json`). I keep one save per campaign/party so we can resume instantly next session.

## Project layout

- `main.py` - app entry point (UI shell, dialogs, navigation)
- `models.py` - rules logic, tables, and persistence (FSM-6 parity)
- `tab_fears.py`, `tab_sanity.py`, `tab_wounds.py`, `tab_spells.py` - tab UIs + flows
- `widgets.py` - reusable UI widgets
- `theme.py` - palette + styling values
- `.github/workflows/build-apk.yml` - GitHub Actions debug APK build
- `buildozer.spec` - Buildozer / python-for-android configuration

## Run on desktop (dev)

Prereqs: Python 3.11+

```bash
python -m venv .venv
# Windows: .\.venv\Scripts\activate
# macOS/Linux: source .venv/bin/activate
pip install "kivy==2.3.0" "kivymd==1.2.0"
python main.py
```

If `pip install kivy` fails, follow the official Kivy install docs for your OS (Kivy has platform-specific wheels/deps).

## Build for Android

- **GitHub Actions**: Actions -> "Build APK" -> Run workflow (APK is uploaded as artifact `apk`).
- **Local (Buildozer, Linux/WSL2)**:

```bash
pip install "Cython<3" pexpect "buildozer==1.5.0"
buildozer android debug
```

## Saves / data

- Save filename: `save_v6.json`
- Kivy location: `App.user_data_dir/save_v6.json`

## License

No license file is included yet. Add a `LICENSE` file before publishing broadly.
