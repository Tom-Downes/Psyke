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
    ListItem, ExpandableSection, populate_rules_section
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

        self._minor_mad_details:   dict = {}
        self._minor_wound_details: dict = {}
        self._major_mad_details:   dict = {}
        self._major_wound_details: dict = {}
        self._cur_minor_detail = None
        self._cur_major_detail = None

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
        if self._cur_minor_detail:
            self._collapse_panel(self._cur_minor_detail)
            self._cur_minor_detail = None

    def _deselect_all_major(self):
        if self._sel_major_mad_widget:
            self._sel_major_mad_widget.set_selected(False, persist=False)
            self._sel_major_mad_widget = None
            self._major_mad_idx = None
        if self._sel_major_wound_widget:
            self._sel_major_wound_widget.set_selected(False, persist=False)
            self._sel_major_wound_widget = None
            self._major_wound_idx = None
        if self._cur_major_detail:
            self._collapse_panel(self._cur_major_detail)
            self._cur_major_detail = None

    # ── Public refresh ─────────────────────────────────────────────────────────

    def refresh(self):
        app = self._app()
        kind_colors = {"short": T.M_SHORT, "long": T.M_LONG, "indefinite": T.M_INDEF}

        # ── Minor: short + long term madness ─────────────────────────────────
        self._minor_mad_box.clear_widgets()
        self._minor_mad_details.clear()
        self._minor_mad_idx = None
        self._sel_minor_mad_widget = None
        self._cur_minor_detail = None

        minor_mads = [
            (i, m) for i, m in enumerate(app.state.madnesses)
            if m.kind in ("short", "long")]
        if not minor_mads:
            self._minor_mad_box.add_widget(CaptionLabel(
                "No Short-Term or Long-Term madness active.",
                color_hex=T.TEXT_DIM, height_dp=28))
        else:
            for list_idx, (state_idx, m) in enumerate(minor_mads):
                color = kind_colors.get(m.kind, T.M_SHORT)
                name  = m.name if m.name else f"{m.kind_label} Effect"
                item  = ListItem(
                    primary=name,
                    secondary=f"{m.kind_label}  |  {m.roll_range}",
                    accent_hex=color,
                    on_tap=lambda w, si=state_idx, li=list_idx: self._on_minor_mad_tap(w, si, li))
                self._minor_mad_box.add_widget(item)

                detail = MDBoxLayout(
                    orientation="vertical", size_hint_y=None, height=0, opacity=0,
                    padding=[dp(0), dp(4), dp(0), dp(4)])
                inner = DescriptionCard(title=f"{m.kind_label.upper()} MADNESS", color_hex=color)
                _lbl = MultilineLabel(text=f"{name}  |  {m.roll_range}\n\n{m.effect}")
                _lbl.bind(width=lambda inst, val: setattr(inst, "text_size", (val, None)))
                inner.add_widget(_lbl)
                detail.add_widget(inner)
                self._minor_mad_box.add_widget(detail)
                self._minor_mad_details[list_idx] = detail

        # ── Minor: minor wounds ───────────────────────────────────────────────
        self._minor_wound_box.clear_widgets()
        self._minor_wound_details.clear()
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

                detail = MDBoxLayout(
                    orientation="vertical", size_hint_y=None, height=0, opacity=0,
                    padding=[dp(0), dp(4), dp(0), dp(4)])
                inner = DescriptionCard(title="MINOR WOUND", color_hex=T.WOUND_MIN)
                _lbl = MultilineLabel(text=f"{w.description}\n\n{w.effect}")
                _lbl.bind(width=lambda inst, val: setattr(inst, "text_size", (val, None)))
                inner.add_widget(_lbl)
                detail.add_widget(inner)
                self._minor_wound_box.add_widget(detail)
                self._minor_wound_details[i] = detail

        # ── Major: all madness kinds ──────────────────────────────────────────
        self._major_mad_box.clear_widgets()
        self._major_mad_details.clear()
        self._major_mad_idx = None
        self._sel_major_mad_widget = None
        self._cur_major_detail = None

        all_mads = list(enumerate(app.state.madnesses))
        if not all_mads:
            self._major_mad_box.add_widget(CaptionLabel(
                "No madness active.",
                color_hex=T.TEXT_DIM, height_dp=28))
        else:
            for list_idx, (state_idx, m) in enumerate(all_mads):
                color = kind_colors.get(m.kind, T.M_INDEF)
                name  = m.name if m.name else f"{m.kind_label} Effect"
                item = ListItem(
                    primary=name,
                    secondary=f"{m.kind_label}  |  {m.roll_range}",
                    accent_hex=color,
                    on_tap=lambda w, si=state_idx, li=list_idx: self._on_major_mad_tap(w, si, li))
                self._major_mad_box.add_widget(item)

                detail = MDBoxLayout(
                    orientation="vertical", size_hint_y=None, height=0, opacity=0,
                    padding=[dp(0), dp(4), dp(0), dp(4)])
                inner = DescriptionCard(title=f"{m.kind_label.upper()} MADNESS", color_hex=color)
                _lbl = MultilineLabel(text=f"{name}  |  {m.roll_range}\n\n{m.effect}")
                _lbl.bind(width=lambda inst, val: setattr(inst, "text_size", (val, None)))
                inner.add_widget(_lbl)
                detail.add_widget(inner)
                self._major_mad_box.add_widget(detail)
                self._major_mad_details[list_idx] = detail

        # ── Major: all wounds (minor + major) ─────────────────────────────────
        self._major_wound_box.clear_widgets()
        self._major_wound_details.clear()
        self._major_wound_idx = None
        self._sel_major_wound_widget = None

        all_wounds = app.state.wounds
        if not all_wounds:
            self._major_wound_box.add_widget(CaptionLabel(
                "No wounds active.",
                color_hex=T.TEXT_DIM, height_dp=28))
        else:
            for i, w in enumerate(all_wounds):
                color = T.BLOOD if w.severity == "major" else T.WOUND_MIN
                sev_label = "Major Wound" if w.severity == "major" else "Minor Wound"
                item = ListItem(
                    primary=w.description,
                    secondary=f"{sev_label}  |  {w.effect[:40] + ('...' if len(w.effect) > 40 else '')}",
                    accent_hex=color,
                    on_tap=lambda widget, idx=i: self._on_major_wound_tap(widget, idx))
                self._major_wound_box.add_widget(item)

                detail = MDBoxLayout(
                    orientation="vertical", size_hint_y=None, height=0, opacity=0,
                    padding=[dp(0), dp(4), dp(0), dp(4)])
                inner = DescriptionCard(title=sev_label.upper(), color_hex=color)
                _lbl = MultilineLabel(text=f"{w.description}\n\n{w.effect}")
                _lbl.bind(width=lambda inst, val: setattr(inst, "text_size", (val, None)))
                inner.add_widget(_lbl)
                detail.add_widget(inner)
                self._major_wound_box.add_widget(detail)
                self._major_wound_details[i] = detail

    # ── Selection handlers ────────────────────────────────────────────────────

    def _on_minor_mad_tap(self, widget: ListItem, state_idx: int, list_idx: int):
        self._deselect_all_minor()
        self._minor_mad_idx        = state_idx
        self._sel_minor_mad_widget = widget
        widget.set_selected(True, persist=True)
        detail = self._minor_mad_details.get(list_idx)
        if detail:
            self._expand_panel(detail)
            self._cur_minor_detail = detail

    def _on_minor_wound_tap(self, widget: ListItem, idx: int):
        self._deselect_all_minor()
        self._minor_wound_idx        = idx
        self._sel_minor_wound_widget = widget
        widget.set_selected(True, persist=True)
        detail = self._minor_wound_details.get(idx)
        if detail:
            self._expand_panel(detail)
            self._cur_minor_detail = detail

    def _on_major_mad_tap(self, widget: ListItem, state_idx: int, list_idx: int):
        self._deselect_all_major()
        self._major_mad_idx        = state_idx
        self._sel_major_mad_widget = widget
        widget.set_selected(True, persist=True)
        detail = self._major_mad_details.get(list_idx)
        if detail:
            self._expand_panel(detail)
            self._cur_major_detail = detail

    def _on_major_wound_tap(self, widget: ListItem, idx: int):
        self._deselect_all_major()
        self._major_wound_idx        = idx
        self._sel_major_wound_widget = widget
        widget.set_selected(True, persist=True)
        detail = self._major_wound_details.get(idx)
        if detail:
            self._expand_panel(detail)
            self._cur_major_detail = detail

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
            app.notify_event(f"Minor Restoration: {name} cured", "spells", T.SILVER)
            return

        if self._minor_wound_idx is not None:
            idx    = self._minor_wound_idx
            minors = app.state.minor_wounds
            if idx >= len(minors):
                self._snack("Selection invalid — refresh.", T.BORDER); return
            target = minors[idx]
            self._push_undo()
            app.state.wounds.remove(target)
            self._log(f"Minor Restoration: cured minor wound - {target.description}")
            app.refresh_all()
            self._save()
            app.notify_event(
                f"Minor Restoration: {target.description} cured", "spells", T.WOUND_MIN)
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
            app.notify_event(f"Major Restoration: {name} cured", "spells", T.SILVER)
            return

        if self._major_wound_idx is not None:
            idx = self._major_wound_idx
            all_wounds = app.state.wounds
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
            app.notify_event(
                f"Major Restoration: {target.description} cured{regen}", "spells", T.WOUND_MIN)
            return

        self._snack(
            "Select a madness or wound first.",
            T.BORDER)
