# FSM Android Deployment Plan
**Base: FSM-6.py (Desktop)**
**Target: Kivy / KivyMD / Buildozer — Android**

---

## Overview

This document maps every feature in FSM-6 to its Android implementation strategy.
The goal is feature parity with the desktop app while adapting the UI to a phone
screen. All game rules, data, and logic must behave identically. The visual style
should feel related to the desktop — same dark theme, same color palette — but
the layout is rebuilt from scratch for portrait phone use.

The current FSM-Android code is an older partial port (pre-desensitization system,
old madness tables, old Stage naming). This plan treats FSM-6 as the single source
of truth and documents everything that must exist in the new version.

---

## 1. Feature Inventory (FSM-6 Reference)

### 1a. Character State
| Feature | Desktop Location | Status |
|---|---|---|
| Character name (text field) | Header | Ported |
| WIS score + modifier | Header chip | Ported |
| CON score + modifier | Header chip | Ported |
| Sanity pool (max = 15 + WIS) | Header + bar | Ported |
| Current sanity | Bar + label | Ported |
| Exhaustion level (0–6 pips) | Header row 2 | Ported |
| Session timer | Header row 2 | Ported |
| Undo stack (50 snapshots) | Header undo btn | Ported |
| Session log (dialog) | Header log btn | Ported |
| Auto-save on every change | Background | Ported |

### 1b. Fear System
| Feature | Desktop Location | Status |
|---|---|---|
| Fear list (add / remove) | Fears tab | Ported |
| Random fear suggestion (dice btn) | Fears tab | Ported |
| Severity level per fear (1–4) | Left tracker | Ported — but uses old "Stage" naming |
| **Severity renamed** (Low/Moderate/High/Extreme) | Severity tracker | **MISSING — needs rename** |
| Fear encounter (WIS save vs DC) | Encounter card | Ported |
| **Desensitization rung per fear (1–4)** | Right tracker | **MISSING — not implemented** |
| **Desens DC auto-fill** (rung → DC 16/14/12/10) | DC field | **MISSING** |
| **Desens effects panel** | Right panel | **MISSING** |
| **Desens tracker buttons (4 rungs)** | Right tracker | **MISSING** |
| Confront (Push Through) | Roll panel | Ported — but missing desens +1 |
| **Confront → desens rung +1** | Logic | **MISSING** |
| Avoid | Roll panel | Ported — but missing desens −1 |
| **Avoid → desens rung −1** | Logic | **MISSING** |
| Avoid → severity +1 | Logic | Ported |
| **Extreme Severity: +1 Exhaustion on encounter start** | Logic | **MISSING** |
| **Extreme Severity: Avoid → add random new fear** | Logic | **MISSING — currently triggers only at stage 4 avoid** |
| Severity effects panel (per stage) | Right panel | Ported |
| Fear rules expandable | Bottom of tab | Ported — needs desens content |

### 1c. Sanity System
| Feature | Desktop Location | Status |
|---|---|---|
| Quick lose buttons (−1/−2/−3/−5/−10) | Sanity tab | Ported |
| Quick recover buttons (+1/+2/+3/+5/+10) | Sanity tab | Ported |
| DM recovery (1d4 / 2d4) | Sanity tab | Ported |
| Restore to max | Sanity tab | Ported |
| Sanity threshold triggers (75/50/25/0%) | Logic | Ported |
| Threshold → madness auto-added | Logic | Ported |

### 1d. Madness System
| Feature | Desktop Location | Status |
|---|---|---|
| Short-term madness (roll table) | Sanity tab | **Needs update to D20 named table** |
| Long-term madness (roll table) | Sanity tab | **Needs update to D20 named table** |
| Indefinite madness (roll table) | Sanity tab | **Needs update to D20 named table** |
| Custom madness (text input) | Sanity tab | Ported |
| Active madness list | Sanity tab | Ported |
| Madness detail on tap | Sanity tab | Ported |
| Remove selected madness | Sanity tab | Ported |
| Madness banner (persistent top display) | Global header | Ported |
| Animated sanity bar (gradient + threshold marks) | Global | Ported |
| Madness rules expandable | Sanity tab | Ported |

