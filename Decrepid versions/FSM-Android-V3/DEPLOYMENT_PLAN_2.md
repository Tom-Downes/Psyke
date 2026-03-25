# FSM Android — Deployment Plan 2
**Base: FSM-6.py (Desktop, 4831 lines, fully scanned)**
**Target: Kivy / KivyMD 1.2.0 / Buildozer — Android**
**Status: Definitive high-grade feature-complete plan**

---

## About This Document

This plan was produced after reading every line of FSM-6.py. It supersedes
Deployment Plan 1. Every feature is covered — including those absent from
Plan 1 (Healing Spells tab, HOPE checkbox, sanity preview, dropdown madness/
wound selection, animation systems, custom popups, session log coloring, etc.).

**Rule**: FSM-6.py is the single source of truth for all game logic and numbers.
The Android code must produce identical outcomes with a touch-native interface.

---

## 1. Project Structure

```
FSM-Android-V2/
├── main.py          — App class, global state, header, tab bar, save/load, undo
├── models.py        — All data models, constants, tables (FSM-6 parity)
├── widgets.py       — SanityBar, MadnessBanner, ExhaustionWidget (canvas)
├── tab_fears.py     — Fears tab (encounter, severity, desens, fear list, rules)
├── tab_sanity.py    — Sanity & Madness tab (lose/recover, madness management)
├── tab_wounds.py    — Wounds tab (encounter, add wounds, wound lists)
├── tab_spells.py    — Healing Spells tab (Minor + Major Restoration) — NEW
├── ui_utils.py      — BorderCard, AccentCard, PulseCard, SectionHeader, dialogs
├── theme.py         — All color/size constants; KivyMD theme bootstrap
├── animations.py    — PulseAnim, OverlayAnim, ShakeAnim helpers
├── buildozer.spec   — Build configuration
├── DEPLOYMENT_PLAN.md   — Plan 1 (superseded)
└── DEPLOYMENT_PLAN_2.md — This file
```

**Architectural rules (non-negotiable):**
- No Tkinter. No platform-specific imports.
- All mutable state lives on `App.state` (SanityState) and `App.fm` (FearManager).
- UI widgets access state via `App.get_running_app()` — never local copies.
- Every mutation must be preceded by `app.undo_stack.push(app.state, app.fm)`.
- Every mutation must be followed by `app.save_manager.save(app.state, app.fm)`.
- `app.refresh_all()` is the single point of truth for propagating state to all UI.
- Use `dp()` for every size. Never raw pixel values.
- Use `Clock.schedule_once` / `Clock.schedule_interval` — never `time.sleep`.
- Minimum touch target: 44dp height, 44dp width.

---

## 2. models.py — Complete Specification

### 2a. Color Constants (theme.py — reference here for models)

```python
# Core palette (from FSM-6 T class)
BG          = "#0d0d12"
BG_CARD     = "#13131a"
BG_CARD2    = "#1a1a24"
BG_CARD3    = "#20202c"
TEXT_BRIGHT = "#e8e4d8"
TEXT_DIM    = "#8a8070"
TEXT_GOLD   = "#c8a84b"
GOLD        = "#c8a84b"
GOLD_DK     = "#8a6a20"
PURPLE      = "#7040a0"
PURPLE_LT   = "#9060c0"
BLOOD       = "#8b2020"
BLOOD_LT    = "#b03030"
GREEN       = "#4aaa60"
BLUE        = "#5090c8"
BLUE_LT     = "#70b0e0"
SILVER      = "#8090a0"
STAGE_1     = "#3a7a4a"   # Low Severity — green
STAGE_2     = "#8a7030"   # Moderate Severity — amber
STAGE_3     = "#8a4020"   # High Severity — orange-red
STAGE_4     = "#7a2020"   # Extreme Severity — dark red
DESENS_COLOR    = "#4a9ab8"   # teal accent for desens
DESENS_COLOR_DK = "#2a5870"
DESENS_RUNG_COLORS = {1: "#2a5f8a", 2: "#2d85c0", 3: "#3aabdc", 4: "#5ad0f8"}
```

### 2b. Game Constants

```python
FEAR_ENC_DC        = 12    # base DC before desens modifier
WIS_DEFAULT        = 10
CON_DEFAULT        = 10
MAX_EXHAUSTION     = 6
UNDO_LIMIT         = 50
SAVE_FILE_NAME     = "save_v6.json"
SAVE_DIR_NAME      = "SanityFearMadnessTrackerAppData"
THRESHOLDS         = [0.75, 0.50, 0.25, 0.00]   # fire in this order descending
DESENS_DC          = {1: 16, 2: 14, 3: 12, 4: 10}
DESENS_NAMES       = {1: "Low", 2: "Moderate", 3: "High", 4: "Extreme"}
DESENS_DESCS = {
    1: "Minimal exposure has built the faintest resistance...",
    2: "Repeated confrontation has dulled the edge of terror...",
    3: "Hardened by experience, the fear has become familiar...",
    4: "Years of exposure have calcified this dread into reflex..."
}
```

### 2c. FearStageInfo + FEAR_STAGES

```python
@dataclass
class FearStageInfo:
    name:  str
    desc:  str
    dice:  int    # Xd4 on failed save
    color: str

FEAR_STAGES = {
    1: FearStageInfo("Low Severity",      "...", 1, STAGE_1),
    2: FearStageInfo("Moderate Severity", "...", 2, STAGE_2),
    3: FearStageInfo("High Severity",     "...", 3, STAGE_3),
    4: FearStageInfo("Extreme Severity",  "...", 4, STAGE_4),
}
```

All UI references to "Stage N" must use `FEAR_STAGES[n].name`. No hardcoded
stage labels anywhere in the UI layer.

### 2d. Madness Tables — D20 Named System

Three tables, each with 20 entries:

```python
@dataclass
class MadnessTableEntry:
    roll_label: str   # e.g. "D20-1"
    name:       str   # e.g. "Black Out"
    effect:     str   # full effect description

SHORT_TERM_TABLE:  List[MadnessTableEntry]  # 20 entries, 1d10 minutes
LONG_TERM_TABLE:   List[MadnessTableEntry]  # 20 entries, 1d10×10 hours
INDEFINITE_TABLE:  List[MadnessTableEntry]  # 20 entries, until cured

# Copy tables verbatim from FSM-6.py — they are the source of truth.
```

```python
@dataclass
class MadnessEntry:
    kind:       str   # "Short", "Long", "Indefinite", "Custom"
    roll_range: str   # e.g. "D20-7" or "Custom"
    name:       str   # named effect title (primary list label)
    effect:     str   # full effect text
    timestamp:  str   # HH:MM from time.strftime
```

### 2e. Wound Tables

```python
@dataclass
class WoundTableEntry:
    roll:   int
    name:   str
    effect: str

MINOR_WOUND_TABLE: List[WoundTableEntry]  # 20 entries
MAJOR_WOUND_TABLE: List[WoundTableEntry]  # 20 entries
# Copy verbatim from FSM-6.py.

@dataclass
class WoundEntry:
    kind:      str   # "Minor" / "Major"
    name:      str
    effect:    str
    cured:     bool = False
    timestamp: str  = ""
```

### 2f. SanityState

