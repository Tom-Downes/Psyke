# Psyke Android V10

This README documents the repository file-by-file, starting with `main.py` and then moving outward to the shared modules, feature tabs, build files, planning notes, assets, and generated cache files.

## What This Repo Is

- A Kivy/KivyMD mobile app for tracking sanity, fears, wounds, spells, hope, and exhaustion.
- A code-first UI project. There are no `.kv` layout files in the repo; the interface is assembled in Python.
- A flat top-level codebase. Several files currently mix UI, domain rules, persistence, animation, and feature flow logic in single large modules.

## Runtime-First Reading Order

- `main.py`
- `gl_preflight.py`
- `theme.py`
- `models.py`
- `widgets.py`
- `ui_utils.py`
- `tab_fears.py`
- `tab_sanity.py`
- `tab_wounds.py`
- `tab_spells.py`

## File-By-File Reference

### `main.py`

- The composition root and executable entry point for the app. This is the file that actually launches `SFMApp().run()`.
- Handles desktop startup concerns before Kivy loads. On Windows it sets the GL backend, runs the OpenGL compatibility check from `gl_preflight.py`, and registers the bundled DejaVu Sans font as `Symbols` so the UI can render arrows and special glyphs reliably.
- Defines several local UI classes instead of importing them from separate modules:
  `SessionLog`, `StatDialog`, `_AdvBtn`, `_StatChip`, `_SanityChip`, `_HopePortrait`, `HeaderCard`, `_TabBtn`, and `SFMApp`.
- `HeaderCard` is the persistent top-of-screen character control area. It owns character name input, exhaustion pips, WIS/CON editors, the sanity chip, hope toggle/portrait state, and the two advantage toggles used by fear and wound encounters.
- `SFMApp.build()` assembles the global shell:
  header, animated sanity bar, custom tab bar, separator line, and a `ScreenManager` with four screens (`fears`, `sanity`, `wounds`, `spells`).
- `SFMApp` also owns the long-lived application state references:
  `SanityState`, `FearManager`, `UndoStack`, `SaveManager`, character name, encounter history, and the session log widget.
- `_load()` hydrates saved state from JSON, restores madness and wound entries, restores fears using backward-compatible logic, replays encounter log history into the visible session log, and refreshes the whole UI.
- `refresh_all()` is an important performance/orchestration method. It updates the cheap global chrome first, then staggers the heavy tab refreshes across separate frames so all four screens do not relayout at once.
- `notify_event()` and `_flush_notify()` build the animated multi-row notification card shown at the bottom of the screen. These functions batch near-simultaneous events, add per-event action buttons, and deep-link back into the correct tab/widget.
- Back-button handling also lives here. The app dismisses open dialogs first, then cancels an active fear encounter if needed, and otherwise lets Android handle the hardware back behavior.
- The file tries to import a CI-generated `build_info.py`, but the fallback metadata object is currently not surfaced elsewhere in `main.py`.

### `gl_preflight.py`

- Windows-only startup safeguard for local desktop/dev use.
- Uses `ctypes` to create a tiny temporary Win32 window, choose a pixel format, create an OpenGL context, and query `GL_VERSION`, `GL_VENDOR`, and `GL_RENDERER`.
- Rejects two classes of unsupported environments:
  OpenGL versions below 2.0, and software fallback renderers such as `GDI Generic`.
- If the probe fails, it prints a diagnostic message, shows a native Windows message box with suggested fixes, and exits the process.
- Can be bypassed intentionally by setting `PSYKE_SKIP_GL_PREFLIGHT=1`.
- This file is not part of the Android runtime path; it exists to prevent confusing desktop launch failures during development.

### `theme.py`

- Central visual token file for the entire app.
- Defines the full palette as raw hex strings:
  backgrounds, borders, text tones, gold/blood/purple/silver accents, wound colors, fear stage colors, madness colors, and desensitization colors.
- Provides `k()`, the repo-wide helper that converts a `#rrggbb` string into a Kivy RGBA tuple.
- Precomputes common Kivy color tuples such as `K_BG`, `K_BORDER`, `K_GOLD`, `K_BLOOD`, and `K_DESENS`.
- Stores lightweight lookup dictionaries used elsewhere in the app:
  `MADNESS_COLORS`, `STAGE_COLORS`, and `DESENS_RUNG_COLORS`.