### 1e. Wounds System
| Feature | Desktop Location | Status |
|---|---|---|
| Wound encounter (CON save, DC + damage input) | Wounds tab | Ported |
| Pass by 5+ / Pass / Fail / Fail by 5+ | Wounds tab | Ported |
| Add minor / major wound (custom or random) | Wounds tab | Ported |
| Minor wound list (tappable, with detail) | Wounds tab | Ported |
| Major wound list (tappable, with detail) | Wounds tab | Ported |
| Cure / Remove wound buttons | Wounds tab | Ported |
| Wound rules expandable | Wounds tab | Ported |

---

## 2. Architecture

Multi-file Kivy/KivyMD project. File structure mirrors the existing FSM-Android
layout but with corrected feature coverage:

```
FSM-Android-V2/
├── main.py          — App class, header, tab bar, global state, load/save
├── models.py        — All data models, tables, constants (port from FSM-6)
├── widgets.py       — SanityBar, MadnessBanner, ExhaustionWidget (canvas widgets)
├── tab_fears.py     — Fears tab (encounter, severity, desens, fear list, rules)
├── tab_sanity.py    — Sanity tab (lose/recover, madness management)
├── tab_wounds.py    — Wounds tab (encounter, wound lists)
├── ui_utils.py      — Shared layout components (BorderCard, AccentCard, etc.)
├── theme.py         — Color constants, dp helpers, KivyMD theme settings
├── buildozer.spec   — Build configuration
└── DEPLOYMENT_PLAN.md  — This file
```

**Key architectural rules:**
- No Tkinter imports anywhere
- All state lives in `SanityState` and `FearManager` on the `App` instance
- UI widgets read state from `App.get_running_app()` on refresh
- Undo always calls `app.undo_stack.push(app.state, app.fm)` before any mutation
- Auto-save after every state change via `app.save_manager.save(...)`
- `app.refresh_all()` propagates state to all visible widgets

---

## 3. UI Layout — Screen by Screen

### 3a. Global Layout (always visible, top to bottom)

```
┌─────────────────────────────────┐  88dp
│ [Character Name Field]  [log] [undo] │  Row 1 — 44dp
│ WIS 10 +0  CON 10 +0  [●●○○○○]  00:00 │  Row 2 — 30dp
├─────────────────────────────────┤  28dp   Sanity bar (gradient, threshold marks)
├─────────────────────────────────┤  52dp   Madness banner (pulse on threshold)
│ Sanity: 25 / 25                 │  18dp   Sanity label
├──────────┬──────────┬───────────┤  40dp   Tab bar
│  FEARS   │  SANITY  │  WOUNDS   │
├─────────────────────────────────┤   2dp   Colored separator line
│                                 │
│         [Active Tab Content]    │  fills remaining height (scrollable)
│                                 │
└─────────────────────────────────┘
```

**Changes vs desktop:**
- Desktop has a persistent sidebar — eliminated on mobile, tabs replace it
- Tab bar stays at the top (not bottom-nav) for visual continuity with the dark theme
- Header collapses two rows to 88dp total — already done in existing Android code
- Madness banner is 52dp instead of desktop's taller version — already done

---

### 3b. Fears Tab

The desktop Fears tab is a two-column layout with the fear list and encounter
on the left, and the severity/desens tracker + effects on the right. On mobile
everything stacks vertically in a scroll view.

**Stacking order (top to bottom):**