```python
@dataclass
class SanityState:
    wis_score:        int = 10
    con_score:        int = 10
    max_sanity:       int = 15   # 15 + wis_mod, rebuilt on set_wis
    current_sanity:   int = 15
    exhaustion:       int = 0    # 0–6
    hope:             bool = False
    fired_thresholds: Set[float] = field(default_factory=set)
    wounds:           List[WoundEntry] = field(default_factory=list)
    madnesses:        List[MadnessEntry] = field(default_factory=list)
    enc_history:      List[dict] = field(default_factory=list)

    # --- Core methods ---
    def wis_mod(self) -> int: return (self.wis_score - 10) // 2
    def con_mod(self) -> int: return (self.con_score - 10) // 2
    def set_wis(self, val: int): ...   # clamp 1–30, rebuild max_sanity, clamp current
    def set_con(self, val: int): ...   # clamp 1–30
    def apply_loss(self, amount: int) -> Tuple[int, List[float]]:
        # Returns (actual_lost, newly_fired_thresholds)
    def apply_recovery(self, amount: int) -> Tuple[int, List[Tuple[str,str,int]]]:
        # Returns (actual_gained, auto_cleared_madnesses)
        # Auto-clear: crossing above 75% clears all Short-term
        #             crossing above 50% clears all Long-term
        #             Indefinite is NEVER auto-cleared
    def add_madness(self, kind: str) -> MadnessEntry:
        # Rolls 1d20, looks up table, creates MadnessEntry
    def add_madness_specific(self, kind: str, roll_range: str,
                              name: str, effect: str) -> MadnessEntry:
        # Creates MadnessEntry from explicit values (from dropdown)
    def add_wound(self, kind: str, name: str, effect: str) -> WoundEntry: ...
    def snapshot(self) -> dict: ...
    def restore(self, d: dict): ...
```

### 2g. FearManager

```python
class FearManager:
    fears:  Dict[str, int]   # fear name → severity rung 1-4
    desens: Dict[str, int]   # fear name → desens rung 1-4

    def get_stage(self, name: str) -> int: ...
    def set_stage(self, name: str, stage: int): ...
    def increment_stage(self, name: str) -> int:  # +1, max 4
    def get_desens(self, name: str) -> int: return self.desens.get(name, 1)
    def set_desens(self, name: str, rung: int): ...
    def incr_desens(self, name: str) -> int:  # +1, max 4
    def decr_desens(self, name: str) -> int:  # -1, min 1
    def add_fear(self, name: str, stage: int = 1): ...
    def remove_fear(self, name: str): ...
    def add_random(self) -> Optional[str]:
        # Picks from FEAR_POOL excluding already-active fears
        # Returns the new fear name, or None if pool exhausted
    def suggest(self, exclude: List[str]) -> Optional[str]: ...
    def snapshot(self) -> dict:
        return {"fears": dict(self.fears), "desens": dict(self.desens)}
    def restore(self, d: dict):
        # Handle both new {"fears":..., "desens":...} format
        # and old flat {name:stage} format (backfill desens=1)
```

### 2h. EncounterState

```python
class EncounterPhase(Enum):
    IDLE           = "idle"
    AWAITING_SAVE  = "awaiting_save"
    AWAITING_CHOICE= "awaiting_choice"

@dataclass
class EncounterState:
    phase:          EncounterPhase = EncounterPhase.IDLE
    fear_name:      str = ""
    fear_stage:     int = 0
    dc:             int = 0
    roll:           int = 0
    sanity_roll:    int = 0   # Xd4 result (damage on fail)
    passed:         bool = False

class WoundEncPhase(Enum):
    IDLE           = "idle"
    AWAITING_SAVE  = "awaiting_save"
    AWAITING_CHOICE= "awaiting_choice"

@dataclass
class WoundEncounterState:
    phase:   WoundEncPhase = WoundEncPhase.IDLE
    dc:      int = 0
    dmg:     int = 0
    roll:    int = 0
    verdict: str = ""
```

### 2i. SaveManager

```python
class SaveManager:
    # Android save path: app.user_data_dir / SAVE_FILE_NAME
    # (Kivy's App.user_data_dir is the correct cross-platform path)
    def save(self, state: SanityState, fm: FearManager): ...
    def load(self) -> Tuple[Optional[SanityState], Optional[FearManager]]: ...
```

Save JSON structure (must match FSM-6 exactly for cross-platform compatibility):
```json
{
  "wis": 10, "con": 10, "current_sanity": 15,
  "exhaustion": 0, "hope": false,
  "fired_thresholds": [],
  "wounds": [{"kind":"Minor","name":"...","effect":"...","cured":false,"timestamp":""}],
  "madnesses": [{"kind":"Short","roll_range":"D20-7","name":"Black Out","effect":"...","timestamp":"12:34"}],
  "enc_history": [{"fear":"Heights","result":"Passed","change":-2,"time":"12:34"}],
  "fears": {"fears": {"Heights": 2}, "desens": {"Heights": 1}}
}
```

### 2j. UndoStack

```python
class UndoStack:
    _stack: List[Tuple[dict, dict]]  # (state_snapshot, fm_snapshot)
    limit: int = UNDO_LIMIT

    def push(self, state: SanityState, fm: FearManager): ...
    def pop(self) -> Optional[Tuple[dict, dict]]: ...
    def can_undo(self) -> bool: ...
```

---

## 3. theme.py — Complete Specification

```python
from kivy.metrics import dp

# --- All colors as above in 2a ---
# --- Size constants ---
HEADER_H      = dp(88)
TAB_BAR_H     = dp(40)
SANITY_BAR_H  = dp(28)
BANNER_H      = dp(52)
SANITY_LABEL_H= dp(18)
CARD_PADDING  = dp(12)
CARD_RADIUS   = dp(8)
TOUCH_MIN     = dp(44)
SECTION_SEP   = dp(8)
LIST_ITEM_H   = dp(56)

def setup_theme(theme_cls):
    """Call once in App.build() to configure KivyMD."""
    theme_cls.theme_style = "Dark"
    theme_cls.primary_palette = "Amber"
    theme_cls.primary_hue = "700"
    theme_cls.accent_palette = "Teal"
```

---

## 4. widgets.py — Complete Specification

### 4a. SanityBar

Canvas-drawn Widget. Matches FSM-6 visual exactly.

```
Features:
- 18-band parabolic gradient fill (dark purple → vivid purple → dark purple)
- Animated smooth fill using smoothstep easing (BarAnim class)
- Threshold markers at 75%, 50%, 25%:  square-notch tick marks
- Percentage label: inside bar if > 15% filled, outside (right-aligned) if < 15%
- Color of fill text: contrasting white or dim based on position
- Updates via set_sanity(current, maximum) which triggers BarAnim
- Clock.schedule_interval tick at 1/30 fps during animation
```

BarAnim:
```python
class BarAnim:
    start: float
    end:   float
    t:     float = 0.0   # 0→1
    speed: float = 3.0   # units/second

    def tick(self, dt: float) -> float:
        # smoothstep(t) applied to interpolate start→end
        # Returns current fill fraction
        # Returns None when animation complete
```

### 4b. MadnessBanner

Canvas-drawn Widget. Always visible in global header area.

```
States:
- NORMAL: dim background, no text (hidden)
- ACTIVE: shows madness name + "(Madness Active)" subtitle
- PULSE: Clock-driven cosine pulse on border color at ~20fps
          pulse cycles between BLOOD and BLOOD_LT
          starts on new madness added or threshold crossed
          pulses for 3.0 seconds then holds ACTIVE state

Methods:
- set_madness(entry: MadnessEntry | None)  — call when active madness changes
- pulse()  — start pulse animation
```

### 4c. ExhaustionWidget

Row of 6 circular pips. Tappable on Android (sets exhaustion to tapped index).

```
Pip states:
- Filled (BLOOD_LT) for levels 0→exhaustion
- Empty (BG_CARD2 + dim outline) for levels above exhaustion
- Minimum size: 36dp diameter, 8dp gap between pips
- On tap: app.undo_stack.push → set exhaustion → save → refresh
```

---

## 5. animations.py — Complete Specification

All animations use `Clock` only. No `time.sleep`. No threading.

### 5a. PulseAnim

Drives the "focus" pulse on effect panels (severity, desens, madness, wound,
sanity controls). Used by `_focus_stage_effects`, `_focus_desens_effects`,
`_focus_madness_effects`, `_focus_wound_effects`, `_focus_sanity_controls`.

