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