```
[FEAR ENCOUNTER CARD]
  — Selected fear label (dim until fear chosen)
  — DC field (auto-filled from desens DC, editable) + ENCOUNTER button
  — Roll panel (appears after encounter, 0dp when hidden):
      Roll result label + big number
      [Failed Save] [Passed]          (row 1)
      [Confront]    [Avoid]           (row 2)
      Pending label

[SEVERITY CARD]  (gold border)
  — 2×2 grid of severity cards:
      [Low Severity  1d4]  [Moderate Severity  2d4]
      [High Severity 3d4]  [Extreme Severity   4d4]

[SEVERITY EFFECTS CARD]  (gold accent)
  — Title: "Low Severity — Low Severity"
  — Dice line: "Fail → roll 1d4 | Pass → encounter ends"
  — Description text

[DESENSITIZATION TRACKER CARD]  (teal border)    ← NEW
  — Header: "DESENSITIZATION"
  — 4 rung buttons in a row:
      [Low Rung 1  DC 16] [Moderate Rung 2  DC 14]
      [High Rung 3  DC 12] [Extreme Rung 4  DC 10]
    (tappable to manually set; highlighted on active rung)

[DESENSITIZATION EFFECTS CARD]  (teal accent)    ← NEW
  — Title: "Low Desensitization — Rung 1"
  — DC label: "DC 16"
  — Description text

[ADD FEAR ROW]
  — Text field + [🎲 suggest] + [Add Fear]

[FEARS LIST CARD]  (gold border)
  — Header: "FEARS" + trash icon (removes selected)
  — List items:  FearName  ·  Severity  ·  Desensitization
    (tap to select; selected item highlighted)

[FEAR RULES]  (expandable section, gold accent)
```

**Design notes:**
- Tapping a fear from the list selects it, fills the encounter card context label,
  updates the severity selector and desens tracker to match that fear's current state,
  and auto-fills the DC field with the fear's current desens DC.
- The severity selector and desens tracker are both interactive — tapping a card
  immediately updates the fear's value and saves.
- The DC field is pre-filled but editable. DM can override before triggering.
- Roll panel is height=0/opacity=0 when hidden; animates open after ENCOUNTER.

---

### 3c. Sanity Tab

Desktop has a card with controls on the left; on mobile it's a single scrollable
column of cards. The layout from the existing Android code is already good here.

**Stacking order:**

```
[SANITY CARD]  (purple border)
  — "LOSE" label
  — [−1] [−2] [−3] [−5] [−10]     (5 equal-width buttons, red)
  — "RECOVER" label
  — [+1] [+2] [+3] [+5] [+10]     (5 equal-width buttons, green)
  — [DM +1d4]  [DM +2d4]  [Restore Max]   (third row)

[MADNESS CARD]  (purple border)
  — "MADNESS" header
  — Caption: auto-added at thresholds; roll or enter custom

  [SHORT-TERM CARD]  (gold-amber accent)
    — Title + "(1d10 minutes)"
    — [Roll Table]  [Custom effect text field]  [Add]

  [LONG-TERM CARD]  (orange accent)
    — Title + "(1d10 × 10 hours)"
    — [Roll Table]  [Custom effect text field]  [Add]

  [INDEFINITE CARD]  (red accent)
    — Title + "(Until cured)"
    — [Roll Table]  [Custom effect text field]  [Add]

  Divider

  "ACTIVE MADNESS" header
  — List items: madness name · type
    (tap to see full effect below)
  — Detail text area (full effect, roll range, timestamp)
  — [Remove Selected]

[MADNESS RULES]  (expandable section)
```

**Roll Table behavior (updated for D20 named system):**
When "Roll Table" is tapped, the model rolls 1d20 and looks up the named entry
(e.g. "Black Out", "Tell-Tale Heart"). The result snackbar shows the rolled number
and the name. The madness is added to the active list with name + full effect text.

---

### 3d. Wounds Tab

The existing Android wounds tab is largely correct. Keep the structure as-is.

**Stacking order:**

```
[WOUND ENCOUNTER CARD]  (blood-red border)
  — DC field + Damage field + [WOUND ENC] button
  — Roll panel (height=0 when hidden):
      Roll result label + verdict (PASS/FAIL etc.)
      [Pass 5+]  [Pass]
      [Fail]     [Fail 5+]
      Result label

[WOUNDS CARD]  (blood-red border)
  — "ADD WOUND" header
  — Description text field (blank = random)
  — [+ Minor]  [+ Major]
  — [Random Minor]  [Random Major]  (flat buttons)

  Divider (teal)
  "MINOR WOUNDS (N)" header + "Long Rest cures" hint
  — Minor wound list (tappable)
  — Detail text
  — [Cure]  [Remove]

  Divider (red)
  "MAJOR WOUNDS (N)" header + "Greater Restoration" hint
  — Major wound list (tappable)
  — Detail text
  — [Cure]  [Remove]

[WOUND RULES]  (expandable section)
```