```python
class PulseAnim:
    """
    Pulses a card's border color between accent_color and dim_color.
    Uses cosine easing. Runs for `duration` seconds at `fps`.
    """
    def start(self, widget, accent_color: str, dim_color: str,
              duration: float = 1.0, fps: int = 20): ...
    def stop(self): ...
```

Usage pattern in all tabs:
```python
def _focus_stage_effects(self):
    PulseAnim().start(self._stage_effect_card,
                      accent=GOLD, dim=GOLD_DK, duration=1.0)

def _focus_desens_effects(self):
    PulseAnim().start(self._desens_effect_card,
                      accent=DESENS_COLOR, dim=DESENS_COLOR_DK, duration=1.0)
```

### 5b. OverlayAnim

Used for skull overlay (fear encounter start) and blood overlay (wound encounter
start). Drawn on a full-screen FloatLayout overlay above all content.

```python
class OverlayAnim:
    """
    Fade-in → hold → fade-out sequence for a centered image.
    Phase:   fade_in (0.3s), hold (0.5s), fade_out (0.4s)
    Uses cosine ease for fade_in/out opacity.
    Image: skull for fears, blood/sword for wounds.
    On Android: use bundled PNG assets (no remote download).
    """
    def show(self, image_source: str, tint: str = ""): ...
```

Desktop downloads OpenMoji PNGs at runtime — on Android, bundle skull.png,
blood.png, sword.png in assets/ and reference them locally.

### 5c. ScreenFadeIn

Runs once on App startup. Fades main window from opacity=0 to opacity=1 over
0.4 seconds using smoothstep. On Android, use `Window.opacity` if available,
or skip gracefully if not supported.

### 5d. ShakeAnim

Equivalent to desktop's `_shake()`. On Android, briefly translates the root
widget ±8dp horizontally, 8 alternations, 30ms apart. Called on invalid input.

```python
class ShakeAnim:
    def shake(self, widget, amplitude_dp=8, steps=8, interval=0.03): ...
```

---

## 6. ui_utils.py — Complete Specification

### 6a. BorderCard

`BoxLayout` subclass with canvas-drawn rectangle outline.

```python
class BorderCard(BoxLayout):
    """
    Dark-background card with colored border.
    border_color: str hex
    border_width: dp
    radius: dp
    """
```

### 6b. AccentCard

`BorderCard` subclass with lighter background for effect panels.

### 6c. SectionHeader

`MDLabel` styled as an uppercase bold section title with a colored underline.

### 6d. DividerLine

Thin `Widget` with canvas-drawn horizontal line in a given color.

### 6e. custom_dialog

```python
def custom_dialog(title: str, body: str, icon: str = "",
                  yes_no: bool = False) -> bool | None:
    """
    Modal popup matching FSM-6's _popup_dialog.
    - Dark rounded-card background (radius 18dp)
    - Icon box with colored icon label (skull=red, brain=purple, etc.)
    - Title text (TEXT_BRIGHT) + body text (TEXT_DIM)
    - If yes_no=True: [YES] (green) + [NO] (dim) buttons → returns True/False
    - If yes_no=False: [OK] button → returns None
    - Centers on screen, dims background
    - On dismiss: release keyboard focus
    """
```

Desktop equivalent: `_popup_dialog()` in FSM-6.py with canvas.create_polygon
rounded-card. Kivy version uses MDDialog or a custom ModalView with canvas.

### 6f. show_snackbar

```python
def show_snackbar(text: str, duration: float = 2.5, color: str = BG_CARD2): ...
```

Uses `MDSnackbar` with `MDLabel` child. Keeps the existing Android pattern.

---

## 7. main.py — Complete Specification

### 7a. App Class

```python
class FSMApp(MDApp):
    state:      SanityState
    fm:         FearManager
    save_manager: SaveManager
    undo_stack:   UndoStack
    enc:          EncounterState
    wenc:         WoundEncounterState
    session_start: float   # time.time() on launch
    session_log:   List[str]  # timestamped strings

    def build(self): ...
    def on_start(self): ...   # load save, ScreenFadeIn, bind back button
    def refresh_all(self): ...  # propagates to all tabs + header + bar + banner
    def log(self, text: str, tag: str = ""): ...  # prepends HH:MM timestamp
    def save(self): ...       # shorthand for save_manager.save(state, fm)
    def undo(self): ...       # pops undo stack, restores, refresh_all
```

### 7b. Global Layout (always visible)

```
Root: BoxLayout (vertical)
├── HeaderWidget                          88dp  fixed
├── SanityBar                             28dp  fixed
├── MadnessBanner                         52dp  fixed
├── SanityLabelRow                        18dp  fixed
│     "Sanity: {current} / {max}"  (TEXT_DIM)
├── TabBar                                40dp  fixed
│     [FEARS]  [SANITY]  [WOUNDS]  [SPELLS]
├── DividerLine (tab accent color)         2dp  fixed
└── ScrollView (fills remaining)               flex
      └── Active Tab Content (BoxLayout vertical, adaptive_height)
```

**Tab accent colors:**
- FEARS:  GOLD (amber)
- SANITY: PURPLE
- WOUNDS: BLOOD
- SPELLS: SILVER

### 7c. HeaderWidget — Row 1 (44dp)

```
[Character Name MDTextField]            [log btn]  [undo btn]
```

- **Character Name**: `MDTextField` mode="rectangle", hint="Character Name",
  stores to `state.name` on `on_text_validate` and `on_focus` (focus lost).
- **Log button**: opens SessionLogDialog (see section 7f).
- **Undo button**: calls `app.undo()`. Dims when `not undo_stack.can_undo()`.

### 7d. HeaderWidget — Row 2 (30dp)

```
[WIS 10 +0]  [CON 10 +0]  [ExhaustionWidget ●●○○○○]  [HOPE □]  [00:00]
```

- **WIS chip**: taps to open WIS entry dialog (numeric field, Set button).
  Shows `WIS {score} {+/-mod}`. On set: `app.undo_stack.push` → `state.set_wis`
  → `save` → `refresh_all`. Update sanity bar + label immediately.
- **CON chip**: same pattern for CON.
- **ExhaustionWidget**: 6 pips, tappable to set level (see section 4c).
- **HOPE checkbox**: `MDCheckbox` + label "HOPE". Stores to `state.hope`.
  No game mechanic currently — tracks state for future use. Saves on toggle.
- **Session Timer**: `Label` updated every 60 seconds via `Clock.schedule_interval`.
  Shows HH:MM elapsed since `session_start`.

### 7e. Back Button Handler (Android)

```python
from kivy.core.window import Window

def _on_keyboard(self, window, key, *args):
    if key == 27:  # Android back / ESC
        if self._active_dialog:
            self._active_dialog.dismiss(); return True
        if self.enc.phase != EncounterPhase.IDLE:
            self._cancel_encounter(); return True
        if self.wenc.phase != WoundEncPhase.IDLE:
            self._cancel_wenc(); return True
        return False   # propagate to Android (home)
    return False
```

### 7f. Session Log Dialog

**NOT always-visible as in desktop** — Android opens it as a `ModalView` or
`MDDialog` because screen space is too constrained for an 8-line always-visible
widget. Dialog is scrollable if log exceeds screen height.

Log entries are color-coded using spans. Categories matching FSM-6:

| Tag     | Color     | Usage                              |
|---------|-----------|-------------------------------------|
| wound   | BLOOD     | wound events                        |
| brain   | PURPLE    | madness events                      |
| passed  | GREEN     | save passed                         |
| failed  | BLOOD_LT  | save failed                         |
| fear    | GOLD      | fear events                         |
| sword   | STAGE_3   | wound encounter events              |
| shield  | GREEN     | recovery events                     |
| sanity  | PURPLE_LT | sanity change events                |
| dice    | BLUE      | roll results                        |
| warn    | GOLD      | warnings / threshold messages       |
| dim     | TEXT_DIM  | neutral / info                      |

