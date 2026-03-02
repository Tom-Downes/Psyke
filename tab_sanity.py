"""
Tab 2: Sanity & Madness
FSM-6 parity: D20 named madness tables, named list items, roll display.
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
from kivymd.uix.textfield import MDTextField

from models import (
    SanityState, MADNESS_RULES_TEXT,
    roll_d, clamp, SANITY_BASE
)
from ui_utils import (
    BorderCard, AccentCard, Divider,
    SectionLabel, CaptionLabel, MultilineLabel,
    ListItem, ExpandableSection
)
import theme as T


class SanityTab(ScrollView):

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.do_scroll_x = False
        self._selected_madness_idx: int | None = None
        self._sel_mad_widget: ListItem | None  = None

        root = MDBoxLayout(
            orientation="vertical",
            padding=dp(10),
            spacing=dp(8),
            size_hint_y=None,
            adaptive_height=True
        )
        self.add_widget(root)

        root.add_widget(self._build_sanity_card())
        root.add_widget(self._build_madness_card())
        root.add_widget(self._build_rules_panel())

    # ── Build: Sanity Card ────────────────────────────────────────────────────

    def _build_sanity_card(self) -> BorderCard:
        card = BorderCard(border_hex=T.PURPLE)
        card.add_widget(SectionLabel("SANITY", color_hex=T.PURPLE))

        # LOSE
        card.add_widget(CaptionLabel("LOSE", color_hex=T.BLOOD_LT, height_dp=18))
        lose_row = MDBoxLayout(spacing=dp(3), size_hint_y=None, height=dp(44))
        for amt in (1, 2, 3, 5, 10):
            lose_row.add_widget(MDRaisedButton(
                text=f"−{amt}",
                md_bg_color=T.k(T.RED_DK),
                size_hint_x=0.2,
                on_release=lambda *_, a=amt: self._do_lose(a)))
        card.add_widget(lose_row)

        # RECOVER
        card.add_widget(CaptionLabel("RECOVER", color_hex=T.STAGE_1, height_dp=18))
        rec_row = MDBoxLayout(spacing=dp(3), size_hint_y=None, height=dp(44))
        for amt in (1, 2, 3, 5, 10):
            rec_row.add_widget(MDRaisedButton(
                text=f"+{amt}",
                md_bg_color=T.k(T.GREEN),
                size_hint_x=0.2,
                on_release=lambda *_, a=amt: self._do_recover(a)))
        card.add_widget(rec_row)

        # DM Recovery + Restore
        dm_row = MDBoxLayout(spacing=dp(4), size_hint_y=None, height=dp(44))
        dm_row.add_widget(MDRaisedButton(
            text="DM +1d4", md_bg_color=T.k(T.PURPLE),
            size_hint_x=0.34, on_release=lambda *_: self._on_dm_rec(1)))
        dm_row.add_widget(MDRaisedButton(
            text="DM +2d4", md_bg_color=T.k(T.PURPLE),
            size_hint_x=0.34, on_release=lambda *_: self._on_dm_rec(2)))
        dm_row.add_widget(MDFlatButton(
            text="Restore Max",
            theme_text_color="Custom", text_color=T.k(T.TEXT_DIM),
            size_hint_x=0.32, on_release=self._on_restore_max))
        card.add_widget(dm_row)

        return card

    # ── Build: Madness Card ───────────────────────────────────────────────────

    def _build_madness_card(self) -> BorderCard:
        card = BorderCard(border_hex=T.PURPLE)
        card.add_widget(SectionLabel("MADNESS", color_hex=T.PURPLE))
        card.add_widget(CaptionLabel(
            "Auto-added at sanity thresholds. Roll D20 table or enter custom effect.",
            color_hex=T.TEXT_DIM, height_dp=28))

        card.add_widget(self._build_madness_cat(
            "SHORT-TERM", "1d10 minutes", T.M_SHORT, "short"))
        card.add_widget(self._build_madness_cat(
            "LONG-TERM", "1d10 × 10 hours", T.M_LONG, "long"))
        card.add_widget(self._build_madness_cat(
            "INDEFINITE", "Until cured", T.M_INDEF, "indefinite"))

        card.add_widget(Divider(color_hex=T.PURPLE))
        card.add_widget(SectionLabel("ACTIVE MADNESS", color_hex=T.PURPLE))

        self._madness_list_box = MDBoxLayout(
            orientation="vertical", adaptive_height=True, spacing=dp(2))
        card.add_widget(self._madness_list_box)

        self._mad_detail = MultilineLabel(
            text="Select a madness entry to view its full effect.",
            color_hex=T.TEXT_DIM)
        card.add_widget(self._mad_detail)

        card.add_widget(MDFlatButton(
            text="Remove Selected",
            theme_text_color="Custom", text_color=T.k(T.RED),
            size_hint_y=None, height=dp(36),
            on_release=self._on_remove_madness))

        return card

    def _build_madness_cat(self, title, duration, color, kind) -> AccentCard:
        inner = AccentCard(accent_hex=color)
        # Title row
        tr = MDBoxLayout(size_hint_y=None, height=dp(22), spacing=dp(8))
        tr.add_widget(MDLabel(
            text=title, bold=True, font_style="Caption",
            theme_text_color="Custom", text_color=T.k(color)))
        tr.add_widget(MDLabel(
            text=f"({duration})", font_style="Overline",
            theme_text_color="Custom", text_color=T.k(T.TEXT_DIM)))
        inner.add_widget(tr)

        # Button + input row
        br = MDBoxLayout(spacing=dp(6), size_hint_y=None, height=dp(44))
        btn_colors = {"short": T.M_SHORT, "long": T.M_LONG, "indefinite": T.M_INDEF}
        br.add_widget(MDRaisedButton(
            text="Roll D20",
            md_bg_color=T.k(btn_colors.get(kind, T.PURPLE)),
            size_hint_x=None, width=dp(88),
            on_release=lambda *_, k=kind: self._on_roll_madness(k)))
        field = MDTextField(
            hint_text="Custom effect…", mode="rectangle",
            line_color_normal=T.k(T.BORDER))
        field.bind(on_text_validate=lambda inst, k=kind: self._on_add_custom_madness(k))
        setattr(self, f"_mad_field_{kind}", field)
        br.add_widget(field)
        br.add_widget(MDFlatButton(
            text="Add", size_hint_x=None, width=dp(44),
            theme_text_color="Custom", text_color=T.k(color),
            on_release=lambda *_, k=kind: self._on_add_custom_madness(k)))
        inner.add_widget(br)
        return inner

    def _build_rules_panel(self) -> ExpandableSection:
        sec = ExpandableSection("Madness Rules", accent_hex=T.PURPLE)
        sec.add_content(MultilineLabel(text=MADNESS_RULES_TEXT, color_hex=T.TEXT_DIM))
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

    # ── Public refresh ─────────────────────────────────────────────────────────

    def refresh(self):
        app = self._app()
        self._madness_list_box.clear_widgets()
        self._selected_madness_idx = None
        self._sel_mad_widget       = None
        self._mad_detail.text      = "Select a madness entry to view its full effect."

        if not app.state.madnesses:
            self._madness_list_box.add_widget(CaptionLabel(
                "No active madness. Entries appear automatically at sanity thresholds.",
                color_hex=T.TEXT_DIM, height_dp=36))
        else:
            for i, m in enumerate(app.state.madnesses):
                kind_colors = {
                    "short": T.M_SHORT, "long": T.M_LONG, "indefinite": T.M_INDEF}
                color = kind_colors.get(m.kind, T.PURPLE)
                # Primary: named effect title (e.g. "Black Out", "Tremors")
                # Secondary: type + roll label
                primary_text   = m.name if m.name else f"{m.kind_label} Effect"
                secondary_text = f"{m.kind_label}  ·  {m.roll_range}"
                item = ListItem(
                    primary=primary_text,
                    secondary=secondary_text,
                    accent_hex=color,
                    on_tap=lambda widget, idx=i: self._on_madness_tap(widget, idx))
                self._madness_list_box.add_widget(item)

    # ── Event: Lose / Recover ─────────────────────────────────────────────────

    def _do_lose(self, amt: int):
        app = self._app()
        self._push_undo()
        threshs = app.state.apply_loss(amt)
        self._log(f"Sanity loss: -{amt} → {app.state.current_sanity}/{app.state.max_sanity}")
        self._handle_thresholds(threshs)
        app.refresh_all()
        self._save()

    def _do_recover(self, amt: int):
        app = self._app()
        self._push_undo()
        app.state.apply_recovery(amt)
        self._log(f"Sanity recovery: +{amt} → {app.state.current_sanity}/{app.state.max_sanity}")
        app.refresh_all()
        self._save()

    def _on_dm_rec(self, dice: int):
        app   = self._app()
        rolls = roll_d(4, dice)
        amt   = sum(rolls)
        rt    = "+".join(map(str, rolls))
        self._push_undo()
        app.state.apply_recovery(amt)
        self._log(
            f"DM Recovery: {dice}d4 ({rt}) = +{amt} → "
            f"{app.state.current_sanity}/{app.state.max_sanity}")
        app.refresh_all()
        self._save()

    def _on_restore_max(self, *_):
        app = self._app()
        self._push_undo()
        old = app.state.current_sanity
        app.state.current_sanity = app.state.max_sanity
        app.state.rebuild_thresholds()
        self._log(f"Restored to max: {old} → {app.state.max_sanity}")
        app.refresh_all()
        self._save()

    # ── Event: Roll D20 madness ───────────────────────────────────────────────

    def _on_roll_madness(self, kind: str):
        app = self._app()
        self._push_undo()
        m = app.state.add_madness(kind)
        labels = {"short": "Short-Term", "long": "Long-Term", "indefinite": "Indefinite"}
        self._log(
            f"Madness rolled ({labels[kind]}): [{m.roll_range}] "
            f"{m.name}  —  {m.effect[:60]}")
        self._snack(
            f"[{m.roll_range}] {m.name}",
            {"short": T.M_SHORT, "long": T.M_LONG, "indefinite": T.M_INDEF}.get(kind, T.PURPLE))
        app.refresh_all()
        self._save()

    # ── Event: Add custom madness ─────────────────────────────────────────────

    def _on_add_custom_madness(self, kind: str):
        app   = self._app()
        field = getattr(self, f"_mad_field_{kind}", None)
        if not field: return
        text = field.text.strip()
        if not text:
            self._snack("Enter a custom effect.", T.BORDER); return
        self._push_undo()
        m = app.state.add_madness(kind, custom_effect=text)
        field.text  = ""
        field.focus = False
        self._log(f"Custom madness ({kind}): {text[:60]}")
        app.refresh_all()
        self._save()

    # ── Event: Select madness entry ───────────────────────────────────────────

    def _on_madness_tap(self, widget: ListItem, idx: int):
        if self._sel_mad_widget and self._sel_mad_widget is not widget:
            self._sel_mad_widget.set_selected(False, persist=False)
        self._selected_madness_idx = idx
        self._sel_mad_widget       = widget
        widget.set_selected(True, persist=True)
        app = self._app()
        if idx < len(app.state.madnesses):
            m = app.state.madnesses[idx]
            display_name = m.name if m.name else f"{m.kind_label} Effect"
            self._mad_detail.text = (
                f"{display_name}\n"
                f"Type: {m.kind_label}  ·  Roll: {m.roll_range}\n"
                f"{m.timestamp}\n\n"
                f"{m.effect}")

    # ── Event: Remove madness ─────────────────────────────────────────────────

    def _on_remove_madness(self, *_):
        idx = self._selected_madness_idx
        if idx is None:
            self._snack("Select a madness entry.", T.BORDER); return
        app = self._app()
        if idx >= len(app.state.madnesses): return
        self._push_undo()
        m = app.state.madnesses.pop(idx)
        name = m.name if m.name else m.kind_label
        self._log(f"Madness removed: [{m.roll_range}] {name}")
        self._selected_madness_idx = None
        self._sel_mad_widget       = None
        app.refresh_all()
        self._save()

    # ── Threshold handling ────────────────────────────────────────────────────

    def _handle_thresholds(self, threshs):
        app = self._app()
        for label, kind in threshs:
            if kind == "zero":
                self._log(f"WARNING: {label}")
                MDSnackbar(
                    MDLabel(text=label,
                            theme_text_color="Custom", text_color=(1, 1, 1, 1)),
                    md_bg_color=T.k(T.BLOOD_DK), duration=4
                ).open()
                continue
            m = app.state.add_madness(kind)
            self._log(
                f"THRESHOLD: {label} → {m.kind_label}: "
                f"[{m.roll_range}] {m.name}  —  {m.effect[:50]}")
            MDSnackbar(
                MDLabel(
                    text=f"Threshold! {m.kind_label}: {m.name}",
                    theme_text_color="Custom", text_color=(1, 1, 1, 1)),
                md_bg_color=T.k(T.PURPLE), duration=3
            ).open()
        if threshs:
            app.refresh_all()
