"""
Tab 4: Healing Spells
Minor Restoration → cures one Short-Term or Long-Term madness, or one Minor Wound.
Major Restoration → cures one Indefinite madness, or one Major Wound (+ regeneration note).
"""
from __future__ import annotations

from kivy.app import App
from kivy.clock import Clock
from kivy.metrics import dp
from kivy.uix.scrollview import ScrollView
from kivy.uix.widget import Widget

from kivymd.uix.boxlayout import MDBoxLayout
from kivymd.uix.button import MDFlatButton, MDRaisedButton
from kivymd.uix.label import MDLabel
from kivymd.uix.snackbar import MDSnackbar

from models import SPELL_RULES_TEXT
from ui_utils import (
    BorderCard, AccentCard, DescriptionCard, Divider,
    SectionLabel, CaptionLabel, MultilineLabel,
    ExpandingEffectCard, ExpandableSection, populate_rules_section
)
import theme as T


class SpellsTab(ScrollView):

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.do_scroll_x = False

        # Selection state: indices into the appropriate lists (needed for cast logic)
        self._minor_mad_idx:   int | None = None
        self._minor_wound_idx: int | None = None
        self._major_mad_idx:   int | None = None
        self._major_wound_idx: int | None = None

        # One active card per section (replaces 4 _sel_*_widget + _cur_*_detail)
        self._active_minor_card: ExpandingEffectCard | None = None
        self._active_major_card: ExpandingEffectCard | None = None

        root = MDBoxLayout(
            orientation="vertical",
            padding=dp(10),
            spacing=dp(8),
            size_hint_y=None,
            adaptive_height=True
        )
        self.add_widget(root)

        root.add_widget(self._build_minor_card())
        root.add_widget(self._build_major_card())
        root.add_widget(self._build_rules_panel())

    # ── Build: Minor Restoration ──────────────────────────────────────────────

    def _build_minor_card(self) -> BorderCard:
        card = BorderCard(border_hex=T.SILVER)
        card.add_widget(SectionLabel("MINOR RESTORATION", color_hex=T.SILVER))
        card.add_widget(CaptionLabel(
            "Cures one Short-Term or Long-Term madness entry, or one Minor Wound.",
            color_hex=T.TEXT_DIM, height_dp=28))

        # ── Short-Term / Long-Term madness selection ─────────────────────────
        card.add_widget(CaptionLabel(
            "SELECT MADNESS  (Short-Term or Long-Term)",
            color_hex=T.M_SHORT, height_dp=20))

        self._minor_mad_box = MDBoxLayout(
            orientation="vertical", adaptive_height=True, spacing=dp(2))
        card.add_widget(self._minor_mad_box)

        # ── Minor wound selection ────────────────────────────────────────────
        card.add_widget(Divider(color_hex=T.SILVER))
        card.add_widget(CaptionLabel(
            "SELECT MINOR WOUND",
            color_hex=T.WOUND_MIN, height_dp=20))

        self._minor_wound_box = MDBoxLayout(
            orientation="vertical", adaptive_height=True, spacing=dp(2))
        card.add_widget(self._minor_wound_box)

        # Cast button
        card.add_widget(Divider(color_hex=T.BORDER))
        cast_row = MDBoxLayout(spacing=dp(8), size_hint_y=None, height=dp(48))
        cast_row.add_widget(Widget())
        cast_row.add_widget(MDRaisedButton(
            text="Cast Minor Restoration",
            md_bg_color=T.k(T.SILVER),
            size_hint_x=None, width=dp(220),
            on_release=self._on_cast_minor))
        cast_row.add_widget(Widget())
        card.add_widget(cast_row)

        return card

    # ── Build: Major Restoration ──────────────────────────────────────────────

    def _build_major_card(self) -> BorderCard:
        card = BorderCard(border_hex=T.SILVER)
        card.add_widget(SectionLabel("MAJOR RESTORATION", color_hex=T.SILVER))
        card.add_widget(CaptionLabel(
            "Cures any madness (Short-Term, Long-Term, or Indefinite), or any Wound (Minor or Major).",
            color_hex=T.TEXT_DIM, height_dp=28))
        card.add_widget(CaptionLabel(
            "Note: Also regenerates lost body parts for Major Wounds.",
            color_hex=T.TEXT_DIM, height_dp=20))

        # ── All madness selection ─────────────────────────────────────────────
        card.add_widget(CaptionLabel(
            "SELECT MADNESS  (Any Kind)",
            color_hex=T.M_SHORT, height_dp=20))

        self._major_mad_box = MDBoxLayout(
            orientation="vertical", adaptive_height=True, spacing=dp(2))
        card.add_widget(self._major_mad_box)

        # ── All wound selection ───────────────────────────────────────────────
        card.add_widget(Divider(color_hex=T.SILVER))
        card.add_widget(CaptionLabel(
            "SELECT WOUND  (Minor or Major)",
            color_hex=T.WOUND_MIN, height_dp=20))

        self._major_wound_box = MDBoxLayout(
            orientation="vertical", adaptive_height=True, spacing=dp(2))
        card.add_widget(self._major_wound_box)

        # Cast button
        card.add_widget(Divider(color_hex=T.BORDER))
        cast_row = MDBoxLayout(spacing=dp(8), size_hint_y=None, height=dp(48))
        cast_row.add_widget(Widget())
        cast_row.add_widget(MDRaisedButton(
            text="Cast Major Restoration",
            md_bg_color=T.k(T.SILVER),
            size_hint_x=None, width=dp(220),
            on_release=self._on_cast_major))
        cast_row.add_widget(Widget())
        card.add_widget(cast_row)

        return card

    def _build_rules_panel(self) -> BorderCard:
        wrapper = BorderCard(border_hex=T.SILVER_LT)
        sec = ExpandableSection(
            "SPELL RULES",
            accent_hex=T.SILVER_LT,
        )
        populate_rules_section(sec, SPELL_RULES_TEXT, T.SILVER_LT)
        wrapper.add_widget(sec)
        return wrapper

    # ── Panel expand/collapse ─────────────────────────────────────────────────

    def _sync_panel_height(self, panel):
        panel.height = panel.minimum_height

    def _expand_panel(self, detail):
        detail.size_hint_y = None
        detail.opacity = 1
        Clock.schedule_once(lambda dt, d=detail: self._sync_panel_height(d))

    def _collapse_panel(self, detail):
        detail.size_hint_y = None
        detail.height = 0
        detail.opacity = 0

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _app(self): return App.get_running_app()

    def _madness_summary(self, m) -> str:
        parts = [m.kind_label, f"Roll: {m.roll_range}"]
        if getattr(m, "duration", ""):
            parts.append(m.duration)
        return " | ".join(parts)

    def _wound_roll(self, severity: str, description: str) -> str:
        from models import MINOR_WOUND_TABLE, MAJOR_WOUND_TABLE
        table = MINOR_WOUND_TABLE if severity == "minor" else MAJOR_WOUND_TABLE
        return next((str(roll) for roll, desc, _ in table if desc == description), "?")

    def _wound_summary(self, severity: str, description: str) -> str:
        label = "Major Wound" if severity == "major" else "Minor Wound"
        sanity_loss = "2d4 Sanity Loss" if severity == "major" else "1d4 Sanity Loss"
        return f"{label} | Roll: {self._wound_roll(severity, description)} | {sanity_loss}"

    def _push_undo(self):
        app = self._app()
        app.undo_stack.push(app.state, app.fm)

    def _save(self):
        app = self._app()
        app.save_manager.save(app.state, app.fm, app.char_name, app.enc_history)

    def _log(self, msg):
        app = self._app()
        app.enc_history.append(msg)
        if hasattr(app, "session_log"):
            app.session_log.add_entry(msg)

    def _snack(self, msg, color=T.BG_CARD):
        MDSnackbar(
            MDLabel(text=msg, theme_text_color="Custom", text_color=(1, 1, 1, 1)),
            md_bg_color=T.k(color), duration=2.5
        ).open()

    def _deselect_all_minor(self):
        if self._active_minor_card:
            self._active_minor_card.set_open(False)
            self._active_minor_card = None
        self._minor_mad_idx   = None
        self._minor_wound_idx = None

    def _deselect_all_major(self):
        if self._active_major_card:
            self._active_major_card.set_open(False)
            self._active_major_card = None
        self._major_mad_idx   = None
        self._major_wound_idx = None

    # ── Public refresh ─────────────────────────────────────────────────────────

    def refresh(self):
        app = self._app()
        kind_colors = {"short": T.M_SHORT, "long": T.M_LONG, "indefinite": T.M_INDEF}

        # ── Minor: short + long term madness ─────────────────────────────────
        self._minor_mad_box.clear_widgets()
        self._minor_mad_idx   = None
        self._active_minor_card = None

        minor_mads = [
            (i, m) for i, m in enumerate(app.state.madnesses)
            if m.kind in ("short", "long")]
        if not minor_mads:
            self._minor_mad_box.add_widget(CaptionLabel(
                "No Short-Term or Long-Term madness active.",
                color_hex=T.TEXT_DIM, height_dp=28))
        else:
            for _, (state_idx, m) in enumerate(minor_mads):
                color = kind_colors.get(m.kind, T.M_SHORT)
                name  = m.name if m.name else f"{m.kind_label} Effect"
                card  = ExpandingEffectCard(
                    on_tap=lambda w, si=state_idx: self._on_minor_mad_tap(w, si))
                card.title_text    = name
                card.subtitle_text = self._madness_summary(m)
                card.detail_body   = m.effect
                card.accent_rgba   = list(T.k(color))
                self._minor_mad_box.add_widget(card)

        # ── Minor: minor wounds ───────────────────────────────────────────────
        self._minor_wound_box.clear_widgets()
        self._minor_wound_idx = None

        minors = app.state.encounter_minor_wounds
        if not minors:
            self._minor_wound_box.add_widget(CaptionLabel(
                "No minor wounds in the wound encounter list.",
                color_hex=T.TEXT_DIM, height_dp=28))
        else:
            for i, w in enumerate(minors):
                card = ExpandingEffectCard(
                    on_tap=lambda wid, idx=i: self._on_minor_wound_tap(wid, idx))
                card.title_text    = w.description
                card.subtitle_text = self._wound_summary("minor", w.description)
                card.detail_body   = w.effect
                card.accent_rgba   = list(T.k(T.WOUND_MIN))
                self._minor_wound_box.add_widget(card)

        # ── Major: all madness kinds ──────────────────────────────────────────
        self._major_mad_box.clear_widgets()
        self._major_mad_idx   = None
        self._active_major_card = None

        all_mads = list(enumerate(app.state.madnesses))
        if not all_mads:
            self._major_mad_box.add_widget(CaptionLabel(
                "No madness active.",
                color_hex=T.TEXT_DIM, height_dp=28))
        else:
            for _, (state_idx, m) in enumerate(all_mads):
                color = kind_colors.get(m.kind, T.M_INDEF)
                name  = m.name if m.name else f"{m.kind_label} Effect"
                card  = ExpandingEffectCard(
                    on_tap=lambda w, si=state_idx: self._on_major_mad_tap(w, si))
                card.title_text    = name
                card.subtitle_text = self._madness_summary(m)
                card.detail_body   = m.effect
                card.accent_rgba   = list(T.k(color))
                self._major_mad_box.add_widget(card)

        # ── Major: all wounds (minor + major) ─────────────────────────────────
        self._major_wound_box.clear_widgets()
        self._major_wound_idx = None

        all_wounds = app.state.encounter_wounds
        if not all_wounds:
            self._major_wound_box.add_widget(CaptionLabel(
                "No wounds in the wound encounter list.",
                color_hex=T.TEXT_DIM, height_dp=28))
        else:
            for i, w in enumerate(all_wounds):
                color = T.BLOOD if w.severity == "major" else T.WOUND_MIN
                card  = ExpandingEffectCard(
                    on_tap=lambda wid, idx=i: self._on_major_wound_tap(wid, idx))
                card.title_text    = w.description
                card.subtitle_text = self._wound_summary(w.severity, w.description)
                card.detail_body   = w.effect
                card.accent_rgba   = list(T.k(color))
                self._major_wound_box.add_widget(card)

    # ── Selection handlers ────────────────────────────────────────────────────

    def _on_minor_mad_tap(self, card: ExpandingEffectCard, state_idx: int):
        if self._active_minor_card is card:
            card.set_open(False)
            self._active_minor_card = None
            self._minor_mad_idx = None
            return
        if self._active_minor_card:
            self._active_minor_card.set_open(False)
        card.set_open(True)
        self._active_minor_card = card
        self._minor_mad_idx     = state_idx
        self._minor_wound_idx   = None

    def _on_minor_wound_tap(self, card: ExpandingEffectCard, idx: int):
        if self._active_minor_card is card:
            card.set_open(False)
            self._active_minor_card = None
            self._minor_wound_idx = None
            return
        if self._active_minor_card:
            self._active_minor_card.set_open(False)
        card.set_open(True)
        self._active_minor_card = card
        self._minor_wound_idx   = idx
        self._minor_mad_idx     = None

    def _on_major_mad_tap(self, card: ExpandingEffectCard, state_idx: int):
        if self._active_major_card is card:
            card.set_open(False)
            self._active_major_card = None
            self._major_mad_idx = None
            return
        if self._active_major_card:
            self._active_major_card.set_open(False)
        card.set_open(True)
        self._active_major_card = card
        self._major_mad_idx     = state_idx
        self._major_wound_idx   = None

    def _on_major_wound_tap(self, card: ExpandingEffectCard, idx: int):
        if self._active_major_card is card:
            card.set_open(False)
            self._active_major_card = None
            self._major_wound_idx = None
            return
        if self._active_major_card:
            self._active_major_card.set_open(False)
        card.set_open(True)
        self._active_major_card = card
        self._major_wound_idx   = idx
        self._major_mad_idx     = None

    # ── Cast actions ──────────────────────────────────────────────────────────

    def _on_cast_minor(self, *_):
        """Minor Restoration: cure selected ST/LT madness OR minor wound."""
        app = self._app()

        if self._minor_mad_idx is not None:
            idx = self._minor_mad_idx
            if idx >= len(app.state.madnesses):
                self._snack("Selection invalid — refresh.", T.BORDER); return
            self._push_undo()
            m = app.state.madnesses.pop(idx)
            name = m.name if m.name else m.kind_label
            self._log(f"Minor Restoration: cured {m.kind_label} madness - [{m.roll_range}] {name}")
            app.refresh_all()
            self._save()
            mcol = {"short": T.M_SHORT, "long": T.M_LONG, "indefinite": T.M_INDEF}.get(m.kind, T.SILVER)
            app.notify_event(
                f"Minor Restoration: [color={mcol}]{name} cured[/color]",
                "spells", T.SILVER
            )
            return

        if self._minor_wound_idx is not None:
            idx    = self._minor_wound_idx
            minors = app.state.encounter_minor_wounds
            if idx >= len(minors):
                self._snack("Selection invalid — refresh.", T.BORDER); return
            target = minors[idx]
            self._push_undo()
            app.state.wounds.remove(target)
            self._log(f"Minor Restoration: cured minor wound - {target.description}")
            app.refresh_all()
            self._save()
            app.notify_event(
                f"Minor Restoration: [color={T.WOUND_MIN}]{target.description} cured[/color]",
                "spells", T.WOUND_MIN
            )
            return

        self._snack(
            "Select a Short-Term/Long-Term madness or Minor Wound first.",
            T.BORDER)

    def _on_cast_major(self, *_):
        """Major Restoration: cure selected madness (any kind) OR wound (any severity)."""
        app = self._app()

        if self._major_mad_idx is not None:
            idx = self._major_mad_idx
            if idx >= len(app.state.madnesses):
                self._snack("Selection invalid — refresh.", T.BORDER); return
            self._push_undo()
            m = app.state.madnesses.pop(idx)
            name = m.name if m.name else m.kind_label
            self._log(f"Major Restoration: cured {m.kind_label} madness - [{m.roll_range}] {name}")
            app.refresh_all()
            self._save()
            mcol = {"short": T.M_SHORT, "long": T.M_LONG, "indefinite": T.M_INDEF}.get(m.kind, T.SILVER)
            app.notify_event(
                f"Major Restoration: [color={mcol}]{name} cured[/color]",
                "spells", T.SILVER
            )
            return

        if self._major_wound_idx is not None:
            idx = self._major_wound_idx
            all_wounds = app.state.encounter_wounds
            if idx >= len(all_wounds):
                self._snack("Selection invalid — refresh.", T.BORDER); return
            target = all_wounds[idx]
            self._push_undo()
            app.state.wounds.remove(target)
            regen = " (regeneration applies)" if target.severity == "major" else ""
            self._log(
                f"Major Restoration: cured {target.severity} wound - {target.description}{regen}")
            app.refresh_all()
            self._save()
            wcol = T.WOUND_MIN if target.severity == "minor" else T.BLOOD
            app.notify_event(
                f"Major Restoration: [color={wcol}]{target.description} cured{regen}[/color]",
                "spells", T.WOUND_MIN
            )
            return

        self._snack(
            "Select a madness or wound first.",
            T.BORDER)