---

## 4. Features Missing from Current Android Code

These all need to be implemented in the new version. Listed in priority order.

### Priority 1 — Core Feature Gaps

**4a. Desensitization System (models.py)**
```
FearManager.desens: Dict[str, int]   # fear name → rung 1-4
FearManager.get_desens(name) → int
FearManager.set_desens(name, rung)
FearManager.incr_desens(name) → int  # Confront: rung +1, max 4
FearManager.decr_desens(name) → int  # Avoid: rung -1, min 1
```
Constants needed:
```
DESENS_DC    = {1: 16, 2: 14, 3: 12, 4: 10}
DESENS_NAMES = {1: "Low", 2: "Moderate", 3: "High", 4: "Extreme"}
DESENS_DESCS = {1: "Minimal exposure...", 2: "...", 3: "...", 4: "..."}
DESENS_COLOR      = "#4a9ab8"   (teal)
DESENS_COLOR_DK   = "#2a5870"
DESENS_RUNG_COLORS = {1: STAGE_1, 2: GOLD, 3: STAGE_3, 4: STAGE_4}
```
Save format: `{"fears": {"Heights": 1}, "desens": {"Heights": 2}}`
The existing `FearManager.snapshot()` / `restore()` in models.py must handle
the `desens` key (with backwards compat for saves that lack it).

**4b. Desensitization Tracker (tab_fears.py)**
Four tappable buttons arranged in a horizontal row. Each button shows:
- Rung number and name (e.g., "Low  Rung 1")
- DC value (e.g., "DC 16")
- Highlighted in teal when it is the active rung
- Tapping manually sets the fear's desens rung and saves

**4c. Desensitization Effects Card (tab_fears.py)**
AccentCard with teal border. Updates when:
- A different fear is selected
- Confront/Avoid is resolved (pulse animation like the severity effects card)
Content: rung name, DC, description paragraph.

**4d. DC Auto-Fill (tab_fears.py)**
When a fear is selected from the list (via `_on_fear_tap`), the DC field
must be filled with `DESENS_DC[app.fm.get_desens(name)]`. The DM can still
edit the field before triggering the encounter.

**4e. Confront Logic — Desens Update (tab_fears.py)**
In `_on_push` (Confront / Push Through):
```
app.fm.incr_desens(name)        # rung +1
# then refresh desens tracker and desens effects card
```

**4f. Avoid Logic — Desens Update (tab_fears.py)**
In `_on_avoid`:
```
new_stage = app.fm.increment_stage(name)   # severity +1 (already done)
app.fm.decr_desens(name)                   # rung -1 (MISSING)
```

### Priority 2 — Severity Rename

**4g. Severity Naming (models.py)**
```python
FEAR_STAGES = {
    1: FearStageInfo("Low Severity",      ..., dice=1, color=STAGE_1),
    2: FearStageInfo("Moderate Severity", ..., dice=2, color=STAGE_2),
    3: FearStageInfo("High Severity",     ..., dice=3, color=STAGE_3),
    4: FearStageInfo("Extreme Severity",  ..., dice=4, color=STAGE_4),
}
```
Update all UI strings from "Stage N" to the severity name.
Fear list secondary text: `"Low Severity · 1d4 · Teal"` not `"Stage 1 · 1d4 · Stage 1"`.

**4h. Extreme Severity Special Rules (tab_fears.py)**
In `_on_encounter`, before the save roll:
```python
if stage == 4:
    app.undo_stack.push(app.state, app.fm)
    app.state.exhaustion = clamp(app.state.exhaustion + 1, 0, 6)
    self._log(f"Extreme Severity — +1 Exhaustion applied")
    app.refresh_all()
```
In `_on_avoid`, if `enc.fear_stage == 4`:
```python
new_fear = app.fm.add_random()
if new_fear:
    self._log(f"Extreme Avoid — panic: new fear added: {new_fear}")
```

### Priority 3 — Updated Tables

**4i. Madness Tables — D20 Named System (models.py)**
Replace both the old `SHORT_TERM_MADNESS_TABLE` and the others with the
FSM-6 versions. Each entry is a 3-tuple: `(roll_label, name, effect)`.
Examples: `("D20-1", "Black Out", "The afflicted's vision gutters out...")`.