- Defines the KivyMD theme presets used by the app shell:
  `KIVY_PRIMARY`, `KIVY_ACCENT`, and `KIVY_STYLE`.

### `models.py`

- The domain/rules/persistence core of the project. Despite the filename, this module is much broader than plain models.
- Holds the main game constants such as sanity math, fear encounter defaults, exhaustion cap, undo depth, save filename, desensitization DCs, threshold breakpoints, and reusable rules text for fears, madness, wounds, and spells.
- Contains the content tables that drive the app:
  named short-term, long-term, and indefinite madness tables, plus minor and major wound tables.
- Provides general-purpose helpers for the rest of the codebase:
  `clamp`, `lerp`, `smoothstep`, `roll_d`, `safe_int`, `hex_lerp`, `stat_modifier`, `hex_to_kivy`, `roll_random_madness`, `roll_random_wound`, and `roll_insanity_duration`.
- Defines the core enums:
  `MadnessStage`, `EncounterPhase`, and `WoundEncPhase`.
- Defines the static metadata dataclasses:
  `MadnessInfo` and `FearStageInfo`, which pair rules text with colors and presentation details.
- `MadnessEntry` is the stored record for an active insanity effect. It knows how to serialize itself, deserialize itself, and expose human-friendly labels/colors by type.
- `WoundEntry` is the stored record for an active wound. It can optionally carry an `enc_record`, which lets wound encounters be reconstructed as richer history cards later.
- `SanityState` is the main mutable player-state container. It owns WIS/CON scores, current/max sanity, exhaustion, fired thresholds, wound list, madness list, hope state, and optional hope image path.
- `SanityState` also implements the main state transitions:
  recalculating sanity from WIS, applying sanity loss/recovery, rebuilding threshold flags, adding wounds/madness entries, and serializing/restoring snapshots for save/undo.
- `FearManager` owns all fear-specific state outside `SanityState`:
  fear names, fear severity levels, desensitization rung per fear, encounter counts, random fear suggestion/addition, and backward-compatible snapshot restore behavior.
- `EncounterState` and `WoundEncounterState` are the lightweight state machines used by the fear and wound encounter tabs.
- `SaveManager` chooses a per-platform config/save location and reads/writes `save_v6.json`.
- `UndoStack` stores bounded snapshots of `SanityState` and `FearManager`, giving the UI a simple global undo mechanism.

### `widgets.py`

- Shared canvas-driven widgets that are more visual than the reusable controls in `ui_utils.py`.
- `SanityBar` is the animated top-level sanity meter shown under the header.
- `SanityBar` does several jobs at once:
  smooth animation, threshold markers at 25/50/75 percent, dynamic stage-based gradient coloring, a moving indicator line, and a cached percentage label texture.
- `MadnessBanner` is intentionally a stub. It remains import-compatible for older code paths, but the actual banner has been removed from the visible layout.
- `ExhaustionWidget` draws the six numbered exhaustion pips, handles tap-to-set and tap-again-to-lower behavior, and supports a flashing highlight when exhaustion increases due to a wound encounter.
- This module is used by `main.py` to render the always-visible app chrome rather than tab-local content.

### `ui_utils.py`

- Shared UI kit for the whole app. This is a component library more than a utility file.
- `themed_field()` standardizes `MDTextField` styling so inputs use the app palette instead of KivyMD's default focus purple.
- Card primitives live here:
  `BorderCard`, `AccentCard`, `DescriptionCard`, and `Divider`.
- Reusable labels and text containers live here:
  `SectionLabel`, `CaptionLabel`, and `MultilineLabel`.
- Tap/select list widgets live here:
  `ListItem`, `SwipeFillListItem`, and `ExpandingEffectCard`.
- `ExpandingEffectCard` is especially important. It is the standard expanding row used across fears, insanity, wounds, and spells, combining selection, animated title fill, detail reveal, and flash highlighting in one widget.
- Animated text/fill helpers live here:
  `FillSwipeTitle` and `_DualFillLabel`.
- Navigation and disclosure helpers live here:
  `SwipePageIndicator`, `MorphArrow`, `HookMorphArrow`, and `ExpandableSection`.
- Action controls live here:
  `HopeButton`, `PickerButton`, and `NotificationActionButton`.
