# Refactor Plan

This document is the living plan for refactoring the project into a cleaner, more professional app structure.

It is cumulative. Each file analysis should update this document rather than creating separate planning notes.

## Current Assessment

The repository is still organized as a flat script-style codebase:

- `main.py`
- `models.py`
- `widgets.py`
- `ui_utils.py`
- `tab_fears.py`
- `tab_sanity.py`
- `tab_wounds.py`
- `tab_spells.py`
- `theme.py`

This layout is workable for a prototype, but it is not ideal for long-term maintenance because app bootstrap, feature UI, custom widgets, persistence orchestration, and view-controller logic are mixed together at the top level.

## Target Structure

Recommended direction for the new repository or major in-place restructure:

```text
psyke/
  app/
    __init__.py
    main.py
    bootstrap.py
    config/
      __init__.py
      theme.py
      fonts.py
      platform.py
    domain/
      __init__.py
      sanity.py
      fears.py
      wounds.py
      spells.py
      persistence.py
      undo.py
    services/
      __init__.py
      save_service.py
      session_log_service.py
      notification_service.py
      navigation_service.py
    ui/
      __init__.py
      app_shell.py
      dialogs/
        __init__.py
        stat_dialog.py
        session_log_dialog.py
      navigation/
        __init__.py
        tab_bar.py
      screens/
        __init__.py
        fears_screen.py
        sanity_screen.py
        wounds_screen.py
        spells_screen.py
      widgets/
        __init__.py
        header/
          __init__.py
          header_card.py
          stat_chip.py
          sanity_chip.py
          advantage_toggle.py
          hope_portrait.py
        notifications/
          __init__.py
          event_notification_card.py
        session/
          __init__.py
          session_log_panel.py
        shared/
          __init__.py
          sanity_bar.py
          exhaustion_widget.py
    features/
      fears/
      sanity/
      wounds/
      spells/
  tests/
    unit/
    integration/
```

## Why This Structure

- `app/main.py` should be a thin entry point only.
- `bootstrap.py` should handle app startup concerns such as platform checks, font registration, and build metadata fallback.
- `config/` should hold environment-specific setup and theme definitions.
- `domain/` should contain state, business rules, serialization models, and undo logic without UI code.
- `services/` should handle save/load orchestration, navigation, notifications, and session log state in a reusable way.
- `ui/screens/` should map to the app’s top-level tabs.
- `ui/widgets/` should hold reusable visual components with clear boundaries.
- `features/` can absorb feature-specific logic over time if tabs currently contain both UI and business behavior.

## File Analysis: `main.py`

### Section Inventory

Existing section headers in `main.py`:

1. `SESSION LOG WIDGET`
2. `STAT DIALOG`
3. `HEADER CARD`
4. `TAB BUTTON`
5. `MAIN APP`
6. `ENTRY POINT`

### What Each Section Does

#### `SESSION LOG WIDGET`

- Defines `SessionLog`, a scrollable visual log panel with color-coded entries and clipboard copy support.
- Responsibility is UI component behavior, not app bootstrap.

Recommended destination:

- `ui/widgets/session/session_log_panel.py`
- Dialog wrapper should eventually live separately in `ui/dialogs/session_log_dialog.py`

#### `STAT DIALOG`

- Defines `StatDialog`, a reusable input dialog for WIS/CON editing.
- This is a dialog component and should not live in the entry file.

Recommended destination:

- `ui/dialogs/stat_dialog.py`

#### `HEADER CARD`

- Defines `_AdvBtn`, `_StatChip`, `_SanityChip`, `_HopePortrait`, and `HeaderCard`.
- This section is really a cluster of reusable header subcomponents plus a header composition widget.
- It is the biggest non-entry concern in the file.

Recommended destination:

- `ui/widgets/header/advantage_toggle.py`
- `ui/widgets/header/stat_chip.py`
- `ui/widgets/header/sanity_chip.py`
- `ui/widgets/header/hope_portrait.py`
- `ui/widgets/header/header_card.py`

#### `TAB BUTTON`

- Defines `_TabBtn`, a custom tab-bar button.
- This belongs with app navigation widgets.

Recommended destination:

- `ui/navigation/tab_bar.py`

#### `MAIN APP`

- Defines `SFMApp`, which currently performs too many roles:
- app bootstrap
- root layout composition
- tab registration
- keyboard/back handling
- save/load orchestration
- global refresh orchestration
- notification batching and rendering
- dialog ownership
- session log ownership
- some undo behavior

Recommended destination:

- Keep a thin `SFMApp` class in `app/main.py` or `ui/app_shell.py`
- Move startup helpers to `app/bootstrap.py`
- Move save/load state hydration to `services/save_service.py`
- Move notification queue/render logic to `services/notification_service.py` plus `ui/widgets/notifications/event_notification_card.py`
- Move navigation/tab registration to `ui/app_shell.py` or `services/navigation_service.py`

#### `ENTRY POINT`

- Runs the app.
- This should remain minimal.

Recommended destination:

- `app/main.py`

## Structural Problems Found in `main.py`

### Poor Separation of Concerns

- `main.py` mixes platform bootstrapping, font registration, build metadata fallback, UI widget definitions, dialog definitions, navigation UI, application state coordination, persistence, and notification rendering.
- `HeaderCard` directly reaches into the running app via `App.get_running_app()`, which tightly couples a reusable widget to the app singleton.
- `SFMApp` knows too much about child widget internals such as `self._fears_tab._enc.active` and `self._header._name_field`.
- Load logic reconstructs domain entities directly inside the app shell rather than through a mapper or persistence service.

### Overlapping or Redundant Logic

- `StatDialog` clamps to `1..30` inline instead of using the imported domain constants `WIS_MIN`, `WIS_MAX`, `CON_MIN`, and `CON_MAX`.
- Notification construction, animation, scheduling, and dismissal all live in a single long method (`_flush_notify`), mixing orchestration and rendering.
- `refresh_all()` updates both lightweight shell chrome and heavy tab refreshes, which suggests the app shell is compensating for overly broad refresh contracts in child tabs.

### Dead, Legacy, or Suspicious Code

- `MadnessBanner` is instantiated for compatibility but never added to the root layout, making it effectively legacy retention code in `main.py`.
- `build_info` fallback values are defined, but `BI.APP_VERSION` and `BI.BUILD_SHA` are not referenced in this file.
- `WIS_MIN`, `WIS_MAX`, `CON_MIN`, and `CON_MAX` are imported but not used in `main.py`.
- `_on_undo()` and `_on_show_log()` exist in the app class, but they do not appear to be wired from this file. Their callers should be confirmed during later file passes.
- `_on_hope_image()` is retained even though `_HopePortrait` explicitly says image picking is unused by design.

### Encapsulation Problems

- `HeaderCard` mutates app state and persists directly. That makes it both a view and a controller.
- `SFMApp._load()` mutates `SanityState`, `FearManager`, header field UI, and session log UI in one place.
- `SFMApp._on_keyboard()` reaches into a private fear-tab encounter object.

### Formatting and Encoding Issues

- `main.py` contains mojibake in section dividers and comments such as `â•`, `â€”`, and `â€“`.
- Comment header style is inconsistent between top-level banners and inline separators.
- Some comments describe removed behavior that should now be deleted instead of documented as compatibility leftovers.
- Internal helper classes use leading underscores inconsistently: some are true private UI fragments, but others are effectively reusable components and should be promoted to normal module-level names once extracted.

## Proposed Split for `main.py`

### Keep in the App Entry Layer

- `SFMApp` only if reduced to app-shell wiring
- `if __name__ == "__main__": ...`

### Move to Bootstrap Layer

- Windows OpenGL preflight
- Unicode font registration
- build metadata fallback

### Move to UI Dialogs

- `StatDialog`
- session log dialog wrapper currently built inline in `_on_show_log()`

### Move to UI Widgets

- `SessionLog`
- `_AdvBtn`
- `_StatChip`
- `_SanityChip`
- `_HopePortrait`
- `HeaderCard`
- `_TabBtn`

### Move to Services

- save/load hydration logic from `_load()`
- notification batching and display logic from `notify_event()` and `_flush_notify()`
- tab switching policy if shared behavior grows
- session log state if it must survive beyond a single visual widget instance

## Initial Cleanup Tasks