The `MadnessEntry` dataclass should store `name` separately so it can be
shown as the primary label in the list item.

`add_madness(kind)` rolls `random.randint(1, 20)`, looks up index `roll - 1`
in the table, and creates a `MadnessEntry(kind, name, roll_range, effect, timestamp)`.

Roll display in the snackbar / log: `"D20-7 Black Out: The afflicted's vision..."`.

---

## 5. UI Adaptation Details

### 5a. Touch Targets
- Every interactive element: minimum 44dp tall
- Desens rung buttons: 4 across, each approximately `(screen_width - padding) / 4`
  wide. On a 360dp phone that is ~82dp wide per button — sufficient.
- Severity stage cards: 2-column grid, each card 56dp tall — sufficient.
- Fear list items: 56dp tall (name + secondary line) — sufficient.

### 5b. Font Strategy
Segoe UI is Windows-only. On Android, KivyMD uses the Material Design font stack
(Roboto). Do not hard-code `FONT_FAMILY = "Segoe UI"`. Instead, use KivyMD's
`font_style` parameter (`"H5"`, `"Body2"`, `"Caption"`, `"Button"`, `"Overline"`)
which maps to Roboto automatically.

For canvas-drawn text (SanityBar, MadnessBanner), use `CoreLabel` without
specifying a font — Kivy will use the platform default.

### 5c. Animations
Keep all animations. Kivy's `Clock.schedule_once` / `Clock.schedule_interval`
behave identically on Android. Frame rate target is 30fps (already throttled
in `SanityBar._tick`). Do not use `time.sleep` anywhere.

Pulse animation (MadnessBanner, severity/desens effects cards) uses
`Clock.schedule_interval` at 1/20 seconds — fine on Android.

### 5d. Keyboard / Soft Keyboard
- All `MDTextField` fields should set `on_text_validate` to trigger the
  associated action (e.g., pressing Done on the DC field fires the same
  path as pressing ENCOUNTER).
- After confirm, call `field.focus = False` to dismiss the soft keyboard.
- The ScrollView must accommodate the keyboard rising — Kivy handles this
  automatically on Android when `SOFT_INPUT_MODE = resize` is set in
  buildozer.spec via `android.manifest`.

### 5e. Back Button
Add a keyboard listener in `main.py`:
```python
from kivy.core.window import Window
Window.bind(on_keyboard=self._on_keyboard)

def _on_keyboard(self, window, key, *args):
    if key == 27:  # ESC / Android back
        # If a dialog is open, dismiss it
        # If an encounter is active, cancel it
        # Otherwise do nothing (let Android handle)
        return True
    return False
```

### 5f. Screen Density
Always use `dp()` for all sizes. Never use raw pixel values.
The existing code already does this correctly.

---

## 6. Models.py Changes Required

The `models.py` in FSM-Android must be updated to match FSM-6. Changes:

| Item | Change |
|---|---|
| `FEAR_STAGES` names | Rename to Low/Moderate/High/Extreme Severity |
| `FearManager.desens` | Add desens dict + all desens methods |
| `FearManager.snapshot()` | Include `"desens"` key |
| `FearManager.restore()` | Handle `"desens"` key + backfill |
| Madness tables | Replace all 3 tables with FSM-6 named D20 versions |
| `MadnessEntry` dataclass | Add `name` field (the named effect title) |
| `add_madness()` | Roll 1–20, look up named entry, set `entry.name` |
| `DESENS_DC` | Add dict `{1:16, 2:14, 3:12, 4:10}` |
| `DESENS_NAMES` | Add dict `{1:"Low", 2:"Moderate", 3:"High", 4:"Extreme"}` |
| `DESENS_DESCS` | Add dict of rung descriptions |
| `DESENS_COLOR` | Add teal color constant |
| `DESENS_RUNG_COLORS` | Add per-rung color dict |
| `FEAR_RULES_TEXT` | Update to include desensitization section |
| Extreme Severity handling | Document in constants for UI to check `stage == 4` |

---

## 7. tab_fears.py Changes Required