- The rules renderer also lives here. `populate_rules_section()` parses plain text rules into headings, step labels, separators, and body copy inside an `ExpandableSection`.
- `EventNotificationBanner` is an older floating banner component. The current app flow mostly uses the richer batched notification card built directly in `main.py`, but this file still contains the earlier reusable overlay implementation.
- A practical takeaway for future maintenance:
  this file is a shared widget library and would be a strong candidate for being split into smaller UI component modules during any refactor.

### `tab_fears.py`

- The fear management screen and one of the two biggest feature modules in the repo.
- Builds a two-page swipe layout.
- Page 0 contains the live fear encounter launcher, encounter history, add-fear controls, fear list, and fear rules.
- Page 1 contains the selected-fear context banner, fear severity cards, desensitization cards, and fear rules again for the detail side of the feature.
- Defines `_EncTab`, the custom encounter-stage rail widget used to show stage progression with reveal, sweep, and committed-state visuals.
- Defines `EncounterListItem`, the expandable encounter card used for live and completed fear encounters. It handles open/close height logic, flashing, animated stroke effects, and keeping the encounter shell visually attached to the rail.
- `FearsTab` owns all feature state for the fear screen:
  selected fear, fear list widgets, severity/desens cards, active encounter object, encounter history widgets, page swipe state, and the active encounter stage tab set.
- `_build_encounter_section()` creates the main encounter shell. It includes a manually editable DC field, the `ENCOUNTER` button, the absolute-positioned stage rail, the live stage panels, and the encounter-history stack.
- `_build_fear_add_row()` creates the fear name input plus a suggestion dice button and add button.
- `_build_fear_list()` creates the selectable fear list with a trash action for removing the currently selected fear.
- `_build_severity_section()` and `_build_desens_section()` convert the rule data from `models.py` into `ExpandingEffectCard` lists on the detail page.
- The encounter flow is a full state machine:
  select a fear, press `ENCOUNTER`, roll a WIS save (with optional advantage), animate the save result, and if the save fails roll sanity loss based on fear severity.
- After a failed fear save, the module presents two consequence branches:
  `CONFRONT` and `AVOID`.
- `CONFRONT` lowers sanity by the rolled amount and increases desensitization. If the fear was already at maximum desensitization, the fear can be removed entirely.
- `AVOID` restores sanity by the rolled amount, increases fear severity, decreases desensitization, and at extreme severity can add a new random fear.
- The module also predicts threshold changes before the user commits the branch, then applies/cures madness entries through threshold handlers once the branch is finalized.
- It coordinates closely with the sanity tab by opening specific insanity cards from notifications and by reusing the same threshold semantics for add/cure behavior.
- It supports canceling an encounter, deleting stored encounter history, reopening the correct fear/severity/desens card from notifications, and logging every encounter step to the shared session log.

### `tab_sanity.py`

- The sanity and insanity feature screen.
- Uses a two-page swipe design.
- Page 0 contains direct sanity loss/recovery controls, the active insanity list, and the insanity rules section.
- Page 1 contains the insanity picker/add workflow plus the same rules content for the add page.
- Tracks the active insanity selection by object identity, which lets the screen preserve the open card across refreshes.
- `_build_sanity_card()` provides the raw number input plus `LOSE` and `RECOVER` actions.
- `_build_active_madness_card()` creates the expanding list of active insanity entries and the trash action used to remove the selected one.
- `_build_madness_add_card()` builds three add sections:
  short-term, long-term, and indefinite. Each has a picker button, preview panel, and `APPLY` button.
- `_open_madness_menu()` reads from the named madness tables in `models.py` and presents them through `MDDropdownMenu`.
- `_on_table_select()` stores the selection as pending, updates the preview copy, highlights the picker button, and expands the detail panel without yet altering state.
- `_apply_insanity()` commits the pending selection, writes a new `MadnessEntry`, refreshes the UI, saves, and emits a notification that can reopen the new entry.
- `_do_lose_input()` and `_do_recover_input()` handle manual sanity changes, log them, save them, and push the update through the global notification pipeline.
- `_handle_thresholds()` and `_handle_recovery_thresholds()` contain the feature's automatic rules logic:
  crossing downward may add a matching madness entry or cure an existing one on re-cross, while recovering upward removes the most recent matching madness effect when appropriate.
