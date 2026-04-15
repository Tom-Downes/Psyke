# Refactor Plan 2

This document is the refined second-pass plan for restructuring the Psyke Android V10 repository into a cleaner production-style codebase.

It consolidates the earlier file-by-file findings into one coherent target architecture, one migration order, and one set of naming and cleanup rules.

## Goals

- Move the project from a flat script-style layout to a professional app-level structure.
- Keep file boundaries obvious and predictable.
- Give each file one clear responsibility.
- Reduce duplication across features.
- Remove dead, legacy, and overlapping code during extraction.
- Normalize encoding and formatting so the codebase is readable by both humans and AI tools.

## Core Architectural Decision

The repository should become feature-first.

That means:

- `features/` owns app-specific product behavior.
- `ui/` owns shared reusable interface primitives and shell widgets.
- `domain/` owns state, rules, tables, and business logic.
- `services/` owns persistence, notifications, session logs, and other app-wide orchestration.
- `app/` owns bootstrap and top-level shell composition.

This is the cleanest fit for the code that was analyzed:

- the current `tab_*` files are not just screens, they are feature packages flattened into single files
- the current `ui_utils.py` is not a utility module, it is a shared UI kit
- the current `models.py` is not just models, it is domain + content + persistence + undo
- the current `main.py` is not just an entry file, it is bootstrap + shell + widgets + dialogs + orchestration

## Refined Target Structure

```text
psyke/
  app/
    __init__.py
    main.py
    bootstrap.py
    app_shell.py
    config/
      __init__.py
      fonts.py
      kivy_theme.py
      platform.py
      theme_roles.py
      theme_tokens.py
    domain/
      __init__.py
      constants.py
      shared/
        __init__.py
        dice.py
        undo.py
      sanity/
        __init__.py
        entities.py
        madness_rules.py
        madness_tables.py
        stages.py
        types.py
      fears/
        __init__.py
        catalog.py
        desensitization.py
        entities.py
        stages.py
        types.py
      wounds/
        __init__.py
        entities.py
        wound_rules.py
        wound_tables.py
        types.py
    services/
      __init__.py
      notification_service.py
      save_service.py
      session_log_service.py
      persistence/
        __init__.py
        migrations.py
        schema.py
    features/
      __init__.py
      sanity/
        __init__.py
        screens/
          sanity_screen.py
        views/
          active_insanity_panel.py
          add_insanity_panel.py
          rules_panel.py
          sanity_controls_panel.py
        controllers/
          add_insanity_controller.py
          sanity_controller.py
      fears/
        __init__.py
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
        controllers/
          fear_encounter_controller.py
          fears_controller.py
        models/
          encounter_record.py
          threshold_preview.py
      wounds/
        __init__.py
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
      spells/
        __init__.py
        screens/
          spells_screen.py
        views/
          restoration_panel.py
          spell_rules_panel.py
        controllers/
          restoration_controller.py
        presenters/
          restoration_notifications.py
    ui/
      __init__.py
      dialogs/
        __init__.py
        session_log_dialog.py
        stat_dialog.py
      navigation/
        __init__.py
        paged_screen.py
        tab_bar.py
      widgets/
        __init__.py
        foundation/
          __init__.py
          cards.py
          fields.py
          labels.py
          sections.py
        header/
          __init__.py
          advantage_toggle.py
          header_card.py
          hope_portrait.py
          sanity_chip.py
          stat_chip.py
        notifications/
          __init__.py
          event_notification_card.py
        session/
          __init__.py
          session_log_panel.py
        shared/
          __init__.py
          exhaustion_widget.py
          sanity_bar.py
        legacy/
          __init__.py
          madness_banner_stub.py  # temporary only if needed
      content/
        __init__.py
        rules_text.py
        rules_renderer.py
      utils/
        __init__.py
        clipping.py
        color_conversion.py
        colors.py
  tests/
    unit/
    integration/
```

## Layer Rules

### `app/`

- Keeps startup and shell composition thin.
- Must not absorb feature-specific business logic.

### `domain/`

- Owns entities, rules, enums/types, content tables, and shared pure logic.
- Must not depend on Kivy/KivyMD widgets.
- Must not own theme colors or UI rendering decisions.

### `services/`

