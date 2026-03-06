"""
Tab 4: Healing Spells
Minor Restoration → cures one Short-Term or Long-Term madness, or one Minor Wound.
Major Restoration → cures one Indefinite madness, or one Major Wound (+ regeneration note).
"""
from __future__ import annotations

from kivy.app import App
from kivy.metrics import dp
from kivy.uix.scrollview import ScrollView
from kivy.uix.widget import Widget

from kivymd.uix.boxlayout import MDBoxLayout
from kivymd.uix.button import MDFlatButton, MDRaisedButton
from kivymd.uix.label import MDLabel
from kivymd.uix.snackbar import MDSnackbar

from models import SPELL_RULES_TEXT
from ui_utils import (
    BorderCard, AccentCard, Divider,
    SectionLabel, CaptionLabel, MultilineLabel,
    ListItem, ExpandableSection
)
import theme as T


class SpellsTab(ScrollView):

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.do_scroll_x = False

        # Selection state: indices into the appropriate lists
        self._minor_mad_idx:    int | None = None
        self._minor_wound_idx:  int | None = None
        self._major_mad_idx:    int | None = None
        self._major_wound_idx:  int | None = None
        self._sel_minor_mad_widget:   ListItem | None = None
        self._sel_minor_wound_widget: ListItem | None = None
        self._sel_major_mad_widget:   ListItem | None = None
        self._sel_major_wound_widget: ListItem | None = None

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
            "SELECT MADNESS (Short-Term or Long-Term)",
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
        card = BorderCard(border_hex=T.GOLD_LT)
        card.add_widget(SectionLabel("MAJOR RESTORATION", color_hex=T.GOLD_LT))
        card.add_widget(CaptionLabel(
            "Cures one Indefinite madness entry, or one Major Wound.",
            color_hex=T.TEXT_DIM, height_dp=28))
        card.add_widget(CaptionLabel(
            "Note: Also regenerates lost body parts for qualifying Major Wounds.",
            color_hex=T.TEXT_DIM, height_dp=20))

        # ── Indefinite madness selection ─────────────────────────────────────
        card.add_widget(CaptionLabel(
            "SELECT INDEFINITE MADNESS",
            color_hex=T.M_INDEF, height_dp=20))

        self._major_mad_box = MDBoxLayout(
            orientation="vertical", adaptive_height=True, spacing=dp(2))
        card.add_widget(self._major_mad_box)

        # ── Major wound selection ─────────────────────────────────────────────
        card.add_widget(Divider(color_hex=T.GOLD_LT))
        card.add_widget(CaptionLabel(
            "SELECT MAJOR WOUND",
            color_hex=T.BLOOD, height_dp=20))

        self._major_wound_box = MDBoxLayout(
            orientation="vertical", adaptive_height=True, spacing=dp(2))
        card.add_widget(self._major_wound_box)

        # Cast button
        card.add_widget(Divider(color_hex=T.BORDER))
        cast_row = MDBoxLayout(spacing=dp(8), size_hint_y=None, height=dp(48))
        cast_row.add_widget(Widget())
        cast_row.add_widget(MDRaisedButton(
            text="Cast Major Restoration",
            md_bg_color=T.k(T.GOLD_DK),
            size_hint_x=None, width=dp(220),
            on_release=self._on_cast_major))
        cast_row.add_widget(Widget())
        card.add_widget(cast_row)

        return card

    def _build_rules_panel(self) -> ExpandableSection:
        sec = ExpandableSection("Spell Rules", accent_hex=T.SILVER)
        sec.add_content(MultilineLabel(text=SPELL_RULES_TEXT, color_hex=T.TEXT_DIM))
        return sec

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _app(self): return App.get_running_app()

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
        if self._sel_minor_mad_widget:
            self._sel_minor_mad_widget.set_selected(False, persist=False)
            self._sel_minor_mad_widget = None
            self._minor_mad_idx = None
        if self._sel_minor_wound_widget:
            self._sel_minor_wound_widget.set_selected(False, persist=False)
            self._sel_minor_wound_widget = None
            self._minor_wound_idx = None

    def _deselect_all_major(self):
        if self._sel_major_mad_widget:
            self._sel_major_mad_widget.set_selected(False, persist=False)
            self._sel_major_mad_widget = None
            self._major_mad_idx = None
        if self._sel_major_wound_widget:
            self._sel_major_wound_widget.set_selected(False, persist=False)
            self._sel_major_wound_widget = None
            self._major_wound_idx = None

    # ── Public refresh ─────────────────────────────────────────────────────────

    def refresh(self):
        app = self._app()

        # ── Minor: short + long term madness ─────────────────────────────────
        self._minor_mad_box.clear_widgets()
        self._minor_mad_idx = None
        self._sel_minor_mad_widget = None

        minor_mads = [
            (i, m) for i, m in enumerate(app.state.madnesses)
            if m.kind in ("short", "long")]
        if not minor_mads:
            self._minor_mad_box.add_widget(CaptionLabel(
                "No Short-Term or Long-Term madness active.",
                color_hex=T.TEXT_DIM, height_dp=28))
        else:
            for list_idx, (state_idx, m) in enumerate(minor_mads):
                color = T.M_SHORT if m.kind == "short" else T.M_LONG
                name  = m.name if m.name else f"{m.kind_label} Effect"
                item  = ListItem(
                    primary=name,
                    secondary=f"{m.kind_label}  |  {m.roll_range}",
                    accent_hex=color,
                    on_tap=lambda w, si=state_idx: self._on_minor_mad_tap(w, si))
                self._minor_mad_box.add_widget(item)

        # ── Minor: minor wounds ───────────────────────────────────────────────
        self._minor_wound_box.clear_widgets()
        self._minor_wound_idx = None
        self._sel_minor_wound_widget = None

        minors = app.state.minor_wounds
        if not minors:
            self._minor_wound_box.add_widget(CaptionLabel(
                "No minor wounds active.",
                color_hex=T.TEXT_DIM, height_dp=28))
        else:
            for i, w in enumerate(minors):
                item = ListItem(
                    primary=w.description,
                    secondary=w.effect[:55] + ("..." if len(w.effect) > 55 else ""),
                    accent_hex=T.WOUND_MIN,
                    on_tap=lambda widget, idx=i: self._on_minor_wound_tap(widget, idx))
                self._minor_wound_box.add_widget(item)

        # ── Major: indefinite madness ─────────────────────────────────────────
        self._major_mad_box.clear_widgets()
        self._major_mad_idx = None
        self._sel_major_mad_widget = None

        indef_mads = [
            (i, m) for i, m in enumerate(app.state.madnesses)
            if m.kind == "indefinite"]
        if not indef_mads:
            self._major_mad_box.add_widget(CaptionLabel(
                "No Indefinite madness active.",
                color_hex=T.TEXT_DIM, height_dp=28))
        else:
            for list_idx, (state_idx, m) in enumerate(indef_mads):
                name = m.name if m.name else "Indefinite Effect"
                item = ListItem(
                    primary=name,
                    secondary=f"Indefinite  |  {m.roll_range}",
                    accent_hex=T.M_INDEF,
                    on_tap=lambda w, si=state_idx: self._on_major_mad_tap(w, si))
                self._major_mad_box.add_widget(item)

        # ── Major: major wounds ───────────────────────────────────────────────
        self._major_wound_box.clear_widgets()
        self._major_wound_idx = None
        self._sel_major_wound_widget = None

        majors = app.state.major_wounds
        if not majors:
            self._major_wound_box.add_widget(CaptionLabel(
                "No major wounds active.",
                color_hex=T.TEXT_DIM, height_dp=28))
        else:
            for i, w in enumerate(majors):
                item = ListItem(
                    primary=w.description,
                    secondary=w.effect[:55] + ("..." if len(w.effect) > 55 else ""),
                    accent_hex=T.BLOOD,
                    on_tap=lambda widget, idx=i: self._on_major_wound_tap(widget, idx))
                self._major_wound_box.add_widget(item)

    # ── Selection handlers ────────────────────────────────────────────────────

    def _on_minor_mad_tap(self, widget: ListItem, state_idx: int):
        self._deselect_all_minor()
        self._minor_mad_idx       = state_idx
        self._sel_minor_mad_widget = widget
        widget.set_selected(True, persist=True)

    def _on_minor_wound_tap(self, widget: ListItem, idx: int):
        self._deselect_all_minor()
        self._minor_wound_idx        = idx
        self._sel_minor_wound_widget = widget
        widget.set_selected(True, persist=True)

    def _on_major_mad_tap(self, widget: ListItem, state_idx: int):
        self._deselect_all_major()
        self._major_mad_idx       = state_idx
        self._sel_major_mad_widget = widget
        widget.set_selected(True, persist=True)

    def _on_major_wound_tap(self, widget: ListItem, idx: int):
        self._deselect_all_major()
        self._major_wound_idx        = idx
        self._sel_major_wound_widget = widget
        widget.set_selected(True, persist=True)

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
            self._log(f"✨ Minor Restoration: cured {m.kind_label} madness — [{m.roll_range}] {name}")
            self._snack(f"Minor Restoration: {name} cured.", T.SILVER)
            app.refresh_all()
            self._save()
            return

        if self._minor_wound_idx is not None:
            idx    = self._minor_wound_idx
            minors = app.state.minor_wounds
            if idx >= len(minors):
                self._snack("Selection invalid — refresh.", T.BORDER); return
            target = minors[idx]
            self._push_undo()
            app.state.wounds.remove(target)
            self._log(f"✨ Minor Restoration: cured minor wound — {target.description}")
            self._snack(f"Minor Restoration: {target.description} cured.", T.WOUND_MIN)
            app.refresh_all()
            self._save()
            return

        self._snack(
            "Select a Short-Term/Long-Term madness or Minor Wound first.",
            T.BORDER)

    def _on_cast_major(self, *_):
        """Major Restoration: cure selected indefinite madness OR major wound."""
        app = self._app()

        if self._major_mad_idx is not None:
            idx = self._major_mad_idx
            if idx >= len(app.state.madnesses):
                self._snack("Selection invalid — refresh.", T.BORDER); return
            self._push_undo()
            m = app.state.madnesses.pop(idx)
            name = m.name if m.name else "Indefinite Madness"
            self._log(f"✨ Major Restoration: cured Indefinite madness — [{m.roll_range}] {name}")
            self._snack(f"Major Restoration: {name} cured.", T.GOLD_LT)
            app.refresh_all()
            self._save()
            return

        if self._major_wound_idx is not None:
            idx    = self._major_wound_idx
            majors = app.state.major_wounds
            if idx >= len(majors):
                self._snack("Selection invalid — refresh.", T.BORDER); return
            target = majors[idx]
            self._push_undo()
            app.state.wounds.remove(target)
            self._log(
                f"✨ Major Restoration: cured major wound — {target.description} "
                f"(regeneration applies if applicable)")
            self._snack(f"Major Restoration: {target.description} cured.", T.GOLD)
            app.refresh_all()
            self._save()
            return

        self._snack(
            "Select an Indefinite madness or Major Wound first.",
            T.BORDER)