- `collapse_all()`, `open_madness()`, and `highlight_last_madness()` exist so tab switching and notifications can control the screen predictably.

### `tab_wounds.py`

- The wound feature screen and the second large staged encounter engine in the repo.
- Builds a two-page swipe layout.
- Page 0 contains wound encounters, wound encounter history, and wound rules.
- Page 1 contains manual wound addition from the minor/major wound tables.
- Reuses pieces from the fear module instead of reinventing the rail system:
  `_EncTab`, `clip_children`, and `EncounterListItem` are imported from `tab_fears.py`.
- Defines `_WoundEncTab`, a blood-themed version of the fear encounter tab with wound-specific stage colors.
- Defines `EncounterWoundCard`, a specialized wound card with two expansion levels:
  first the wound description opens, then a nested `ENCOUNTER DETAILS` shell can open underneath to reveal the frozen encounter record.
- `WoundsTab` tracks separate selection state for minor wounds, major wounds, wound encounter cards, and pending add-page selections.
- `_build_encounter_section()` creates the encounter launcher. Instead of entering a DC directly, the user enters damage taken and the module calculates the wound DC from that value.
- The wound encounter flow is fully automated:
  damage input -> computed DC -> CON save roll -> outcome classification -> sanity roll when needed -> wound result panel -> automatic state application.
- The outcome matrix is encoded directly in the module:
  `pass5` means no wound,
  `pass` means a minor wound plus `1d4` sanity loss,
  `fail` means a major wound plus `2d4` sanity loss,
  `fail5` means a major wound plus `2d4` sanity loss and `+1` exhaustion.
- `_populate_wound_stage()` renders the final wound-result panel before the state changes are applied.
- `_do_auto_complete()` is the key commit method. It pushes undo, applies the wound, adjusts exhaustion, applies sanity loss, resolves threshold-driven insanity side effects, attaches the encounter record to the wound, logs the event, saves, and schedules the resulting notifications.
- Encounter-derived wounds get an `enc_record` attached so the tab can rebuild them as richer history cards after reload rather than as plain wound rows.
- `_build_add_wound_card()` mirrors the insanity add-page structure with two sections:
  minor wound and major wound, each with picker, preview, and `APPLY`.
- `refresh()` distinguishes between plain wounds and encounter-backed wounds so it can place reloadable encounter wounds in the encounter history area while keeping plain wounds in the simpler list structures.
- The tab also supports removing a selected wound, removing an encounter-backed wound and its paired history widget, and opening/highlighting the correct wound card from notifications.

### `tab_spells.py`

- The healing/restoration feature screen.
- Builds two restoration panels and one collapsible rules panel inside a single scroll view.
- `Minor Restoration` targets either short-term/long-term madness or a minor wound.
- `Major Restoration` targets any madness or any wound, and explicitly preserves the "regeneration applies" note when curing a major wound.
- `refresh()` reconstructs four target lists on every update:
  minor-valid madness, minor wounds, all madness, and all wounds.
- The screen uses `ExpandingEffectCard` throughout so each possible cure target can be expanded, inspected, and selected before casting.
- The selection model keeps one active card for the minor spell area and one active card for the major spell area.
- `_on_cast_minor()` and `_on_cast_major()` remove the selected entry from application state, push undo, log the cure, save the new state, and send a notification summarizing what was cured.
- The module is mostly a coordinator over existing state owned by `SanityState`; it does not define new domain rules tables of its own beyond consuming `SPELL_RULES_TEXT`.

### `buildozer.spec`

- Android packaging and deployment configuration for Buildozer.
- Declares the app title (`Psyke`), package name/domain, source directory, packaged extensions, icon path, and Android presplash image.
- Excludes development-only and generated directories such as `__pycache__`, `.git`, `.venv`, `.github`, and temporary release folders from packaged builds.
- Pins the runtime requirements to `python3`, `kivy==2.3.0`, `kivymd==1.2.0`, and `plyer`.
- Locks the app to portrait orientation and targets Android API 35 with minimum API 26.
- Declares Android architectures for `arm64-v8a` and `armeabi-v7a`.
- Uses `android.accept_sdk_license = True` for non-interactive CI and sets `android:windowSoftInputMode=adjustResize` so on-screen keyboards work better with scrollable content.
- Stores the base app version (`8.0.0`) plus the numeric Android version code that the CI script updates per build.