On Android, use `[color=hex]text[/color]` markup in a `Label` inside a
`ScrollView`. Copy button exports log to clipboard via `Clipboard.copy()`.

### 7g. refresh_all()

```python
def refresh_all(self):
    self._header.refresh()
    self._sanity_bar.set_sanity(self.state.current_sanity, self.state.max_sanity)
    self._banner.set_madness(self._active_madness_for_banner())
    self._sanity_label.text = f"Sanity: {self.state.current_sanity} / {self.state.max_sanity}"
    self._exhaustion.set_level(self.state.exhaustion)
    active = self._active_tab
    if active == "fears":   self._tab_fears.refresh()
    if active == "sanity":  self._tab_sanity.refresh()
    if active == "wounds":  self._tab_wounds.refresh()
    if active == "spells":  self._tab_spells.refresh()
```

Active tab only refreshes the visible tab. On tab switch, call `refresh()`
on the newly shown tab.

---

## 8. tab_fears.py — Complete Specification

### 8a. Layout (top to bottom in ScrollView)

```
[FEAR ENCOUNTER CARD]      gold border
[SEVERITY TRACKER CARD]    gold border
[SEVERITY EFFECTS CARD]    gold accent, PulseAnim target
[DESENSITIZATION CARD]     teal border           ← NEW
[DESENSITIZATION EFFECTS]  teal accent, PulseAnim target  ← NEW
[ADD FEAR ROW]             borderless
[ACTIVE FEARS CARD]        gold border
[FEAR RULES]               expandable section
```

### 8b. Fear Encounter Card

```
[skull icon]  [selected fear label — dim until selected]
DC: [text field, auto-filled from desens DC, editable]  [ENCOUNTER btn]

--- roll panel (height=0/opacity=0 when hidden) ---
"Roll Result"  [big number — auto-rolled WIS save]
[Failed Save]  [Passed]          row 1
[Confront]     [Avoid]           row 2

--- sanity preview box (appears after failed save) ---
"Confront: {current} − {roll}  =  {result}  {madness_change}"
"Avoid:    {current} + {gain}  =  {result}  {madness_change}"
```

**Encounter trigger flow:**
1. User taps ENCOUNTER (fear must be selected).
2. If `enc.phase != IDLE`: show error snackbar ("Encounter already active").
3. If stage == 4 (Extreme Severity):
   - `undo_stack.push` → `state.exhaustion += 1` → `save` → `refresh_all`
   - `log(f"Extreme Severity encounter — +1 Exhaustion", "warn")`
4. Show `OverlayAnim("assets/skull.png")`.
5. Auto-roll WIS save: `roll = random.randint(1, 20) + state.wis_mod()`.
6. Set `enc = EncounterState(phase=AWAITING_SAVE, fear_name=..., fear_stage=stage, dc=dc_field_value, roll=roll)`.
7. Animate roll panel open (height 0 → full, opacity 0→1, 0.25s).
8. Show roll result number.
9. Enable [Failed Save] / [Passed] buttons. Disable [Confront] / [Avoid].

**DC auto-fill on fear selection:**
```python
def _on_fear_tap(self, name):
    self._sel = name
    dc = DESENS_DC[app.fm.get_desens(name)]
    self._dc_field.text = str(dc)
    self._refresh_severity_tracker()
    self._refresh_desens_tracker()
    self._refresh_desens_effects()
    self._refresh_stage_effects()
    self._encounter_label.text = name
```

**[Failed Save] flow:**
1. `enc.phase = AWAITING_CHOICE`.
2. Roll sanity damage: `roll = sum(random.randint(1,4) for _ in range(enc.fear_stage))`.
3. `enc.sanity_roll = roll`.
4. Enable [Confront] / [Avoid] buttons.
5. Update sanity preview box (see 8c below).
6. Call `_focus_stage_effects()`.

**[Passed] flow:**
1. `undo_stack.push` → no sanity change → `enc.phase = IDLE`.
2. Close roll panel (animate shut).
3. `log(f"PASSED fear save vs DC {enc.dc} (rolled {enc.roll})", "passed")`.
4. Save + refresh_all. Record in `enc_history`.

**[Confront] flow:**
1. `undo_stack.push`.
2. `state.apply_loss(enc.sanity_roll)` → capture `(_, newly_fired)`.
3. `fm.incr_desens(enc.fear_name)`.
4. `log(f"CONFRONT — {enc.fear_name}: −{enc.sanity_roll} sanity", "fear")`.
5. Record enc_history entry.
6. Save, refresh_all.
7. `_refresh_desens_tracker()`, `_refresh_desens_effects()`, `_focus_desens_effects()`.
8. Close roll panel (animate shut).
9. `enc.phase = IDLE`.
10. If `newly_fired`: call `_handle_thresh(newly_fired)` via `Clock.schedule_once(0.16s)`.

**[Avoid] flow:**
1. `undo_stack.push`.
2. `gained, cleared = state.apply_recovery(2)`.
3. `new_stage = fm.increment_stage(enc.fear_name)`.
4. `fm.decr_desens(enc.fear_name)`.
5. `log(f"AVOID — {enc.fear_name}: +{gained} sanity, severity → {FEAR_STAGES[new_stage].name}", "fear")`.
6. If `cleared`: log each auto-cleared madness.
7. If `new_stage == 4`:
   - `new_fear = fm.add_random()`
   - If `new_fear`: `log(f"Extreme panic — new fear: {new_fear}", "warn")`; show snackbar.