- Replace mojibake characters and normalize file encoding to UTF-8.
- Standardize section headers and eventually remove large banner comments once modules are small enough to be self-explanatory.
- Remove unused imports from `main.py`.
- Confirm whether `MadnessBanner` should be deleted entirely.
- Confirm whether hope image support is real or legacy.
- Replace direct widget-to-app mutation patterns with callback-based or controller/service-based communication.
- Replace direct app access to child private attributes with explicit public methods.

## Files to Create

- `app/main.py`
- `app/bootstrap.py`
- `app/config/fonts.py`
- `app/config/platform.py`
- `app/ui/app_shell.py`
- `app/ui/dialogs/stat_dialog.py`
- `app/ui/dialogs/session_log_dialog.py`
- `app/ui/navigation/tab_bar.py`
- `app/ui/widgets/session/session_log_panel.py`
- `app/ui/widgets/header/header_card.py`
- `app/ui/widgets/header/advantage_toggle.py`
- `app/ui/widgets/header/stat_chip.py`
- `app/ui/widgets/header/sanity_chip.py`
- `app/ui/widgets/header/hope_portrait.py`
- `app/ui/widgets/notifications/event_notification_card.py`
- `app/services/save_service.py`
- `app/services/notification_service.py`
- `app/services/session_log_service.py`

## Files to Simplify Later

- `models.py`
- `widgets.py`
- `ui_utils.py`
- `tab_fears.py`
- `tab_sanity.py`
- `tab_wounds.py`
- `tab_spells.py`

---

## Analysis: `tab_wounds.py`

### What The Current Sections Do

- `Page state`, `Page 0`, `Page 1`, `Page indicator`, and `Swipe detection` implement a two-page swipeable screen with one page for encounters and active wounds, and a second page for manually adding wounds.
- `Build encounter card` creates the full wound encounter workflow UI, including DC and damage input, roll result display, a hope action row, and the resolution buttons.
- `Build active wound card` renders the active minor and major wound lists plus the shared remove action.
- `Build add wound card` renders the manual wound-add workflow, including separate minor and major pickers, previews, and apply actions.
- `Internal helpers` mixes app-shell bridge methods, panel expand/collapse behavior, wound-label formatting, threshold notification helpers, and wound preview cleanup.
- `Public refresh` rebuilds both active wound lists and restores the selected/open card state.
- `Encounter` executes the wound encounter flow, including rolling, hope use, resolution, wound creation, sanity loss, threshold handling, exhaustion changes, logging, persistence, and notifications.
- `Add wound` applies a wound manually and triggers refresh, save, and notification behavior.
- `Active list interactions` manages open/close state for expanded wound detail cards and provides `open_wound()` as a public navigation helper.
- `Remove wound` deletes the selected minor or major wound and refreshes the screen.

### Structural Problems

- `tab_wounds.py` is not just a screen file. It currently owns screen composition, encounter-state orchestration, manual add workflows, threshold side effects, logging, persistence calls, notification scheduling, and active-list interaction behavior.
- The `_app()`, `_push_undo()`, `_save()`, `_log()`, and `_snack()` helper cluster confirms the same missing controller/service boundary already seen in `tab_fears.py` and `tab_sanity.py`.
- Minor and major wound flows are duplicated in several places:
  - separate preview widgets and apply actions in the add-wound panel
  - separate open-state handlers in `_on_minor_tap()` and `_on_major_tap()`
  - separate remove handlers in `_on_remove_minor()` and `_on_remove_major()`
  - duplicated notification/open-card wiring in `refresh()` and `_resolve()`
- The two-page swipe/navigation system is nearly the same architectural pattern as `tab_sanity.py` and should not remain independently implemented per feature.
- Encounter resolution is overloaded. `_resolve()` currently handles gameplay outcomes, sanity loss, threshold processing, exhaustion changes, logging, UI notifications, refresh timing, and persistence in one method.
- `open_wound()` is effectively a public feature API, which is good to preserve, but it should live on a clearer screen/controller boundary after refactor.

### Redundant, Overlapping, or Legacy Code

- `_on_minor_tap()` and `_on_major_tap()` are near-mirror implementations and should become one shared selection/open-state helper parameterized by severity.
- `_on_remove_minor()` and `_on_remove_major()` are also near-mirror implementations and should become one shared removal path.
- The add-wound UI duplicates the same severity-specific picker/preview/apply structure twice, which suggests a reusable `wound_picker_panel` component.
- Threshold notification logic overlaps conceptually with the threshold behavior already identified in `tab_fears.py` and `tab_sanity.py`. This should be centralized rather than remaining feature-local.
- The page indicator and swipe navigation overlap strongly with `tab_sanity.py`, which points to a reusable paged feature-screen container or shared swipe-navigation module.

### Dead Or Unused Code And Import Cleanup

- `Color` and `Rectangle` are imported but not used.
- `MDFlatButton` is imported but not used.
- `open_wound()` should stay, but some of the surrounding selection logic can likely be collapsed once list ownership is simplified.

### Formatting And Encoding Issues

- `tab_wounds.py` contains the same mojibake comment divider corruption seen in other files.
- The file still uses compressed single-line guard clauses and tightly packed state updates that make scanning harder than it needs to be.
- Naming is reasonably consistent, but the file is still too large and too responsibility-dense to remain readable long-term.

### Recommended Split For `tab_wounds.py`

- `features/wounds/screens/wounds_screen.py`
- `features/wounds/views/wound_encounter_panel.py`
- `features/wounds/views/active_wounds_panel.py`
- `features/wounds/views/wound_picker_panel.py`
- `features/wounds/views/wound_rules_panel.py`
- `features/wounds/controllers/wound_encounter_controller.py`
- `features/wounds/controllers/wound_selection_controller.py`
- `features/wounds/presenters/wound_notifications.py`

### Why The Sections Should Move

- The screen should compose panels and expose public feature entry points like `open_wound()`, but it should not own encounter resolution details.
- The encounter card and encounter-resolution behavior should move apart: view code belongs in a panel module, while roll/outcome/state-transition logic belongs in a controller.
- The active-wounds list should become its own view so selection behavior and card expansion logic are isolated from encounter logic.
- The add-wound panel should be extracted because it is a self-contained workflow and contains reusable severity-picker structure that should not stay embedded in the screen file.
- Threshold and notification formatting should move closer to shared feature services/presenters so wounds, fears, and sanity do not keep re-implementing related behavior.

### Additional Cleanup Tasks Identified From `tab_wounds.py`

- Remove unused imports: `Color`, `Rectangle`, and `MDFlatButton`.
- Merge severity-specific selection and removal handlers into generalized helpers.
- Extract the repeated add-wound picker UI into a reusable wound-specific panel.
- Consolidate encounter outcome handling so the UI does not manually coordinate logging, refresh timing, save calls, and notification construction.
- Normalize text encoding to UTF-8 and replace corrupted comment banners.

## Target Structure Refinement After `tab_wounds.py`

The target structure should now explicitly account for wounds as a full feature package, not a standalone tab module:

```text
psyke/
  app/
    features/
      sanity/
        screens/
        views/
        controllers/
      fears/
        screens/
        views/
        controllers/
      wounds/
        screens/
          wounds_screen.py
        views/
          active_wounds_panel.py
          wound_encounter_panel.py
          wound_picker_panel.py
          wound_rules_panel.py
        controllers/
          wound_encounter_controller.py
          wound_selection_controller.py
        presenters/
          wound_notifications.py
    ui/
      navigation/
        paged_screen.py
      widgets/
        shared/
```

---

## Analysis: `tab_spells.py`

### What The Current Sections Do

- `Build: Minor Restoration` creates the UI for curing either a short/long madness or a minor wound.
- `Build: Major Restoration` creates the UI for curing any madness or any wound, including the regeneration note for major wounds.
- `Panel expand/collapse` defines generic height/visibility helpers for expandable panels.
- `Helpers` mixes app-shell bridge methods, wound/madness summary formatting, snackbar display, and selection reset helpers.
- `Public refresh` rebuilds four selection lists:
  - minor-cast madness targets
  - minor-cast minor wound targets
  - major-cast madness targets
  - major-cast all wound targets
- `Selection handlers` manages open-card state and selected indices for the four target groups.
- `Cast actions` performs the actual cure logic, including state mutation, undo, logging, save, refresh, and notifications.

### Structural Problems