### `build_aab_ci.sh`

- CI-focused release script for building a signed Android App Bundle.
- Requires signing credentials through environment variables:
  `ANDROID_KEYSTORE_BASE64`, `ANDROID_KEYSTORE_PASSWORD`, `ANDROID_KEY_ALIAS`, and `ANDROID_KEY_PASSWORD`.
- Decodes the keystore into a temporary local file before the build starts.
- Uses an inline Python helper to modify `buildozer.spec` before release:
  version, numeric version code, release artifact type, keystore path, and keystore alias/password settings are all inserted or updated automatically.
- Generates a `build_info.py` file during CI with `APP_VERSION`, `BUILD_SHA`, `BUILD_DATE_UTC`, and `BUILD_RUN`.
- Runs `buildozer -v android release`, tees the full log to `buildozer-aab.log`, signs the resulting `.aab` with `jarsigner`, verifies the signature, and copies the final artifact to `ABB/ABB-V5.aab`.
- Cleans up the temporary keystore file at the end of the script.

### `REFACTOR_PLAN.md`

- First-pass architecture/refactor planning document.
- Describes the current flat top-level structure as prototype-friendly but hard to maintain long-term.
- Proposes a layered future layout with `app`, `config`, `domain`, `services`, `ui`, and `features`.
- Serves as a "living plan" document intended to accumulate file-by-file findings and reorganization recommendations over time.
- Useful for understanding the repo author's initial refactor direction and the pain points that motivated it.

### `REFACTOR_PLAN_2.md`

- Second-pass, more opinionated refactor plan.
- Refines the earlier idea into a clearer feature-first architecture where `features/` own product behavior, `ui/` owns reusable presentation building blocks, `domain/` owns rules/state/tables, `services/` owns orchestration, and `app/` owns bootstrap/shell composition.
- Contains a more detailed target tree and stronger naming/cleanup guidance than the first plan.
- Best read as the newer architectural proposal rather than runtime documentation.

### `icon.png`

- Main application icon asset.
- Current image size is `1024x1024`.
- Used by `buildozer.spec` both as the app icon and the Android presplash image.

### `__pycache__/gl_preflight.cpython-311.pyc`

- Auto-generated bytecode cache for `gl_preflight.py`.
- Mirrors the source module for faster Python startup and is not the authoritative file to edit.

### `__pycache__/main.cpython-311.pyc`

- Auto-generated bytecode cache for `main.py`.
- Represents the compiled form of the app shell/composition root.

### `__pycache__/models.cpython-311.pyc`

- Auto-generated bytecode cache for `models.py`.
- Mirrors the compiled rules/state/persistence module.

### `__pycache__/tab_fears.cpython-311.pyc`

- Auto-generated bytecode cache for `tab_fears.py`.
- Mirrors the compiled fear feature module and encounter engine.

### `__pycache__/tab_sanity.cpython-311.pyc`

- Auto-generated bytecode cache for `tab_sanity.py`.
- Mirrors the compiled sanity/insanity feature screen.

### `__pycache__/tab_spells.cpython-311.pyc`

- Auto-generated bytecode cache for `tab_spells.py`.
- Mirrors the compiled healing/restoration feature screen.

### `__pycache__/tab_wounds.cpython-311.pyc`

- Auto-generated bytecode cache for `tab_wounds.py`.
- Mirrors the compiled wound feature module and encounter engine.

### `__pycache__/theme.cpython-311.pyc`

- Auto-generated bytecode cache for `theme.py`.
- Mirrors the compiled color token module.

### `__pycache__/ui_utils.cpython-311.pyc`

- Auto-generated bytecode cache for `ui_utils.py`.
- Mirrors the compiled shared UI kit.

### `__pycache__/widgets.cpython-311.pyc`

- Auto-generated bytecode cache for `widgets.py`.
- Mirrors the compiled shared canvas widget module.

## Notes

- There was no `README.md` in the repo before this file was added.
- `build_info.py` is referenced by the runtime/build flow but is not currently committed in this repository. It is generated by `build_aab_ci.sh` during CI builds.
- The `__pycache__` files are generated artifacts rather than source. They are included here only so the repo scan covers every file currently present in the working tree.