8. Record enc_history, save, refresh_all.
9. `_refresh_desens_tracker()`, `_refresh_desens_effects()`, `_focus_desens_effects()`.
10. Close roll panel, `enc.phase = IDLE`.
11. No deferred threshold popup needed (recovery can't trigger threshold).

### 8c. Sanity Preview Box

Appears in the encounter card below the roll panel after a failed save.

```
"Confront: 18 − 3 = 15"          (color: TEXT_DIM / BLOOD)
"Avoid:    18 + 2 = 20"          (color: TEXT_DIM / GREEN)
```

If the result crosses a madness threshold, append the madness stage change:
```
"Confront: 18 − 3 = 15  ⚠ Madness threshold!"
```

Implementation:
```python
def _update_sanity_preview(self, roll: int):
    cur = app.state.current_sanity
    confront_result = max(0, cur - roll)
    avoid_gain = 2
    avoid_result = min(app.state.max_sanity, cur + avoid_gain)
    confront_thresh = _would_cross_threshold(cur, confront_result, app.state)
    self._preview_confront.text = f"Confront: {cur} − {roll} = {confront_result}" + \
                                   ("  ⚠" if confront_thresh else "")
    self._preview_avoid.text    = f"Avoid:    {cur} + {avoid_gain} = {avoid_result}"
```

### 8d. Severity Tracker Card

2×2 `GridLayout` of tappable cards. Each card:
- Shows stage name + dice (e.g., "Low Severity  1d4")
- Background color from `FEAR_STAGES[n].color` when active, dim when not
- Minimum height: 56dp per card
- Tapping sets the selected fear's stage: `undo_stack.push → fm.set_stage(name, n) → save → refresh`

```python
def _refresh_severity_tracker(self):
    stage = fm.get_stage(self._sel) if self._sel else 0
    for n, card in self._stage_cards.items():
        card.active = (n == stage)
        card.border_color = FEAR_STAGES[n].color if n == stage else BG_CARD3
```

After tapping a severity card, call `_focus_stage_effects()`.

### 8e. Severity Effects Card

AccentCard with gold border. Updates when severity tracker changes.

```
"Low Severity — 1d4"           (title, GOLD)
"Fail → roll 1d4..."           (dice line, TEXT_DIM)
"{desc from FEAR_STAGES[n].desc}"  (body, TEXT_DIM)
```

PulseAnim target: `_focus_stage_effects()` pulses gold border.

### 8f. Desensitization Tracker Card (NEW)

`BorderCard` with `DESENS_COLOR` border. Four tappable rung buttons in a horizontal row.

Each button (occupies `(screen_width - 2×padding) / 4` wide):
```
Row 1: "{DESENS_NAMES[n]}"      (name label)
Row 2: "Rung {n}"              (subtitle)
Row 3: "DC {DESENS_DC[n]}"    (DC label)
```

Active rung: background = `DESENS_RUNG_COLORS[rung]`, border highlighted.
Inactive rungs: background = `BG_CARD2`, border = `DESENS_COLOR_DK`.

Tapping sets the selected fear's desens rung:
```python
def _on_desens_select(self, rung: int):
    if not self._sel: return
    app.undo_stack.push(app.state, app.fm)
    app.fm.set_desens(self._sel, rung)
    app.save()
    self._refresh_desens_tracker()
    self._refresh_desens_effects()
    self._focus_desens_effects()
    # update DC field to match new rung
    self._dc_field.text = str(DESENS_DC[rung])
```

### 8g. Desensitization Effects Card (NEW)

AccentCard with `DESENS_COLOR` border. Updates on rung change or fear selection.

```
"Low Desensitization — Rung 1"    (title, DESENS_COLOR)
"DC 16"                           (DC label, bold)
"{DESENS_DESCS[rung]}"            (body, TEXT_DIM)
```

PulseAnim target: `_focus_desens_effects()` pulses teal border.

### 8h. Add Fear Row

```
[MDTextField: "Fear name..."]  [🎲 Suggest]  [Add Fear]
```

- **Suggest**: calls `fm.suggest(list(fm.fears.keys()))`, fills text field.
- **Add Fear**: validates non-empty, not duplicate → `undo_stack.push → fm.add_fear(name) → save → refresh`.
- `on_text_validate` on field triggers Add Fear.

### 8i. Active Fears Card

`BorderCard` with GOLD border. Header: "FEARS" + trash icon (remove selected).

List of fears. Each list item (56dp tall, tappable):
```
[Fear Name]              (TEXT_BRIGHT, bold)
[SeverityName · DesensName]  (TEXT_DIM, subtitle)
```

Selected item: background = `BG_CARD3`, left accent bar = `FEAR_STAGES[stage].color`.

On tap: `_on_fear_tap(name)` (see 8b).

Remove button (trash icon in header): removes selected fear.
`undo_stack.push → fm.remove_fear(sel) → save → refresh`.

**No "Remove All" on mobile** — destructive; use per-item swipe-to-delete or
long-press context menu if desired in v2.1.

### 8j. Fear Rules Section

Expandable `MDExpansionPanel` at bottom of Fears tab. Header: "FEAR RULES" (gold).
Content: full `FEAR_RULES_TEXT` from FSM-6 including the desensitization section.
Use `Label` with `text_size=(width, None)` for word wrap.

---

## 9. tab_sanity.py — Complete Specification

### 9a. Layout (top to bottom in ScrollView)

```
[SANITY CONTROLS CARD]      purple border, PulseAnim target
[MADNESS CARD]              purple border
  ├─ [SHORT-TERM CARD]      gold-amber accent
  ├─ [LONG-TERM CARD]       orange accent
  └─ [INDEFINITE CARD]      red accent
[ACTIVE MADNESS CARD]       purple border
[MADNESS RULES]             expandable
```

### 9b. Sanity Controls Card

Desktop uses text entry fields for arbitrary amounts. Android uses the existing
preset-button approach (better for touch):

```
"LOSE SANITY"
[−1] [−2] [−3] [−5] [−10]        (5 equal-width, BLOOD buttons, 48dp tall)

"RECOVER SANITY"
[+1] [+2] [+3] [+5] [+10]        (5 equal-width, GREEN buttons, 48dp tall)

[DM +1d4]  [DM +2d4]  [Restore Max]   (3 buttons, 44dp tall)
```

**Also provide a custom amount row** (not in desktop UI — mobile improvement):
```
[MDTextField: amount]  [LOSE]  [RECOVER]
```

This covers arbitrary amounts the DM might call for, equivalent to the desktop's
text-entry approach.

**Lose flow:**
```python
def _on_lose(self, amount: int):
    app.undo_stack.push(app.state, app.fm)
    actual, fired = app.state.apply_loss(amount)
    app.log(f"−{actual} sanity ({app.state.current_sanity}/{app.state.max_sanity})", "sanity")
    app.save(); app.refresh_all()
    PulseAnim().start(self._sanity_card, PURPLE, BG_CARD2)
    if fired:
        Clock.schedule_once(lambda dt: self._handle_thresh(fired), 0.16)
```

**Recover flow:**
```python
def _on_recover(self, amount: int):
    app.undo_stack.push(app.state, app.fm)
    actual, cleared = app.state.apply_recovery(amount)
    app.log(f"+{actual} sanity ({app.state.current_sanity}/{app.state.max_sanity})", "shield")
    for kind, label, n in cleared:
        app.log(f"Auto-cleared {n} {kind} madness(es) — above threshold", "brain")
    app.save(); app.refresh_all()
    PulseAnim().start(self._sanity_card, GREEN, BG_CARD2)
```

**DM Dice roll:**
```python
def _on_dm_roll(self, dice_count: int):
    total = sum(random.randint(1,4) for _ in range(dice_count))
    show_snackbar(f"DM rolled {dice_count}d4 = {total}", color=PURPLE)
    self._on_recover(total)
```

**Restore Max:**
```python
def _on_restore_max(self):
    amount = app.state.max_sanity - app.state.current_sanity
    if amount <= 0: return
    self._on_recover(amount)
```

### 9c. Madness Category Cards

**Desktop uses Combobox dropdowns** to select specific named effects from the
full 20-entry table. Android replicates this with `MDDropDownItem` / spinner.

Each of the 3 madness cards has the same layout:

```
[SHORT-TERM MADNESS]               (header, gold-amber)
"1d10 minutes"                     (subtitle)

[Dropdown — select specific effect ▾]   full-width, 44dp
[Custom effect MDTextField]             (blank = random roll)
[Roll Random]   [Add Selected]          (2 buttons)
```

**Dropdown behavior:**
- Options list: all 20 named entries in the table
- Format: "D20-1: Black Out", "D20-2: ...", etc.
- Selecting an option previews the effect text below the dropdown
- [Add Selected]: creates madness from dropdown selection via `add_madness_specific`
- [Roll Random]: rolls 1d20 in code, picks entry, creates madness via `add_madness`
- [Custom effect]: if text entered, creates a Custom madness entry (kind="Custom")

**Add madness flow:**
```python
def _on_add_madness(self, kind: str, roll_range: str, name: str, effect: str):
    app.undo_stack.push(app.state, app.fm)
    entry = app.state.add_madness_specific(kind, roll_range, name, effect)
    app.log(f"Madness added: {name} ({kind})", "brain")
    app.save(); app.refresh_all()
    self._banner.pulse()
    PulseAnim().start(self._madness_card, PURPLE, BG_CARD2)
```

### 9d. Active Madness Card

Header: "ACTIVE MADNESS" + remove-selected icon (trash).

List of madness entries. Each item (56dp tall, tappable):
```
[Madness Name]           (TEXT_BRIGHT, bold)
[Kind · Roll · Time]    (TEXT_DIM, subtitle)
```

On tap: shows full effect text in an `MDExpansionPanel` or inline detail area below.

Remove selected: `undo_stack.push → state.madnesses.remove(entry) → save → refresh_all`.

**No "Remove All" button on main view** — provide in a long-press context menu or
a confirmation dialog to prevent accidental wipes.

### 9e. Madness Effects Panel

Inline below the active madness list. Shows full effect text of selected entry.

```
[Selected Name]         (TEXT_BRIGHT)
[Roll: D20-7]  [Kind]   (TEXT_DIM)
[Full effect text]      (TEXT_DIM, multiline, wrap)
[Timestamp]             (TEXT_DIM, italic)
```

PulseAnim target: `_focus_madness_effects()` — called after threshold adds madness
and on manual selection.

### 9f. _handle_thresh Flow

Called (deferred 160ms) when sanity loss fires a threshold.

```python
def _handle_thresh(self, fired_thresholds: List[float]):
    for pct in fired_thresholds:
        label = {0.75:"75%", 0.50:"50%", 0.25:"25%", 0.0:"0%"}[pct]
        kind  = {0.75:"Short", 0.50:"Long", 0.25:"Indefinite", 0.0:"Indefinite"}[pct]
        msg = f"Sanity crossed {label} threshold!\nRoll random {kind} madness?"
        answer = custom_dialog("THRESHOLD", msg, icon="brain", yes_no=True)
        if answer:
            entry = app.state.add_madness(kind)
            app.log(f"Threshold madness: {entry.name} ({kind})", "brain")
        app.save(); app.refresh_all()
        # Navigate to sanity tab
        app.switch_tab("sanity")
        Clock.schedule_once(lambda dt: self._focus_madness_effects(), 0.2)
```

### 9g. Madness Rules Section

`MDExpansionPanel` at bottom. Content: `MADNESS_RULES_TEXT` from FSM-6.

---

## 10. tab_wounds.py — Complete Specification

### 10a. Layout (top to bottom)

```
[WOUND ENCOUNTER CARD]       blood-red border
[ADD WOUND CARD]             blood-red border
[MINOR WOUNDS CARD]          blood-red border
[MAJOR WOUNDS CARD]          blood-red border (darker accent)
[WOUND RULES]                expandable
```

### 10b. Wound Encounter Card

```
DC: [text field]    Damage: [text field]   [Calc DC]    [WOUND ENC]

--- roll panel (hidden when IDLE) ---
Roll: [auto-rolled CON save]
[Pass 5+]  [Pass]
[Fail]     [Fail 5+]

"Result: ..."      (outcome label)
```

**Calc DC button:**
```python
def _on_calc_dc(self):
    try:
        dmg = int(self._dmg_field.text)
        dc = max(10, dmg // 2)
        self._dc_field.text = str(dc)
    except ValueError:
        ShakeAnim().shake(self._dc_field)
```

**Encounter trigger:**
1. Validate DC and dmg fields.
2. Show `OverlayAnim("assets/blood.png")`.
3. Auto-roll CON save: `roll = random.randint(1,20) + state.con_mod()`.
4. Set `wenc = WoundEncounterState(phase=AWAITING_SAVE, dc=dc, dmg=dmg, roll=roll)`.
5. Animate roll panel open.
6. Enable [Pass 5+] / [Pass] / [Fail] / [Fail 5+].

**Outcome buttons:**
```python
OUTCOMES = {
    "pass5": ("PASS by 5+", "Full success — immune this session", GREEN),
    "pass":  ("PASS",       "No wound",                           GREEN),
    "fail":  ("FAIL",       "Add Minor Wound",                    BLOOD_LT),
    "fail5": ("FAIL by 5+", "Add Major Wound",                    BLOOD),
}
```
Each button calls `_wound_resolve(verdict)`.

**_wound_resolve:**
```python
def _wound_resolve(self, verdict: str):
    app.undo_stack.push(app.state, app.fm)
    if verdict in ("fail", "fail5"):
        kind = "Major" if verdict == "fail5" else "Minor"
        # roll random wound from table
        table = MAJOR_WOUND_TABLE if kind == "Major" else MINOR_WOUND_TABLE
        entry_data = random.choice(table)
        app.state.add_wound(kind, entry_data.name, entry_data.effect)
        app.log(f"Wound: {entry_data.name} ({kind})", "wound")
    else:
        app.log(f"Wound save PASSED (rolled {wenc.roll} vs DC {wenc.dc})", "passed")
    app.save(); app.refresh_all()
    self._close_roll_panel()
    wenc.phase = WoundEncPhase.IDLE
```

### 10c. Add Wound Card

```
[Minor Dropdown ▾]   [Major Dropdown ▾]
[Custom name MDTextField]
[+ Add Minor]   [+ Add Major]
[Random Minor]  [Random Major]   (flat buttons)
```

Dropdowns list all entries from `MINOR_WOUND_TABLE` / `MAJOR_WOUND_TABLE`.
Format: "1: Sprained Ankle — ...(effect truncated to 40 chars)".

**Add wound flow:**
```python
def _on_add_wound(self, kind: str, name: str, effect: str):
    app.undo_stack.push(app.state, app.fm)
    app.state.add_wound(kind, name, effect)
    app.log(f"Wound added: {name} ({kind})", "wound")
    app.save(); app.refresh_all()
    PulseAnim().start(self._wound_card, BLOOD, BG_CARD2)
```

### 10d. Minor Wounds Card

Header: "MINOR WOUNDS ({n})" + "Long Rest cures" hint + remove icon.

List of minor wounds. Each item (56dp, tappable):
```
[Wound Name]            (TEXT_BRIGHT)
[Minor · cured? · Time] (TEXT_DIM)
```

Tap: show full effect in inline detail area.

```
[Cure]  [Remove]           (action row under details)
```

**Cure** sets `wound.cured = True`, logs, saves.
**Remove** removes from list entirely.

### 10e. Major Wounds Card

Same structure as minor. Header: "MAJOR WOUNDS ({n})" + "Greater Restoration" hint.

### 10f. Wound Effects Panels

One for minor, one for major. Each is an `AccentCard` showing:
```
[Wound Name]        (TEXT_BRIGHT)
[Kind · Roll]       (TEXT_DIM)
[Full effect text]  (TEXT_DIM, multiline)
```

PulseAnim target: `_focus_wound_effects()`.

### 10g. Wound Rules Section

`MDExpansionPanel`. Content: `WOUND_RULES_TEXT` from FSM-6.

---

## 11. tab_spells.py — Complete Specification (NEW TAB)

This tab is entirely absent from the existing Android code. It implements the
Healing Spells system from FSM-6's 4th tab. Accent color: SILVER.

### 11a. Layout

```
[MINOR RESTORATION CARD]    silver border
[MAJOR RESTORATION CARD]    silver border (darker)
[SPELL RULES]               expandable
```

### 11b. Minor Restoration Card

```
"MINOR RESTORATION"                       (header, SILVER)
"2nd-level · Verbal/Somatic · 10 min"    (subtitle, TEXT_DIM)
"Cures one Minor Wound OR one Short or Long-term Madness."

"SELECT WOUND TO CURE"
[Minor wounds list — eligible (not cured)]

"SELECT MADNESS TO CURE"
[Short/Long-term madness list — eligible]

[Cast Minor Restoration]                  (SILVER button, 48dp)
```

**Cast flow:**
```python
def _cast_minor(self):
    sel_wound = self._minor_wound_list.selected
    sel_mad   = self._minor_mad_list.selected
    if not (sel_wound or sel_mad) or (sel_wound and sel_mad):
        show_snackbar("Select exactly one wound OR one madness to cure.")
        ShakeAnim().shake(self._minor_card); return
    app.undo_stack.push(app.state, app.fm)
    if sel_wound:
        sel_wound.cured = True
        app.log(f"Minor Restoration — cured wound: {sel_wound.name}", "shield")
    else:
        app.state.madnesses.remove(sel_mad)
        app.log(f"Minor Restoration — cured madness: {sel_mad.name}", "brain")
    app.save(); app.refresh_all()
```

### 11c. Major Restoration Card

```
"MAJOR RESTORATION"                               (header, SILVER darker)
"4th-level · Verbal/Somatic/Material · 1 hour"  (subtitle)
"Material: Diamonds worth ≥100gp (destroyed)."
"Requires DC 15 CON save."
"Cures one Major Wound OR one Indefinite Madness."

"SELECT MAJOR WOUND"
[Major wounds list — eligible (not cured)]

"SELECT INDEFINITE MADNESS"
[Indefinite madness list]

[DC 15 CON Save: auto-roll]   [Cast Major Restoration]
```

**Cast flow (with CON save):**
```python
def _cast_major(self):
    sel_wound = self._major_wound_list.selected
    sel_mad   = self._indef_mad_list.selected
    if not (sel_wound or sel_mad) or (sel_wound and sel_mad):
        show_snackbar("Select exactly one major wound OR indefinite madness.")
        ShakeAnim().shake(self._major_card); return
    # CON save DC 15
    roll = random.randint(1, 20) + app.state.con_mod()
    passed = roll >= 15
    show_snackbar(f"CON save: rolled {roll} vs DC 15 — {'PASSED' if passed else 'FAILED'}")
    app.log(f"Major Restoration CON save: {roll} vs 15", "dice")
    if not passed:
        app.log("Major Restoration FAILED — spell fails", "failed"); return
    app.undo_stack.push(app.state, app.fm)
    if sel_wound:
        sel_wound.cured = True
        app.log(f"Major Restoration — cured major wound: {sel_wound.name}", "shield")
    else:
        app.state.madnesses.remove(sel_mad)
        app.log(f"Major Restoration — cured indefinite madness: {sel_mad.name}", "brain")
    app.save(); app.refresh_all()
```

### 11d. List Behavior

Both Restoration lists are read-only `RecycleView` or `ScrollView`-based lists.
Items highlight on tap (single-select). Ineligible items (cured wounds, wrong
madness type) are filtered out — the lists show only actionable entries.

If a list is empty, show a dim label: "No eligible wounds" / "No eligible madnesses".

---

## 12. Global Interaction Patterns

### 12a. Undo

- Undo button in header: `app.undo()`.
- Keyboard: `Window.bind(on_keyboard=...)` → Ctrl+Z or Android back (in context).
- Dims when stack is empty.
- After undo: `refresh_all()` + `show_snackbar("Undone")`.

### 12b. Error Handling

- Invalid numeric input: `ShakeAnim().shake(field)` + `show_snackbar("Invalid value")`.
- No fear selected for encounter: `show_snackbar("Select a fear first")`.
- Duplicate fear name: `show_snackbar("Fear already exists")`.
- Operation during active encounter: `show_snackbar("Finish the current encounter first")`.

### 12c. Tab Switching

- Tapping a tab header calls `app.switch_tab(name)`.
- The previously visible tab's content is kept but not refreshed.
- The newly visible tab is refreshed immediately via its `refresh()` method.
- Tab accent color: the `DividerLine` below the tab bar changes color to match
  the active tab.

### 12d. Soft Keyboard

- All `MDTextField` fields set `on_text_validate` to trigger the primary action.
- After action: `field.focus = False` to dismiss keyboard.
- `android.manifest` must set `SOFT_INPUT_MODE = resize` in buildozer.spec.

---

## 13. buildozer.spec — Complete Specification

```ini
[app]
title = Sanity Fear and Madness
package.name = sanityfearandmadness
package.domain = org.fsm
source.dir = .
source.include_exts = py,png,jpg,kv,atlas,md
source.include_patterns = assets/*
version = 2.0

requirements = python3,kivy==2.3.0,kivymd==1.2.0,Pillow

orientation = portrait
fullscreen = 0

android.api = 33
android.minapi = 26
android.archs = arm64-v8a, armeabi-v7a
android.allow_backup = True

android.manifest.user_permissions =
    WRITE_EXTERNAL_STORAGE,
    READ_EXTERNAL_STORAGE

# Soft keyboard resize mode
android.manifest = None   # use default; add resize via p4a hook if needed

[buildozer]
log_level = 2
warn_on_root = 1
```

**assets/ folder required files:**
```
assets/skull.png    — fear encounter overlay (OpenMoji skull, bundled locally)
assets/blood.png    — wound encounter overlay
assets/sword.png    — combat overlay (optional)
```

Do NOT rely on runtime download (desktop does this; Android cannot).
Pre-download and bundle all three PNGs in assets/.

---

## 14. Implementation Order

Follow this sequence to maintain a runnable app at every step:

### Phase 1 — Models (no UI, testable standalone)

1. Port all constants: `FEAR_STAGES`, `DESENS_*`, `FEAR_ENC_DC`, `THRESHOLDS`.
2. Port `FearManager` with full desens support.
3. Port `SanityState` with `apply_loss`, `apply_recovery` (auto-clear madness),
   `add_madness`, `add_madness_specific`, `add_wound`, `snapshot`, `restore`.
4. Replace madness tables with FSM-6 D20 named system.
5. Replace wound tables with FSM-6 entries.
6. Port `SaveManager` (use `App.user_data_dir`), `UndoStack`.
7. **Unit test** models in isolation (`python -c "from models import *; ..."`).

### Phase 2 — Infrastructure

8. Write `theme.py` with all color/size constants.
9. Write `animations.py` with `PulseAnim`, `OverlayAnim`, `ShakeAnim`, `ScreenFadeIn`.
10. Write `ui_utils.py` with `BorderCard`, `AccentCard`, `SectionHeader`, `custom_dialog`, `show_snackbar`.
11. Write `widgets.py`: `SanityBar` (BarAnim), `MadnessBanner` (pulse), `ExhaustionWidget`.

### Phase 3 — Main Shell

12. Write `main.py` `FSMApp.build()` with header, sanity bar, banner, sanity label,
    tab bar, scroll area. Stub tab content.
13. Wire `refresh_all()`, `log()`, `save()`, `undo()`.
14. Add back-button handler, ScreenFadeIn, session timer.
15. **Smoke test**: `python main.py` (desktop Kivy) — confirms layout, header, bar.

### Phase 4 — Fears Tab

16. Implement `tab_fears.py` top-to-bottom:
    a. Encounter card (without roll panel first)
    b. Severity tracker (2×2 grid)
    c. Severity effects card
    d. Desensitization tracker (4 rung buttons)
    e. Desensitization effects card
    f. Add fear row
    g. Active fears list
    h. Fear rules section
17. Wire all encounter logic (ENCOUNTER → [Failed/Passed] → [Confront/Avoid]).
18. Wire DC auto-fill, desens tracker, sanity preview.
19. Wire `_focus_stage_effects`, `_focus_desens_effects` pulse.
20. Add `OverlayAnim` for skull on encounter.
21. Wire `_handle_thresh` deferred call from Confront.
22. **Test**: add fear, set stage/desens, run encounters, confront, avoid, verify state.

### Phase 5 — Sanity Tab

23. Implement `tab_sanity.py`:
    a. Sanity controls card (preset buttons + custom amount row)
    b. Three madness category cards with dropdowns
    c. Active madness list
    d. Madness effects panel
    e. Madness rules section
24. Wire `_handle_thresh` popup.
25. Wire auto-clear madness logging on recovery.
26. **Test**: lose sanity, cross thresholds, add madnesses, recover, verify auto-clear.

### Phase 6 — Wounds Tab

27. Implement `tab_wounds.py`:
    a. Wound encounter card (with Calc DC)
    b. Add wound card (dropdowns + random)
    c. Minor/major wound lists
    d. Wound effects panels
    e. Wound rules section
28. Wire `OverlayAnim` for blood on wound encounter.
29. **Test**: wound encounter all 4 outcomes, add wounds, cure, remove.

### Phase 7 — Healing Spells Tab

30. Implement `tab_spells.py`:
    a. Minor Restoration card
    b. Major Restoration card (with CON save)
    c. Spell rules section
31. **Test**: cast both spells, verify cure logic, verify CON save fail path.

### Phase 8 — Polish + Android Build

32. Bundle assets (skull.png, blood.png, sword.png).
33. Test `ScreenFadeIn`, `ShakeAnim`, all `PulseAnim` callsites.
34. Verify save/load round-trip (save, quit, relaunch, confirm state).
35. Verify undo stack (50 operations).
36. Test session log dialog (open, scroll, copy).
37. **Smoke test on desktop**: `python main.py` — full flow, all tabs.
38. **Build**: `buildozer android debug`.
39. **Install and test on Android device or emulator**.
40. Fix orientation lock, soft keyboard, back button on-device.

---

## 15. Known Kivy/KivyMD Pitfalls

| Pitfall | Resolution |
|---------|------------|
| `MDCard` rejects `orientation` kwarg | Use `BoxLayout` + canvas background (already in ui_utils.py) |
| `MDSnackbar` API changed in KivyMD 2.x | Pin to KivyMD 1.2.0; use `MDLabel` child pattern |
| `adaptive_height=True` parent needs binding | Parent `ScrollView` must bind `height` to `minimum_height` |
| `GridLayout` equal rows | Use `row_force_default=True` + `row_default_height` |
| Widget refs invalidated after `clear_widgets` | Rebuild all refs inside each `refresh()` call |
| `Clock.schedule_once` deferred layout | Necessary for post-layout operations; use `lambda dt:` |
| PIL not available on Android by default | Add `Pillow` to buildozer requirements |
| Font `Segoe UI` is Windows-only | Never hardcode; use KivyMD `font_style` or `CoreLabel` default |
| `Window.opacity` may not work on Android | Wrap `ScreenFadeIn` in try/except; skip gracefully |
| Dropdowns (`Spinner` / `MDDropDownItem`) clip at screen edge | Use `MDDropdownMenu` with `position="bottom"` and `max_height` |
| `RecycleView` needs `ViewClass` set | Confirm `RecycleBoxLayout` or `RecycleGridLayout` as container |
| Android back button fires `key=27` | Bind `Window.on_keyboard`, always return `True` when consuming |

---

## 16. Feature Parity Checklist

### Header
- [ ] Character name (MDTextField, saves on validate/blur)
- [ ] WIS score + modifier chip (tap to edit, updates max_sanity)
- [ ] CON score + modifier chip (tap to edit)
- [ ] Exhaustion pips 0–6 (tappable ExhaustionWidget)
- [ ] HOPE checkbox (stores boolean, no game logic yet)
- [ ] Session timer HH:MM (updates every 60s)
- [ ] Undo button (dims when stack empty)
- [ ] Session Log button (opens dialog)

### Global
- [ ] Sanity bar (18-band gradient, BarAnim, threshold marks)
- [ ] Madness banner (pulse on threshold, shows active madness)
- [ ] Sanity label "X / Y"
- [ ] 4-tab bar (FEARS / SANITY / WOUNDS / SPELLS)
- [ ] Tab accent DividerLine changes color per tab
- [ ] Back button: dismiss dialog → cancel encounter → propagate

### Fears Tab
- [ ] Encounter card: fear label, DC auto-fill, ENCOUNTER button
- [ ] Roll panel: auto-rolled save, Failed/Passed row, Confront/Avoid row
- [ ] Sanity preview box (Confront math, Avoid math, threshold warning)
- [ ] Skull overlay animation on encounter start
- [ ] Extreme Severity: +1 Exhaustion before roll
- [ ] Severity tracker: 4 named cards (Low/Moderate/High/Extreme), tappable
- [ ] Severity effects card: name, dice, description
- [ ] Desensitization tracker: 4 rung buttons, teal, DC labels
- [ ] Desensitization effects card: rung name, DC, description
- [ ] Desens tracker and effects update on Confront / Avoid
- [ ] Desens effects pulse after Confront/Avoid
- [ ] Confront: desens rung +1, sanity loss, _handle_thresh deferred
- [ ] Avoid: severity +1, desens rung -1, sanity +2
- [ ] Avoid at Extreme Severity: add_random fear
- [ ] Add fear row: text field, Suggest button, Add Fear
- [ ] Active fears list: name + severity + desens secondary text
- [ ] Tap fear: selects, fills DC, updates trackers
- [ ] Remove selected fear
- [ ] Fear rules section (expandable, includes desens content)

### Sanity Tab
- [ ] Preset lose buttons: −1/−2/−3/−5/−10
- [ ] Preset recover buttons: +1/+2/+3/+5/+10
- [ ] Custom amount row: text field + LOSE + RECOVER
- [ ] DM +1d4 / DM +2d4
- [ ] Restore to Max
- [ ] _handle_thresh: Yes/No popup → auto-roll or skip
- [ ] Auto-clear Short-term on crossing above 75%
- [ ] Auto-clear Long-term on crossing above 50%
- [ ] Sanity controls pulse (PulseAnim)
- [ ] Short-term madness card: dropdown + custom field + Roll Random + Add
- [ ] Long-term madness card: same
- [ ] Indefinite madness card: same
- [ ] Active madness list: name (primary), kind+roll+time (secondary)
- [ ] Tap madness: shows full effect in detail area
- [ ] Remove selected madness
- [ ] Madness banner pulse on add
- [ ] Madness effects panel (PulseAnim target)
- [ ] Navigate to sanity tab on threshold
- [ ] Madness rules section (expandable)

### Wounds Tab
- [ ] Wound encounter: DC field, dmg field, Calc DC button, WOUND ENC
- [ ] Blood overlay animation on encounter start
- [ ] Roll panel: auto-rolled CON save, 4 outcome buttons
- [ ] Wound resolve: Minor on Fail, Major on Fail 5+
- [ ] Add wound: minor dropdown, major dropdown, custom field
- [ ] Random minor / random major buttons
- [ ] Minor wounds list: name + kind + time
- [ ] Major wounds list: name + kind + time
- [ ] Tap wound: shows full effect + Cure + Remove actions
- [ ] Cure wound (sets cured=True)
- [ ] Remove wound (removes from list)
- [ ] Wound effects panels (minor + major, PulseAnim targets)
- [ ] Wound rules section (expandable)

### Healing Spells Tab (NEW)
- [ ] Minor Restoration card: spell info, minor wound list, short/long madness list, Cast
- [ ] Cast Minor: validates selection (exactly one), cures wound or removes madness
- [ ] Major Restoration card: spell info, DC 15 CON save note, major wound list, indefinite madness list, Cast
- [ ] Cast Major: auto-rolls CON save DC 15, cures on pass, fails on fail
- [ ] Spell rules section

### Save / Load
- [ ] JSON save to `App.user_data_dir / SAVE_FILE_NAME`
- [ ] Loads on startup, restores full state
- [ ] Backwards compatible with old flat fear format
- [ ] enc_history saved as list of dicts

### Animations
- [ ] BarAnim (smoothstep ease) on sanity bar
- [ ] PulseAnim on severity effects, desens effects, madness effects, wound effects, sanity controls
- [ ] OverlayAnim: skull (fear) and blood (wound)
- [ ] MadnessBanner cosine pulse
- [ ] ScreenFadeIn on launch (graceful fallback if not supported)
- [ ] ShakeAnim on invalid input

---

*End of Deployment Plan 2 — covers every feature in FSM-6.py.*
*Source of truth: `C:\Users\Tom\Desktop\FSM\FSM-Desktop\FSM-6.py` (4831 lines)*