| Item | Change |
|---|---|
| `_build_encounter_card` | DC field auto-fills from desens DC on fear selection |
| `_build_stage_selector` | Card titles use severity names not "Stage N" |
| `_build_desens_tracker` | **NEW**: 4 tappable rung buttons, teal color scheme |
| `_build_desens_effects` | **NEW**: AccentCard showing rung name, DC, description |
| `refresh()` | Also refresh desens tracker and desens effects on fear selection |
| `_on_fear_tap` | Fill DC field; update desens tracker and effects |
| `_on_stage_select` | No change needed |
| `_on_desens_select` | **NEW**: set desens rung, refresh, save |
| `_on_encounter` | Check `stage == 4` → apply +1 exhaustion before save roll |
| `_on_push` (Confront) | Add `app.fm.incr_desens(name)` + refresh desens UI |
| `_on_avoid` | Add `app.fm.decr_desens(name)` + check stage 4 → add random fear |
| Fear list item secondary text | Show severity name + desens rung name |

---

## 8. Buildozer Configuration

Key `buildozer.spec` settings for Android:

```ini
[app]
title = Sanity Fear and Madness
package.name = sanityfearandmadness
package.domain = org.fsm
source.dir = .
source.include_exts = py,png,jpg,kv,atlas
version = 2.0

requirements = python3,kivy==2.3.0,kivymd==1.2.0

orientation = portrait
fullscreen = 0

android.api = 33
android.minapi = 26
android.archs = arm64-v8a, armeabi-v7a

[buildozer]
log_level = 2
```

**Do not include kivymd as a separate requirement if it bundles kivy.**
Test against KivyMD 1.2.0 (stable) — KivyMD 2.x changed APIs significantly.

---

## 9. What Stays the Same (Do Not Change)

- All game rules and numbers (sanity pool formula, threshold percentages,
  exhaustion level effects, wound DC formula, fear DC formula)
- Color palette (hex values from `theme.py`)
- Save file format (JSON, same keys as FSM-6's `save_v6.json`)
- Undo stack behavior (50-entry limit, snapshot-based)
- Session log format (timestamped strings, copyable)
- All random tables (fear pool, wound tables, madness tables)
- Encounter phase state machine (AWAITING_SAVE → AWAITING_CHOICE)

---

## 10. Implementation Order

Recommended sequence to minimise broken states mid-implementation:

1. **Update `models.py`**: Add desens fields to `FearManager`, update `FEAR_STAGES`
   names, replace madness tables, add `MadnessEntry.name`, add desens constants.
   Test models in isolation (no UI required).

2. **Update `tab_fears.py`**: Add desens tracker card and effects card.
   Wire `_on_fear_tap` to fill DC and update desens UI.
   Fix `_on_push` and `_on_avoid` to call desens methods.
   Add extreme severity exhaustion and random-fear logic.

3. **Update `tab_sanity.py`**: Update Roll Table to use new named D20 madness tables.
   Update list item display to show madness name as primary text.

4. **Update `main.py`**: Add back-button handler.

5. **Smoke test on desktop** (`python main.py`) to verify layout and logic.

6. **Build and test on Android** via `buildozer android debug`.

---

## 11. Known Kivy/KivyMD Pitfalls

- `MDCard` does not accept `orientation` as a constructor kwarg — use
  `BoxLayout` with canvas background instead (already handled in `ui_utils.py`).
- `MDSnackbar` API changed between KivyMD versions; keep the current pattern
  with `MDLabel` child and `md_bg_color`.
- `adaptive_height=True` on `MDBoxLayout` works but the parent `ScrollView`
  must have `size_hint_y=None` and `height` driven by `minimum_height`
  binding — the existing code already handles this correctly.
- `GridLayout` with `row_force_default=True` and `row_default_height` is the
  reliable way to get equal-height rows; the existing 2×2 severity grid is correct.
- `Clock.schedule_once(lambda dt: ...)` for deferred layout updates is necessary
  in some cases because Kivy's layout pass happens asynchronously.
- Never store Kivy widget references across screen rebuilds if `clear_widgets`
  is called; rebuild the references in the same `refresh()` call.