- Owns save/load orchestration, notifications, session logging, and migration/versioning.
- Can depend on domain.
- Should not render UI directly except through clear UI-facing contracts.

### `features/`

- Owns each product area end-to-end.
- Screens compose panels.
- Views render feature-specific UI pieces.
- Controllers coordinate feature actions and app/service calls.
- Feature-local widgets stay inside the feature package when they are not broadly reusable.

### `ui/`

- Owns shared reusable interface primitives and shell-level widgets.
- Should stay generic and shallow.
- Must not become another omnibus utility sink.

## Cross-Cutting Decisions

These decisions should now be treated as settled:

- Replace `tab_*` files with feature packages.
- Replace giant omnibus modules with smaller files organized by responsibility.
- Keep rules text out of domain entities.
- Keep visual colors and semantic theme mappings out of domain modules.
- Move save-format compatibility into explicit persistence migrations.
- Remove direct `App.get_running_app()` usage from reusable widgets where practical.
- Reduce direct private-child access across modules.
- Remove mojibake and standardize the repo on UTF-8.

## High-Priority Global Cleanup

### Encoding and Formatting

- Normalize all source files to UTF-8.
- Remove corrupted comment dividers and unreadable punctuation.
- Replace giant banner-comment structure with real modules.
- Break up one-line multi-statement methods where they reduce scanability.

### Naming

- Rename `SFMApp` to `PsykeApp`.
- Replace `tab_*` names with `*_screen.py` or feature package modules.
- Replace unclear private helper component names like `_TabBtn` and `_AdvBtn` with explicit component names after extraction.

### Redundant and Legacy Code

- Remove `MadnessBanner` once imports are updated.
- Remove confirmed dead branches in `tab_fears.py`.
- Remove unused imports from every analyzed file before or during extraction.
- Re-check old compatibility shims after each migration step instead of carrying them indefinitely.

### Shared Behavior Cleanup

- Consolidate threshold handling across sanity, fears, and wounds.
- Consolidate repeated selection/open-card patterns where possible.
- Consolidate swipe-page navigation into a shared `paged_screen` abstraction if the extracted features still need it.

## File-Level Refactor Priorities

### 1. `main.py`

Refactor goal:

- reduce to entrypoint + app shell wiring only

Move out:

- bootstrap logic
- dialogs
- header widgets
- session log widget
- tab/navigation widgets
- notification rendering/orchestration
- save/load hydration

Major issues:

- severe concern mixing
- direct widget-to-app mutation
- direct app access to child private internals
- legacy `MadnessBanner` retention

### 2. `models.py`

Refactor goal:

- split into domain packages + persistence + content resources

Move out:

- rules text
- static tables
- UI color helpers
- save manager
- migrations/version handling
- undo stack if it remains shared infrastructure

Major issues:

- domain + persistence + content + undo all mixed together
- duplicated visual metadata
- storage schema coupled to runtime entities

### 3. `ui_utils.py`

Refactor goal:

- replace with a real shared UI/design-system structure

Split into:

- foundation widgets
- controls/navigation widgets
- rules rendering
- feature-specific shared widgets such as `HopeButton`

Major issues:

- utility sink
- overlapping list/card components
- likely dead legacy notification banner

### 4. `widgets.py`

Refactor goal:

- keep only real shared widgets and remove compatibility debris

Keep:

- `SanityBar`
- `ExhaustionWidget`

Remove or isolate:

- `MadnessBanner`

### 5. `theme.py`

Refactor goal:

- split tokens, semantic roles, and Kivy adapters

Major issues:

- duplicated color ownership with `models.py`
- probable unused `K_*` exports
- global dependency sink pattern via `import theme as T`

### 6. `tab_sanity.py`

Refactor goal:

- first model feature extraction pattern

Split into:

- screen
- sanity controls panel
- add-insanity panel
- active-insanity panel
- controller(s)

Major issues:

- threshold logic embedded in UI
- repeated app bridge helpers
- object-identity-based selection state

### 7. `tab_wounds.py`

Refactor goal:

- second model feature extraction pattern

Split into:

- screen
- encounter panel
- active wounds panel
- wound picker panel
- notifications presenter
- controller(s)

Major issues:

- duplicated minor/major logic
- overloaded encounter resolution method
- repeated app bridge helpers

### 8. `tab_spells.py`

Refactor goal:

- compact feature extraction after shared patterns are established

Split into:

- screen
- restoration panel
- rules panel
- restoration controller
- notifications presenter

Major issues:

- duplicated minor/major selection and cast flows
- several confirmed unused helpers/imports

### 9. `tab_fears.py`

Refactor goal:

- largest and highest-risk feature extraction

Split into:

- fears screen
- feature views
- encounter widgets
- encounter controller
- replay/frozen encounter view
- threshold preview model/helper

Major issues:

- most overloaded file in the repo
- unreachable code
- severe encoding damage
- heavy shell coupling

## Recommended Migration Order

Implement the refactor in this order:

1. Create the new folder skeleton and import-safe placeholder modules.
2. Split `theme.py` into config/theme files and color utilities.
3. Split `ui_utils.py` and `widgets.py` into shared UI modules.
4. Split `models.py` into domain + persistence + content.
5. Shrink `main.py` to shell/bootstrap wiring.
6. Extract `tab_sanity.py` into `features/sanity/`.
7. Extract `tab_wounds.py` into `features/wounds/`.
8. Extract `tab_spells.py` into `features/spells/`.
9. Extract `tab_fears.py` into `features/fears/`.
10. Remove temporary legacy shims and dead compatibility imports.

Why this order:

- it stabilizes shared dependencies before moving the feature modules
- it avoids copying bad boundaries into the new structure
- it leaves the most complex feature, fears, until the common patterns are already proven

## Concrete Removal Candidates

Confirmed or near-confirmed cleanup targets from the analysis:

- `MadnessBanner`
- dead branches after `return` in `tab_fears.py`
- dead `if False` branch in `tab_fears.py`
- unused imports in `main.py`
- unused imports in `widgets.py`
- unused imports in `ui_utils.py`
- unused imports in `tab_sanity.py`
- unused imports in `tab_wounds.py`
- unused imports and dead helpers in `tab_spells.py`
- duplicated desensitization color ownership between `models.py` and `theme.py`

## File Creation Checklist

Create these first because they unlock the rest of the refactor:

- `app/main.py`
- `app/bootstrap.py`
- `app/app_shell.py`
- `app/config/fonts.py`
- `app/config/kivy_theme.py`
- `app/config/platform.py`
- `app/config/theme_roles.py`
- `app/config/theme_tokens.py`
- `app/services/save_service.py`
- `app/services/notification_service.py`
- `app/services/session_log_service.py`
- `app/services/persistence/schema.py`
- `app/services/persistence/migrations.py`
- `app/ui/dialogs/stat_dialog.py`
- `app/ui/dialogs/session_log_dialog.py`
- `app/ui/navigation/tab_bar.py`
- `app/ui/navigation/paged_screen.py`
- `app/ui/widgets/session/session_log_panel.py`
- `app/ui/widgets/header/header_card.py`
- `app/ui/widgets/header/advantage_toggle.py`
- `app/ui/widgets/header/stat_chip.py`
- `app/ui/widgets/header/sanity_chip.py`
- `app/ui/widgets/header/hope_portrait.py`
- `app/ui/widgets/notifications/event_notification_card.py`
- `app/ui/widgets/shared/sanity_bar.py`
- `app/ui/widgets/shared/exhaustion_widget.py`
- `app/ui/content/rules_text.py`
- `app/ui/content/rules_renderer.py`

## Standards For The New Codebase

- One responsibility per file.
- No hidden legacy code kept “for compatibility” without an explicit migration reason.
- No feature logic in shared UI primitives.
- No UI formatting data inside domain modules.
- No persistence schema logic embedded inside domain entities.
- No unreadable comment art used as a substitute for file structure.
- Prefer explicit public methods over cross-module access to private attributes.
- Prefer narrow imports from small modules over giant omnibus imports.

## Success Criteria

The refactor is successful when:

- the app entry layer is small and easy to understand
- each feature can be scanned independently
- shared UI is easy to discover without reading feature code
- domain logic can be understood without reading UI files
- persistence and migrations are isolated
- dead/duplicate code is materially reduced
- encoding problems are gone
- future refactors no longer depend on giant comment-header files