- `tab_spells.py` is smaller than the other feature files, but it still mixes screen composition, target-list rendering, selection state management, cast logic, notification formatting, and persistence orchestration.
- The `_app()`, `_push_undo()`, `_save()`, `_log()`, and `_snack()` pattern appears again here, which reinforces that app-level actions need a cleaner feature/service boundary.
- Minor and major restoration flows are structurally very similar, but the current implementation duplicates list rendering, selection handlers, and cast logic instead of expressing the shared pattern directly.
- The file is named like a tab, but it is already behaving like a feature screen and should move into a proper `features/spells/` package.

### Redundant, Overlapping, Or Legacy Code

- `_on_minor_mad_tap()`, `_on_minor_wound_tap()`, `_on_major_mad_tap()`, and `_on_major_wound_tap()` are near-duplicate selection handlers and should become a generalized selection helper.
- `_on_cast_minor()` and `_on_cast_major()` repeat the same overall structure:
  - validate selection
  - mutate state
  - push undo
  - log
  - refresh
  - save
  - notify
  This should become a clearer spells controller or shared cure-action path.
- The four list-building blocks inside `refresh()` repeat the same `ExpandingEffectCard` population pattern with only data-source and formatting differences.

### Dead Or Unused Code And Import Cleanup

- `MDFlatButton` is imported but not used.
- `AccentCard`, `DescriptionCard`, and `MultilineLabel` are imported but not used.
- `_sync_panel_height()`, `_expand_panel()`, and `_collapse_panel()` are defined but not used.
- `_deselect_all_minor()` and `_deselect_all_major()` are defined but not used.
- If the unused panel helpers are removed, `Clock` also becomes unused.

### Formatting And Encoding Issues

- `tab_spells.py` contains the same mojibake comment divider corruption seen across the repo.
- The module header docstring already shows encoding damage (`â†’`) instead of clean punctuation.
- The file is more readable than several others, but repeated flow blocks still make it scan less cleanly than a production feature module should.

### Recommended Split For `tab_spells.py`

- `features/spells/screens/spells_screen.py`
- `features/spells/views/restoration_panel.py`
- `features/spells/views/spell_rules_panel.py`
- `features/spells/controllers/restoration_controller.py`
- `features/spells/presenters/restoration_notifications.py`

### Why The Sections Should Move

- The screen should compose the spell panels and expose refresh behavior, but the cast operations should not stay embedded in UI code.
- The restoration panels are structurally reusable and should be parameterized rather than hard-coded twice in one file.
- Notification and log message construction should move out of the screen so spell actions are easier to test and keep consistent with other features.
- Shared selection behavior should live in a smaller view/controller boundary instead of being repeated across four tap handlers.

### Additional Cleanup Tasks Identified From `tab_spells.py`

- Remove unused imports: `MDFlatButton`, `AccentCard`, `DescriptionCard`, and `MultilineLabel`.
- Remove unused helpers: `_sync_panel_height()`, `_expand_panel()`, `_collapse_panel()`, `_deselect_all_minor()`, and `_deselect_all_major()`.
- Extract a generalized restoration target list pattern so minor and major restoration do not keep duplicating card-building logic.
- Extract cure/cast behavior into a spells controller that owns state mutation, save, log, and notify sequencing.
- Normalize UTF-8 encoding and replace corrupted punctuation in the module docstring and section dividers.

## Target Structure Refinement After `tab_spells.py`

The target structure should now include spells as its own feature package alongside fears, sanity, and wounds:

```text
psyke/
  app/
    features/
      fears/
      sanity/
      wounds/
      spells/
        screens/
          spells_screen.py
        views/
          restoration_panel.py
          spell_rules_panel.py
        controllers/
          restoration_controller.py
        presenters/
          restoration_notifications.py
```

---

## Analysis: `theme.py`

### What The Current Sections Do

- `Raw hex constants` defines the base palette, feature colors, state colors, and desensitization rung colors.
- `Kivy float-tuple converters` provides `k()` plus precomputed RGBA tuple constants.
- `KivyMD custom_color palette entries` stores app-level framework theme configuration.
- `MADNESS_COLORS`, `STAGE_COLORS`, and `DESENS_RUNG_COLORS` provide semantic color lookup tables used across features.

### Structural Problems

- `theme.py` is compact, but it currently mixes several different concerns:
  - raw palette tokens
  - semantic feature/status colors
  - Kivy-specific conversion helpers
  - framework theme configuration
  - app-facing semantic lookup tables
- This is acceptable for a prototype, but not ideal for a production repository where design tokens, semantic color roles, and framework adapters should be easier to reason about independently.
- The module is globally imported as `theme as T` across the app, which makes it a central dependency sink instead of a narrower, more explicit design-system boundary.

### Redundant, Overlapping, Or Blurry Ownership

- `DESENS_RUNG_COLORS` exists in both `theme.py` and `models.py`, which confirms visual metadata is still duplicated across UI and domain layers.
- `STAGE_COLORS` and `MADNESS_COLORS` are presentation concerns and should live in a UI/design-system layer rather than being redefined or implied in feature/domain modules.
- The precomputed `K_*` tuples duplicate data that can be derived from the raw hex palette, which may be acceptable as a convenience layer, but should be isolated as a framework adapter rather than mixed directly with token definitions.

### Dead Or Unused Code And Cleanup Risks

- The `K_*` tuple constants appear to be defined only in `theme.py` and not referenced elsewhere in the repo. They are likely unused convenience leftovers.
- `KIVY_PRIMARY`, `KIVY_ACCENT`, and `KIVY_STYLE` are used by `main.py` and should stay, but they should move into a more explicit framework theme config module.
- `MADNESS_COLORS` and `STAGE_COLORS` are defined here but do not appear to be referenced elsewhere in the current repo, which suggests either dead exports or incomplete standardization.

### Formatting And Encoding Issues

- `theme.py` contains the same mojibake corruption seen in the rest of the repo, including comment dividers and inline comments like `â€”`.
- The file is otherwise readable, but the current all-caps flat constant layout would be easier to scan if split into tokens, semantic roles, and adapters.

### Recommended Split For `theme.py`

- `app/config/theme_tokens.py`
- `app/config/theme_roles.py`
- `app/config/kivy_theme.py`
- `ui/utils/color_conversion.py`

### Why The Sections Should Move

- Raw hex constants should become design tokens so they are easy to change without touching framework code.
- Semantic lookup tables should live in a roles layer that maps app concepts like madness stages and wound severity to visual styling.
- `k()` and any precomputed Kivy tuples should live in a framework adapter or color utility layer rather than beside design tokens.
- KivyMD app theme settings should be isolated in a config module so bootstrap code can consume them directly without importing the whole palette namespace.

### Additional Cleanup Tasks Identified From `theme.py`

- Remove duplicated desensitization color ownership from `models.py` and keep visual color definitions in the UI/theme layer only.
- Evaluate whether the unused `K_*` tuple exports should be deleted or regenerated on demand instead of kept as global constants.
- Decide whether `MADNESS_COLORS` and `STAGE_COLORS` should be standardized as the single semantic color mapping source or removed if truly unused.
- Normalize UTF-8 encoding and replace corrupted punctuation and comment banners.

## Target Structure Refinement After `theme.py`

The target structure should now separate design tokens, semantic theme roles, and Kivy-specific adapters:

```text
psyke/
  app/
    config/
      kivy_theme.py
      theme_roles.py
      theme_tokens.py
  ui/
    utils/
      color_conversion.py
```

## File Analysis: `widgets.py`

### Section Inventory

Existing section headers in `widgets.py`:

1. `SANITY BAR`
2. `MADNESS BANNER`
3. `EXHAUSTION WIDGET`

### What Each Section Does

#### `SANITY BAR`

- Defines `SanityBar`, an animated canvas-based header/status widget.
- Handles sanity percentage animation, gradient rendering, threshold markers, label texture caching, and post-animation callbacks.
- This is a real shared widget with app-shell value.

Recommended destination:

- `ui/widgets/shared/sanity_bar.py`

#### `MADNESS BANNER`

- Defines `MadnessBanner`, but it is currently a zero-size no-op compatibility stub.
- It is not a real active widget anymore.

Recommended destination:

- remove entirely once imports are updated
- if temporary compatibility is needed during migration, move to a very explicit legacy shim module such as `ui/widgets/legacy/madness_banner_stub.py`

#### `EXHAUSTION WIDGET`

- Defines `ExhaustionWidget`, a clickable exhaustion level control with local drawing and flash animation.
- This is a legitimate shared UI component, but it is currently still app-shell flavored rather than domain-agnostic.

Recommended destination:

- `ui/widgets/shared/exhaustion_widget.py`

### Structural Problems Found in `widgets.py`

### Poor Separation of Concerns

- `widgets.py` is a better candidate for a shared UI module than `main.py`, but it still bundles unrelated responsibilities: one active shared status widget, one dead compatibility shim, and one active input widget.
- `SanityBar` depends on domain metadata (`MADNESS`, `MadnessStage`) and generic helper functions imported from `models.py`, which keeps the widget coupled to the giant omnibus domain module ([widgets.py](/Users/Tom/Desktop/Psyke-Android-V10/widgets.py#L20), [widgets.py](/Users/Tom/Desktop/Psyke-Android-V10/widgets.py#L156)).
- `ExhaustionWidget` is presentation-only, but its callback contract is informal (`set_change_callback`) instead of being exposed as a clearer event API or bound property.

### Overlapping or Redundant Logic

- `MadnessBanner` is retained only for compatibility and duplicates the concept of a madness-status visual element without actually providing behavior ([widgets.py](/Users/Tom/Desktop/Psyke-Android-V10/widgets.py#L214)).
- `SanityBar` owns text cache, gradient cache, animation queueing, and rendering in one class. That is acceptable for a self-contained widget, but it should live in a dedicated file because the implementation is dense.
- `SanityBar` imports `FEAR_STAGES`, but that symbol is unused in this file ([widgets.py](/Users/Tom/Desktop/Psyke-Android-V10/widgets.py#L20)).

### Dead, Legacy, or Suspicious Code

- `MadnessBanner` is confirmed legacy compatibility code. It is instantiated in `main.py` but never added to the root widget tree, and its methods are no-ops ([main.py](/Users/Tom/Desktop/Psyke-Android-V10/main.py#L730), [widgets.py](/Users/Tom/Desktop/Psyke-Android-V10/widgets.py#L214)).
- `App` is imported in `widgets.py` but unused ([widgets.py](/Users/Tom/Desktop/Psyke-Android-V10/widgets.py#L11)).
- `StringProperty` exists only to support the legacy banner stub and becomes removable if that stub is deleted ([widgets.py](/Users/Tom/Desktop/Psyke-Android-V10/widgets.py#L18), [widgets.py](/Users/Tom/Desktop/Psyke-Android-V10/widgets.py#L216)).

### Encapsulation Problems

- `SanityBar.after_animation()` is effectively part widget API and part orchestration primitive for screen refresh timing. That coupling is workable, but it means the widget is currently coordinating app behavior instead of only exposing state/animation completion.
- `ExhaustionWidget.flash_pip()` is used externally by the app shell to emphasize state changes, which is fine, but it suggests the shell relies on a concrete internal widget rather than a more abstract header component API.

### Formatting and Encoding Issues

- `widgets.py` contains the same mojibake section separators and corrupted punctuation seen elsewhere.
- Several comments use corrupted arrow/emdash text such as `â†’` and `â€”`.
- Inline explanatory comments are useful here, but there are enough of them that the file would benefit from smaller modules rather than more comments.

## Proposed Split for `widgets.py`

### Keep as Shared Widgets

- `SanityBar` -> `ui/widgets/shared/sanity_bar.py`
- `ExhaustionWidget` -> `ui/widgets/shared/exhaustion_widget.py`

### Delete or Isolate as Legacy

- `MadnessBanner` -> delete after import cleanup
- if deletion must be staged, isolate it in `ui/widgets/legacy/madness_banner_stub.py`

### Support Modules To Introduce

- `ui/widgets/shared/animation_hooks.py` only if other widgets later need the same animation-completion behavior
- `ui/utils/textures.py` only if texture caching repeats elsewhere
- otherwise keep `SanityBar` self-contained in its own module

## Why `widgets.py` Should Be Split This Way

- `SanityBar` and `ExhaustionWidget` are both valid reusable widgets, but they solve different problems and should be independently discoverable.
- Removing `MadnessBanner` reduces false surface area for both human developers and AI tools.
- A dedicated `sanity_bar.py` file will make the animation behavior and rendering logic much easier to inspect without noise from unrelated widgets.
- A dedicated `exhaustion_widget.py` file makes it clearer that the widget is an input/control component rather than a generic decoration.

## Additional Cleanup Tasks Identified From `widgets.py`

- Remove unused imports: `App`, `FEAR_STAGES`, and likely `StringProperty` if `MadnessBanner` is deleted.
- Normalize encoding and replace corrupted separators/comments with UTF-8 text.
- Ensure `SanityBar` imports its stage palette from a narrow domain or presentation module rather than the whole current `models.py`.
- Consider whether `after_animation()` should stay on the widget or move into a shell-level controller if multiple widgets begin driving orchestration timing.

## Target Structure Refinement After `widgets.py`

Shared shell widgets can now be scoped more clearly:

```text
psyke/
  app/
    ui/
      widgets/
        shared/
          sanity_bar.py
          exhaustion_widget.py
        header/
          header_card.py
          stat_chip.py
          sanity_chip.py
          advantage_toggle.py
          hope_portrait.py
        notifications/
          event_notification_card.py
        session/
          session_log_panel.py
        legacy/
          madness_banner_stub.py  # temporary only if needed
```

## File Analysis: `ui_utils.py`

### Section Inventory

Key sections and constructs present in `ui_utils.py`:

1. `themed_field`
2. `BorderCard`
3. `AccentCard`
4. `DescriptionCard`
5. `Divider`
6. `HopeButton`
7. `SectionLabel`, `CaptionLabel`, `MultilineLabel`
8. `ListItem`
9. `FillSwipeTitle`
10. `SwipeFillListItem`
11. `ExpandingEffectCard`
12. `NotificationActionButton`
13. `MorphArrow`
14. `PickerButton`
15. `_DualFillLabel`
16. `SwipePageIndicator`
17. `ExpandableSection`
18. `populate_rules_section` and rules parsing helpers
19. `EventNotificationBanner`

### What This File Actually Is

`ui_utils.py` is not a utility module in the normal sense. It is currently a mixed UI kit containing:

- low-level styling helpers
- card and label primitives
- interactive controls
- animated list-row components
- section/panel containers
- rules-text rendering logic
- navigation widgets
- notification widgets

That means it is acting more like a compressed design system plus feature widget layer than a true helper module.

### What Each Major Area Does

#### Styling / Foundation Helpers

- `themed_field`
- `BorderCard`
- `AccentCard`
- `DescriptionCard`
- `Divider`
- `SectionLabel`
- `CaptionLabel`
- `MultilineLabel`

These are the closest things to real reusable foundation components.

Recommended destination:

- `ui/foundation/fields.py`
- `ui/foundation/cards.py`
- `ui/foundation/labels.py`
- `ui/foundation/dividers.py`

#### Hope Control

- `HopeButton`

This is not a generic UI utility. It is a feature-specific control used in fear and wound encounters.

Recommended destination:

- `features/shared/widgets/hope_button.py`
- or `ui/widgets/encounters/hope_button.py`

#### List / Card Interaction Components

- `ListItem`
- `FillSwipeTitle`
- `SwipeFillListItem`
- `ExpandingEffectCard`

These are reusable interaction patterns, but they are more specialized than the foundation layer.

Recommended destination:

- `ui/widgets/lists/list_item.py`
- `ui/widgets/lists/swipe_fill_list_item.py`
- `ui/widgets/cards/expanding_effect_card.py`
- `ui/widgets/text/fill_swipe_title.py`

#### Picker / Arrow / Page Indicator Controls

- `NotificationActionButton`
- `MorphArrow`
- `PickerButton`
- `_DualFillLabel`
- `SwipePageIndicator`

These are control/navigation widgets and should be grouped together rather than left in a generic utility file.

Recommended destination:

- `ui/widgets/controls/notification_action_button.py`
- `ui/widgets/controls/picker_button.py`
- `ui/widgets/navigation/morph_arrow.py`
- `ui/widgets/navigation/swipe_page_indicator.py`

#### Expandable Rules Panel

- `ExpandableSection`
- rules parsing helpers
- `populate_rules_section`

This is a very specific pattern for rendering text content into a collapsible rules section. It is shared, but it is not a utility in the generic sense.

Recommended destination:

- `ui/widgets/sections/expandable_section.py`
- `ui/content/rules_renderer.py`

#### Legacy / Overlapping Notification UI

- `EventNotificationBanner`

This appears to be an older notification overlay implementation and is likely superseded by the newer notification card batching in `main.py`.

Recommended destination:

- delete if unused
- otherwise isolate under `ui/widgets/legacy/event_notification_banner.py`

### Structural Problems Found in `ui_utils.py`

### Poor Separation of Concerns

- The file mixes foundational UI primitives with feature-specific encounter controls, navigation widgets, rules rendering, and notification UI.
- `HopeButton` is shared only by encounter flows, not by the application generally, so it should not live beside cards, labels, and fields.
- `populate_rules_section()` is content rendering logic, not a general utility helper.
- `NotificationActionButton` is shell/notification-specific, while most of the rest of the file is feature UI or generic visual building blocks.

### Overlapping or Redundant Logic

- `ListItem`, `SwipeFillListItem`, and `ExpandingEffectCard` overlap conceptually as list-row / selection / reveal patterns and should be organized together so future deduplication is possible ([ui_utils.py](/Users/Tom/Desktop/Psyke-Android-V10/ui_utils.py#L367), [ui_utils.py](/Users/Tom/Desktop/Psyke-Android-V10/ui_utils.py#L592), [ui_utils.py](/Users/Tom/Desktop/Psyke-Android-V10/ui_utils.py#L743)).
- `MorphArrow` is reused by both `PickerButton` and `ExpandableSection`, which is a good sign it should be its own module rather than buried deep in a utility sink ([ui_utils.py](/Users/Tom/Desktop/Psyke-Android-V10/ui_utils.py#L1127), [ui_utils.py](/Users/Tom/Desktop/Psyke-Android-V10/ui_utils.py#L1219), [ui_utils.py](/Users/Tom/Desktop/Psyke-Android-V10/ui_utils.py#L1510)).
- `EventNotificationBanner` overlaps with the newer notification system in `main.py`, which already builds richer notification cards and action buttons ([ui_utils.py](/Users/Tom/Desktop/Psyke-Android-V10/ui_utils.py#L1738), [main.py](/Users/Tom/Desktop/Psyke-Android-V10/main.py#L885)).

### Dead, Legacy, or Suspicious Code

- `EventNotificationBanner` does not appear to be used anywhere else in the repository and is a strong removal candidate.
- `ListItem` also appears unused outside `ui_utils.py` comments and internal references, while newer flows use `SwipeFillListItem` and `ExpandingEffectCard`.
- `MDFlatButton` and `MDIconButton` are imported in `ui_utils.py`, but do not appear to be used in the file.
- The file is very large for a utility module at roughly 1,800 lines, which is itself a maintainability smell.

### Encapsulation Problems

- `populate_rules_section()` parses raw text, interprets formatting conventions, and instantiates concrete widget types directly. That couples content format, styling rules, and widget composition into one helper.
- Some widgets expose callback-style APIs while others rely purely on property mutation, with no consistent pattern across the file.
- `_DualFillLabel` is a private implementation detail of `SwipePageIndicator`, which is fine, but keeping both buried in a giant shared file makes the dependency harder to follow.

### Formatting and Encoding Issues

- `ui_utils.py` contains the same mojibake corruption seen in other files.
- Comment headers are helpful for orientation but the file is now too large for comment banners to be a sufficient organizational tool.
- Several comments still refer to replacement history and version-sensitive workarounds, which should be moved into migration notes or removed after restructuring.

## Proposed Split for `ui_utils.py`

### UI Foundation

- `ui/foundation/cards.py`
- `ui/foundation/labels.py`
- `ui/foundation/fields.py`
- `ui/foundation/dividers.py`

### Shared Interactive Widgets

- `ui/widgets/text/fill_swipe_title.py`
- `ui/widgets/cards/expanding_effect_card.py`
- `ui/widgets/lists/swipe_fill_list_item.py`
- `ui/widgets/lists/list_item.py` only if still needed after cleanup

### Shared Controls / Navigation

- `ui/widgets/controls/picker_button.py`
- `ui/widgets/controls/notification_action_button.py`
- `ui/widgets/navigation/morph_arrow.py`
- `ui/widgets/navigation/swipe_page_indicator.py`

### Section / Content Rendering

- `ui/widgets/sections/expandable_section.py`
- `ui/content/rules_renderer.py`

### Feature-Oriented Widgets

- `features/shared/widgets/hope_button.py`

### Legacy Removal Candidates

- `ui/widgets/legacy/event_notification_banner.py` only if temporary isolation is needed
- otherwise delete `EventNotificationBanner`

## Why `ui_utils.py` Should Be Split This Way

- A foundation layer should stay extremely easy to scan and should only contain true primitives.
- Feature-specific controls like `HopeButton` should live near the encounter flows that use them.
- Navigation widgets and picker controls are reusable, but they are a different responsibility from cards, labels, and text rendering.
- Rules rendering is a content presentation concern and should be easy to update without reading through unrelated widgets.
- Breaking this file apart will make future AI-assisted edits much safer because changes to cards, list interactions, and rules rendering will be isolated.

## Additional Cleanup Tasks Identified From `ui_utils.py`

- Remove unused imports such as `MDFlatButton` and `MDIconButton`.
- Confirm whether `ListItem` is still needed; remove it if the newer swipe-fill row has fully replaced it.
- Delete or isolate `EventNotificationBanner` after verifying it is no longer used.
- Normalize encoding and replace corrupted separators/arrows/punctuation.
- Standardize interaction APIs across widgets where practical: explicit callbacks, bound properties, or public methods instead of a mixture of patterns.
- Re-evaluate whether rules parsing should rely on content conventions embedded in free-form strings, or whether structured content objects would be better long term.

## Target Structure Refinement After `ui_utils.py`

The UI layer now splits more cleanly into foundation, widgets, navigation, and content rendering:

```text
psyke/
  app/
    ui/
      foundation/
        cards.py
        dividers.py
        fields.py
        labels.py
      content/
        rules_text.py
        rules_renderer.py
      widgets/
        cards/
          expanding_effect_card.py
        controls/
          notification_action_button.py
          picker_button.py
        lists/
          list_item.py
          swipe_fill_list_item.py
        navigation/
          morph_arrow.py
          swipe_page_indicator.py
        sections/
          expandable_section.py
        shared/
          sanity_bar.py
          exhaustion_widget.py
      features/
        shared/
          widgets/
            hope_button.py
```

## File Analysis: `tab_fears.py`

### Section Inventory

Major sections and embedded responsibilities visible in `tab_fears.py`:

1. `_EncTab`
2. `clip_children`
3. `ENCOUNTER LIST ITEM` / `EncounterListItem`
4. `FEARS TAB` / `FearsTab`
5. page indicator and swipe navigation logic
6. encounter card/builders
7. fear list / add fear / severity / desensitization / rules builders
8. encounter stage shell and panel builders
9. encounter event handlers
10. threshold and recovery threshold handling

### What This File Actually Is

`tab_fears.py` is not just a screen file. It currently contains:

- the fears screen layout
- a two-page navigation system
- multiple custom encounter widgets
- encounter shell/stage animation logic
- fear list state handling
- encounter orchestration and resolution logic
- threshold side effects and sanity interactions
- logging and notification triggers
- replay/frozen encounter rendering

This is effectively an entire feature package flattened into one file.

### What Each Major Area Does

#### `_EncTab`

- Custom animated stage-tab widget for the fear encounter rail.
- Handles custom drawing, reveal/commit animations, and state styling.

Recommended destination:

- `features/fears/widgets/encounter_stage_tab.py`

#### `clip_children`

- Stencil helper for clipping child drawing to a widget’s bounds.
- This is a generic canvas utility, but it currently lives inside the fears feature file.

Recommended destination:

- `ui/utils/clipping.py`

#### `EncounterListItem`

- Feature-specific expandable list item that hosts idle/live/completed encounter modes.
- This is a substantial widget in its own right.

Recommended destination:

- `features/fears/widgets/encounter_list_item.py`

#### `FearsTab`

- Main fears screen implementation.
- Builds the two-page layout, fear selection UI, severity/desensitization views, encounter shell, and rules panel.
- Also orchestrates the encounter flow and cross-feature side effects.

Recommended destination:

- screen composition to `features/fears/screens/fears_screen.py`
- event/controller logic to `features/fears/controllers/fears_controller.py`

#### Encounter Shell / Stage Panels / Frozen Replay

- `_build_encounter_section()`
- `_open_encounter_stage()`
- `_reset_enc_ui()`
- `_show_roll_panel()`
- `_build_frozen_encounter_shell()`
- various stage reveal/retract and layout helpers

These form a distinct feature subsystem and should not remain inline inside the screen module.

Recommended destination:

- `features/fears/widgets/encounter_flow_shell.py`
- `features/fears/widgets/frozen_encounter_view.py`
- `features/fears/controllers/encounter_stage_controller.py`

#### Fear List / Severity / Desensitization / Rules Builders

- `_build_fear_list()`
- `_build_fear_add_row()`
- `_build_severity_section()`
- `_build_desens_section()`
- `_build_rules_panel()`

These are screen composition concerns and can stay close to the screen, but should be broken into smaller view modules or builder modules.

Recommended destination:

- `features/fears/views/fear_list_panel.py`
- `features/fears/views/fear_editor_panel.py`
- `features/fears/views/severity_panel.py`
- `features/fears/views/desensitization_panel.py`
- `features/fears/views/rules_panel.py`

#### Encounter Event Handlers

- `_on_encounter()`
- `_on_push()`
- `_on_avoid()`
- `_on_use_hope()`
- `_animate_roll_result()`
- `_handle_thresholds()`
- `_handle_recovery_thresholds()`

These methods represent business flow orchestration, not just UI rendering.

Recommended destination:

- `features/fears/controllers/fear_encounter_controller.py`

### Structural Problems Found in `tab_fears.py`

### Poor Separation of Concerns

- `tab_fears.py` mixes screen composition, custom widget classes, animation internals, feature-state orchestration, logging, notifications, persistence calls, and cross-feature sanity effects in one file ([tab_fears.py](/Users/Tom/Desktop/Psyke-Android-V10/tab_fears.py#L50), [tab_fears.py](/Users/Tom/Desktop/Psyke-Android-V10/tab_fears.py#L468), [tab_fears.py](/Users/Tom/Desktop/Psyke-Android-V10/tab_fears.py#L849)).
- `FearsTab` reaches directly into the app singleton for state, notifications, persistence, and tab navigation behavior, making the feature tightly coupled to the app shell.
- Threshold handling for sanity lives inside the fears feature, even though the resulting madness entries conceptually belong to the sanity domain/screen.

### Overlapping or Redundant Logic

- `EncounterListItem` visually overlaps with `ExpandingEffectCard`, but reimplements a large amount of interaction and drawing logic instead of sharing a smaller common primitive.
- The fear feature implements its own swipe/page system, stage-tab system, encounter replay view, and clipping helper all inside the screen file.
- `_on_push()` and `_on_avoid()` both contain large duplicated post-resolution branches after an early `return`, leaving unreachable legacy code in the file ([tab_fears.py](/Users/Tom/Desktop/Psyke-Android-V10/tab_fears.py#L3413), [tab_fears.py](/Users/Tom/Desktop/Psyke-Android-V10/tab_fears.py#L3596)).

### Dead, Legacy, or Suspicious Code

- Unreachable duplicate logic exists after `return` in both confrontation and avoidance handlers. This is a strong cleanup candidate because it creates maintenance risk and makes behavior harder to trust.
- `MDFlatButton` appears imported but unused in this file.
- `DESENS_COLOR` and `DESENS_COLOR_DK` are imported but do not appear to be used in the file.
- There is a disabled block `if False and stage == 4:` left behind in `_on_encounter()`, which is effectively dead legacy code.

### Encapsulation Problems

- The screen directly mutates app state, fear manager state, undo stack, logging, and persistence through app-wide access patterns rather than through a narrower feature controller/repository interface.
- `FearsTab` coordinates notification timing against `app._san_bar.after_animation(...)`, which couples feature logic directly to shell widget animation state.
- Encounter replay construction is embedded inside the screen module rather than being represented as a dedicated view over an encounter record.

### Formatting and Encoding Issues

- `tab_fears.py` has some of the worst encoding corruption in the repository, including heavily broken comment separators and mojibake inside comments and strings.
- Several comment headers are now unreadable enough that they reduce clarity rather than improving it.
- The file is large enough that comment-based organization is no longer sufficient for fast comprehension.

## Proposed Split for `tab_fears.py`

### Feature Package

- `features/fears/screens/fears_screen.py`
- `features/fears/controllers/fears_controller.py`
- `features/fears/controllers/fear_encounter_controller.py`
- `features/fears/views/fear_list_panel.py`
- `features/fears/views/fear_editor_panel.py`
- `features/fears/views/severity_panel.py`
- `features/fears/views/desensitization_panel.py`
- `features/fears/views/rules_panel.py`
- `features/fears/widgets/encounter_stage_tab.py`
- `features/fears/widgets/encounter_list_item.py`
- `features/fears/widgets/encounter_flow_shell.py`
- `features/fears/widgets/frozen_encounter_view.py`
- `features/fears/models/encounter_record.py`

### Shared Utilities / Shared UI

- `ui/utils/clipping.py`
- keep using shared UI foundation/widgets from the future `ui/` split instead of redefining them in this feature

## Why `tab_fears.py` Should Be Split This Way

- The fears feature is already large enough to justify its own package.
- The custom encounter rail and encounter list item are meaningful feature widgets and should be independently testable and readable.
- The screen should mainly compose panels and delegate feature actions, not contain full encounter state machines and replay rendering.
- Splitting replay rendering from live encounter orchestration will make future bug fixes much safer.
- A dedicated controller layer will reduce direct coupling between the fears feature and the app singleton.

## Additional Cleanup Tasks Identified From `tab_fears.py`

- Remove unreachable duplicate branches after `return` in `_on_push()` and `_on_avoid()`.
- Remove dead `if False` legacy code in encounter exhaustion handling.
- Remove unused imports such as `MDFlatButton`, `DESENS_COLOR`, and `DESENS_COLOR_DK` if later passes confirm they are truly unused.
- Normalize the file to UTF-8 and replace corrupted comment banners and arrows.
- Move generic stencil clipping out of the feature file.
- Isolate threshold handling logic so fears triggers domain events rather than directly owning sanity-side consequences.
- Reduce direct `App.get_running_app()` style feature coupling in favor of controller/service injection or explicit callbacks.

### Second-Pass Refinements For `tab_fears.py`

- `MDFlatButton` is now confirmed unused in `tab_fears.py`, so it should be removed rather than left as a tentative cleanup item.
- The helper layer `_app()`, `_push_undo()`, `_save()`, and `_log()` indicates the screen is compensating for a missing feature controller/service boundary.
- `open_fear()`, `open_severity()`, `open_desens()`, and `cancel_encounter()` form a small public API that should be preserved intentionally during extraction rather than being left as incidental screen methods.
- `_calc_threshold_preview()`, `_loss_threshold_preview()`, and `_recovery_threshold_preview()` point to a separate threshold-preview helper module for the fears feature.
- `_build_frozen_encounter_shell()` is large enough to justify its own replay view module rather than remaining an inline helper.

## Target Structure Refinement After `tab_fears.py`

The fears feature should become the first true feature package in the refactor:

```text
psyke/
  app/
    features/
      fears/
        controllers/
          fear_encounter_controller.py
          fears_controller.py
        models/
          encounter_record.py
          threshold_preview.py
        screens/
          fears_screen.py
        views/
          desensitization_panel.py
          fear_editor_panel.py
          fear_list_panel.py
          rules_panel.py
          severity_panel.py
        widgets/
          encounter_flow_shell.py
          encounter_list_item.py
          encounter_stage_tab.py
          frozen_encounter_view.py
```

## File Analysis: `tab_sanity.py`

### Section Inventory

Major sections and responsibilities visible in `tab_sanity.py`:

1. `SanityTab`
2. page indicator and swipe navigation
3. `Build: Sanity Card`
4. `Build: Add Insanity Card`
5. `Build: Active Insanity Card`
6. rules panel
7. helper layer (`_app`, `_push_undo`, `_save`, `_log`, `_snack`, preview panel helpers)
8. public refresh and deep-link helper (`open_madness`)
9. sanity input handlers (`_do_lose_input`, `_do_recover_input`)
10. insanity picker/apply flow
11. active-insanity selection/removal
12. threshold and recovery-threshold handling

### What This File Actually Is

`tab_sanity.py` is much more cohesive than `tab_fears.py`, but it still combines:

- the sanity screen layout
- a two-page navigation pattern
- add-insanity workflow UI
- active-insanity list behavior
- save/log/undo hooks
- threshold side effects and madness creation/cure logic

So it is closer to a real feature screen, but still broad enough to benefit from a feature package split.

### What Each Major Area Does

#### `SanityTab`

- Main sanity screen implementation.
- Composes the two pages, handles swiping, builds the panels, and coordinates active list selection and add-flow behavior.

Recommended destination:

- `features/sanity/screens/sanity_screen.py`

#### Page Navigation

- `_build_page_indicator()`
- `_update_indicator()`
- `_update_sv_positions()`
- `_animate_to_page()`
- `_animate_snap_back()`
- swipe handlers

This is screen-level behavior, but it repeats the same two-page swipe pattern used elsewhere.

Recommended destination:

- leave local for now in `features/sanity/screens/sanity_screen.py`
- later consider a shared two-page swipe container if the same pattern repeats across tabs

#### Sanity Input / State Controls

- `_build_sanity_card()`
- `_do_lose_input()`
- `_do_recover_input()`

This is a focused subfeature and can be separated from the list and add-flow concerns.

Recommended destination:

- `features/sanity/views/sanity_controls_panel.py`
- controller logic to `features/sanity/controllers/sanity_controller.py`

#### Add Insanity Flow

- `_build_madness_add_card()`
- `_open_madness_menu()`
- `_on_table_select()`
- `_apply_insanity()`
- `_add_insanity_now()`

This is a distinct subflow with its own UI state and preview lifecycle.

Recommended destination:

- `features/sanity/views/add_insanity_panel.py`
- controller logic to `features/sanity/controllers/add_insanity_controller.py`

#### Active Insanity List

- `_build_active_madness_card()`
- `refresh()`
- `_on_madness_tap()`
- `_on_remove_madness()`
- `highlight_last_madness()`
- `open_madness()`

This is another clear panel/module boundary.

Recommended destination:

- `features/sanity/views/active_insanity_panel.py`

#### Threshold Handling

- `_handle_thresholds()`
- `_handle_recovery_thresholds()`

These methods overlap conceptually with threshold-side behavior already seen in `tab_fears.py`, which suggests they should be centralized rather than duplicated across features.

Recommended destination:

- `features/sanity/controllers/threshold_controller.py`
- or, better, a domain/service-level threshold event handler shared by fears and sanity flows

### Structural Problems Found in `tab_sanity.py`

### Poor Separation of Concerns

- `tab_sanity.py` still mixes screen composition, picker-preview workflow, list behavior, save/log/undo hooks, and threshold business logic in one file.
- Like `tab_fears.py`, it relies on `_app()`, `_push_undo()`, `_save()`, and `_log()` helpers to reach back into app-level services instead of working through an explicit feature boundary.
- Threshold handling remains embedded in the UI layer rather than being modeled as a clearer domain/service responsibility.

### Overlapping or Redundant Logic

- The two-page swipe/page-indicator pattern overlaps with the same navigation approach used in other tabs.
- Threshold cure/add behavior duplicates ideas already implemented in `tab_fears.py`, even if the exact behavior is slightly different.
- The add-insanity preview system keeps a local `_pending` structure and manual panel expand/collapse state; that is fine in isolation, but it is really its own mini workflow controller.

### Dead, Legacy, or Suspicious Code

- Several imports appear unused in `tab_sanity.py`: `Color`, `SanityState`, `roll_d`, `clamp`, and `SANITY_BASE` do not appear to be referenced in this file.
- Because `open_madness()` relies on object identity after rebuild, there is a subtle risk if entries ever become copied/reloaded instead of preserved as the same objects.

### Encapsulation Problems

- The screen mutates app state directly when adding/removing/correcting madness entries.
- `refresh()` rebuilds the whole active-insanity list each time, which is simple but means selection state is reconstructed by object identity rather than through a stable entry id.
- `open_madness()` functions like a public navigation API but is just an incidental screen method today.

### Formatting and Encoding Issues

- `tab_sanity.py` has the same mojibake comment separators and corrupted punctuation seen elsewhere.
- The file is still readable, but the comment banners are beginning to do structural work that should be handled by smaller modules.
- Some strings still contain corrupted punctuation such as `Ã—` in duration text.

## Proposed Split for `tab_sanity.py`

### Feature Package

- `features/sanity/screens/sanity_screen.py`
- `features/sanity/controllers/sanity_controller.py`
- `features/sanity/controllers/add_insanity_controller.py`
- `features/sanity/controllers/threshold_controller.py`
- `features/sanity/views/sanity_controls_panel.py`
- `features/sanity/views/add_insanity_panel.py`
- `features/sanity/views/active_insanity_panel.py`
- `features/sanity/views/rules_panel.py`

### Shared / Cross-Feature Candidates

- shared threshold event handling between fears and sanity
- shared swipe-page container if the same pattern continues in wounds

## Why `tab_sanity.py` Should Be Split This Way

- The file already contains several natural panel boundaries that can become easy-to-scan view modules.
- Separating the add-insanity flow from the active-insanity list will make future changes to either one safer.
- Threshold logic should move away from the UI layer and become reusable from multiple feature flows.
- The sanity screen is much closer to a maintainable package split than fears, so it can serve as a model for later feature extraction.

## Additional Cleanup Tasks Identified From `tab_sanity.py`

- Remove unused imports: `Color`, `SanityState`, `roll_d`, `clamp`, and `SANITY_BASE`.
- Normalize text encoding and replace corrupted separators and duration punctuation.
- Consider introducing stable IDs for madness entries if future refresh/navigation flows become more complex than object identity can safely support.
- Extract the `_app()`, `_push_undo()`, `_save()`, and `_log()` dependency bridge into a controller or injected feature service layer.
- Reconcile threshold-add/cure behavior with the corresponding fears-side logic so the rules live in one place.

## Target Structure Refinement After `tab_sanity.py`

The sanity feature should become a parallel feature package with cleaner panel boundaries:

```text
psyke/
  app/
    features/
      sanity/
        controllers/
          add_insanity_controller.py
          sanity_controller.py
          threshold_controller.py
        screens/
          sanity_screen.py
        views/
          active_insanity_panel.py
          add_insanity_panel.py
          rules_panel.py
          sanity_controls_panel.py
```

## Naming Cleanup Targets

- Rename `SFMApp` to an app name that matches the product, likely `PsykeApp`.
- Replace ambiguous `tab_*` file names with `*_screen.py` or feature-based module names.
- Replace helper names like `_TabBtn` and `_AdvBtn` with explicit component names once extracted.
- Rename `SessionLog` and `HeaderCard` modules to match file responsibility exactly.

## Decisions to Validate in Later Passes

- Whether `models.py` should split into domain entities vs persistence DTOs.
- Whether each tab file should become a screen package with widgets, controllers, and domain helpers.
- Whether refresh scheduling can be replaced by more targeted state updates.
- Whether the notification system should be reusable across screens or scoped to the shell only.

## File Analysis: `models.py`

### Section Inventory

Existing section headers in `models.py`:

1. `CONSTANTS`
2. `DESENSITIZATION CONSTANTS`
3. `D20 MADNESS TABLES`
4. `WOUND TABLES`
5. `RULES TEXT`
6. `UTILITY`
7. `ENUMS`
8. `STATIC INFO DICTS`
9. `DATACLASSES`

### What Each Section Does

#### `CONSTANTS`

- Defines global gameplay and persistence constants such as stat ranges, sanity base, save file name, threshold definitions, and the default random fear pool.
- This is a mixed section because gameplay constants and persistence constants do not belong in the same module.

Recommended destination:

- gameplay constants to `domain/constants.py`
- fear pool to `domain/fears/catalog.py`
- persistence file name/version to `services/persistence/schema.py` or `services/save_service.py`

#### `DESENSITIZATION CONSTANTS`

- Defines desensitization DCs, labels, descriptions, and colors.
- This section mixes domain mechanics with presentation colors.

Recommended destination:

- DCs and rung semantics to `domain/fears/desensitization.py`
- display colors to `ui/presentation/fear_palette.py` or merged into theme configuration

#### `D20 MADNESS TABLES`

- Large static content table for short/long/indefinite madness results.
- This is content data, not executable domain logic.

Recommended destination:

- `domain/sanity/madness_tables.py`
- optionally `data/madness_tables.py` if the project later separates content from code

#### `WOUND TABLES`

- Large static content table for minor/major wounds.
- Like the madness tables, this is content data and should be separated from state classes and persistence code.

Recommended destination:

- `domain/wounds/wound_tables.py`

#### `RULES TEXT`

- Defines long UI-facing rules strings for fears, sanity, wounds, and spells.
- These are display resources, not domain models.

Recommended destination:

- `ui/content/rules_text.py`
- or separate per-feature files such as `features/fears/rules_text.py`, `features/sanity/rules_text.py`, etc.

#### `UTILITY`

- Contains generic helpers (`clamp`, `safe_int`, interpolation/color helpers) and random content selectors.
- This section is internally inconsistent because it mixes:
- generic math helpers
- UI color interpolation helpers
- dice/random helpers
- domain table selection helpers

Recommended destination:

- generic numeric helpers to `shared/utils/numbers.py`
- dice/random helpers to `domain/shared/dice.py`
- UI color helpers to `ui/utils/colors.py`
- madness/wound selection logic to `domain/sanity/madness_rules.py` and `domain/wounds/wound_rules.py`

#### `ENUMS`

- Defines `MadnessStage`, `EncounterPhase`, and `WoundEncPhase`.
- These are proper domain types, but they should be grouped by feature instead of living in one omnibus file.

Recommended destination:

- `domain/sanity/types.py`
- `domain/fears/types.py`
- `domain/wounds/types.py`

#### `STATIC INFO DICTS`

- Defines `MadnessInfo`, `MADNESS`, `FearStageInfo`, and `FEAR_STAGES`.
- This is a combination of domain metadata and presentation-oriented text/color config.

Recommended destination:

- gameplay semantics to `domain/sanity/stages.py` and `domain/fears/stages.py`
- if colors remain necessary here, isolate them behind a presentation mapping layer instead of baking them into the core domain objects

#### `DATACLASSES`

- Contains `roll_insanity_duration`, `MadnessEntry`, `WoundEntry`, `SanityState`, `FearManager`, `EncounterState`, `WoundEncounterState`, `SaveManager`, and `UndoStack`.
- This is the most overloaded section in the file.

Recommended destination:

- `MadnessEntry` and `SanityState` to `domain/sanity/entities.py`
- `WoundEntry` and wound encounter state to `domain/wounds/entities.py`
- `FearManager` and fear encounter state to `domain/fears/entities.py`
- `SaveManager` to `services/save_service.py`
- `UndoStack` to `domain/shared/undo.py` or `services/undo_service.py`

### Structural Problems Found in `models.py`

### Poor Separation of Concerns

- `models.py` is not just models; it is effectively the project’s domain layer, content registry, utility module, persistence adapter, and undo service in one file ([models.py](/Users/Tom/Desktop/Psyke-Android-V10/models.py#L1), [models.py](/Users/Tom/Desktop/Psyke-Android-V10/models.py#L850), [models.py](/Users/Tom/Desktop/Psyke-Android-V10/models.py#L884)).
- UI-facing rules text and color metadata are embedded directly beside domain entities ([models.py](/Users/Tom/Desktop/Psyke-Android-V10/models.py#L264), [models.py](/Users/Tom/Desktop/Psyke-Android-V10/models.py#L510)).
- Persistence path logic is mixed into a nominal model module via `SaveManager` ([models.py](/Users/Tom/Desktop/Psyke-Android-V10/models.py#L850)).

### Overlapping or Redundant Logic

- Desensitization colors are defined here even though theme color definitions already exist in `theme.py`, creating duplicated visual responsibility across modules.
- `MadnessEntry.kind_label`, `MadnessEntry.kind_color`, `MADNESS`, and the madness tables all partly describe the same concept in different forms.
- `SanityState` performs both domain state mutation and snapshot/restore serialization responsibilities.
- `FearManager` mixes fear list behavior, desensitization behavior, encounter counts, snapshot/restore compatibility, and random suggestion behavior in one class.

### Dead, Legacy, or Suspicious Code

- `math` and `Any` appear unused in `models.py` ([models.py](/Users/Tom/Desktop/Psyke-Android-V10/models.py#L9), [models.py](/Users/Tom/Desktop/Psyke-Android-V10/models.py#L14)).
- `save_v6.json` and the `restore()` methods carry version-compat and legacy flat-format behavior inline rather than through explicit migration code ([models.py](/Users/Tom/Desktop/Psyke-Android-V10/models.py#L28), [models.py](/Users/Tom/Desktop/Psyke-Android-V10/models.py#L797)).
- `hope_img_path` is still embedded in `SanityState` even though the current header widget explicitly treats image picking as unused-by-design.

### Encapsulation Problems

- `SanityState` serializes itself into app save format with `snapshot()` and `restore()`, tying the entity to storage schema ([models.py](/Users/Tom/Desktop/Psyke-Android-V10/models.py#L677)).
- `FearManager.restore()` contains legacy file-format branching, which belongs in a repository/mapper layer rather than the runtime manager object ([models.py](/Users/Tom/Desktop/Psyke-Android-V10/models.py#L797)).
- `SaveManager.save()` knows concrete fields from multiple domains and manually assembles a whole-app save payload, so it is acting as an application repository, not a simple helper ([models.py](/Users/Tom/Desktop/Psyke-Android-V10/models.py#L864)).

### Formatting and Encoding Issues

- `models.py` contains the same mojibake comment divider corruption seen in `main.py`.
- Several strings still contain corrupted punctuation such as `â€”`, `â€“`, and `Ã—` in comments and rules text.
- Many one-line methods and multiple statements per line reduce scanability for both humans and AI tools.

## Proposed Split for `models.py`

### Domain Core

- `domain/constants.py`
- `domain/shared/dice.py`
- `domain/shared/undo.py`
- `domain/sanity/types.py`
- `domain/sanity/entities.py`
- `domain/sanity/madness_tables.py`
- `domain/sanity/madness_rules.py`
- `domain/fears/types.py`
- `domain/fears/entities.py`
- `domain/fears/catalog.py`
- `domain/fears/desensitization.py`
- `domain/fears/stages.py`
- `domain/wounds/types.py`
- `domain/wounds/entities.py`
- `domain/wounds/wound_tables.py`
- `domain/wounds/wound_rules.py`

### UI / Content Resources

- `ui/content/rules_text.py`
- `ui/utils/colors.py`

### Services / Persistence

- `services/save_service.py`
- `services/persistence/schema.py`
- `services/persistence/migrations.py`

## Why `models.py` Should Be Split This Way

- Static gameplay content tables change for different reasons than state classes and should not live together.
- Serialization and migration logic should be centralized so domain entities stay focused on runtime behavior.
- Feature-specific encounter state belongs with its feature, which will make future tab refactors much easier.
- Rules text is display content and should be editable without touching domain or persistence code.
- Shared helper functions should become predictable, shallow imports rather than being discovered inside a giant omnibus module.

## Additional Cleanup Tasks Identified From `models.py`

- Remove unused imports such as `math` and `Any`.
- Normalize all text encoding to UTF-8 and replace corrupted separators and punctuation.
- Decide whether `hope_img_path` is still a supported product feature; remove it from the domain model if not.
- Move save-format compatibility logic into explicit migrations rather than burying it in `restore()` methods.
- Separate domain metadata from visual theme metadata so colors are not duplicated between `models.py` and `theme.py`.
- Replace multi-statement one-line methods with standard block formatting for easier code review and automated analysis.

## Target Structure Refinement After `models.py`

The earlier target structure should be refined with a clearer split between domain, UI content, and persistence:

```text
psyke/
  app/
    main.py
    bootstrap.py
    config/
      theme.py
      fonts.py
      platform.py
    domain/
      constants.py
      shared/
        dice.py
        undo.py
      fears/
        catalog.py
        desensitization.py
        entities.py
        stages.py
        types.py
      sanity/
        entities.py
        madness_rules.py
        madness_tables.py
        stages.py
        types.py
      wounds/
        entities.py
        wound_rules.py
        wound_tables.py
        types.py
    services/
      save_service.py
      persistence/
        schema.py
        migrations.py
      notification_service.py
      session_log_service.py
      navigation_service.py
    ui/
      app_shell.py
      content/
        rules_text.py
      dialogs/
      navigation/
      screens/
      widgets/
      utils/
        colors.py
```

## Files to Simplify Later

- `models.py`
- `widgets.py`
- `ui_utils.py`
- `tab_fears.py`
- `tab_sanity.py`
- `tab_wounds.py`
- `tab_spells.py`
