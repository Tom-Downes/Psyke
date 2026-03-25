"""
Tab 2: Sanity & Madness  (V2 redesign)

Two-page swipeable layout:
  Page 0 — Sanity & Madness: sanity card, active madness list, rules
  Page 1 — Add Madness: table picker, pending preview, add button

Swipe left/right to move between pages.
"""
from __future__ import annotations

from datetime import datetime

from kivy.app import App
from kivy.graphics import Color, Rectangle
from kivy.metrics import dp
from kivy.uix.scrollview import ScrollView
from kivy.uix.widget import Widget

from kivymd.uix.boxlayout import MDBoxLayout
from kivymd.uix.button import MDFlatButton, MDRaisedButton
from kivymd.uix.label import MDLabel
from kivymd.uix.menu import MDDropdownMenu
from kivymd.uix.snackbar import MDSnackbar

from models import (
    SanityState, MADNESS_RULES_TEXT,
    SHORT_TERM_MADNESS_TABLE, LONG_TERM_MADNESS_TABLE, INDEFINITE_MADNESS_TABLE,
    roll_d, clamp, SANITY_BASE, MadnessEntry
)
from ui_utils import (
    BorderCard, AccentCard, DescriptionCard, Divider,
    SectionLabel, CaptionLabel, MultilineLabel,
    ListItem, ExpandableSection, themed_field, PickerButton, PageDot
)
import theme as T


class SanityTab(MDBoxLayout):

    def __init__(self, **kwargs):
        kwargs.setdefault("orientation", "vertical")
        super().__init__(**kwargs)

        self._selected_madness_idx: int | None = None
        self._sel_mad_widget: ListItem | None  = None
        self._pending_madness: dict | None = None   # {kind, roll, name, effect}

        # Dropdown menus (lazy-created)
        self._short_menu   = None
        self._long_menu    = None
        self._indef_menu   = None

        # ── Page state ──────────────────────────────────────────────────────
        self._page = 0  # 0 = Sanity & Madness, 1 = Add Madness

        # Page indicator bar
        self.add_widget(self._build_page_indicator())

        # Content area — holds exactly one ScrollView at a time
        self._content_area = MDBoxLayout(orientation="vertical")
        self.add_widget(self._content_area)

        # ── Page 0 (Sanity & Madness) ────────────────────────────────────────
        self._sv0 = ScrollView(do_scroll_x=False)
        p0 = MDBoxLayout(
            orientation="vertical",
            padding=dp(10), spacing=dp(8),
            size_hint_y=None, adaptive_height=True)
        p0.add_widget(self._build_sanity_card())
        p0.add_widget(self._build_active_madness_card())
        p0.add_widget(self._build_rules_panel())
        self._sv0.add_widget(p0)

        # ── Page 1 (Add Madness) ─────────────────────────────────────────────
        self._sv1 = ScrollView(do_scroll_x=False)
        p1 = MDBoxLayout(
            orientation="vertical",
            padding=dp(10), spacing=dp(8),
            size_hint_y=None, adaptive_height=True)
        p1.add_widget(self._build_madness_add_card())
        self._sv1.add_widget(p1)

        # Show page 0 on launch
        self._content_area.add_widget(self._sv0)
        self._update_indicator()

    # ── Page indicator ───────────────────────────────────────────────────────

    def _build_page_indicator(self) -> MDBoxLayout:
        row = MDBoxLayout(
            size_hint_y=None, height=dp(26),
            spacing=dp(4), padding=[dp(10), dp(2), dp(10), dp(2)])

        with row.canvas.before:
            Color(*T.k(T.BG_INSET))
            self._ind_bg = Rectangle()
        row.bind(pos=lambda w, _: setattr(self._ind_bg, 'pos', w.pos),
                 size=lambda w, _: setattr(self._ind_bg, 'size', w.size))

        self._ind_lbl0 = MDLabel(
            text="Sanity & Madness", halign="right",
            theme_text_color="Custom", text_color=T.k(T.PURPLE),
            font_style="Caption", bold=True,
            size_hint_x=0.42)

        self._dot0 = PageDot(color_hex=T.PURPLE)
        self._dot1 = PageDot(color_hex=T.TEXT_DIM)

        self._ind_lbl1 = MDLabel(
            text="Add Madness", halign="left",
            theme_text_color="Custom", text_color=T.k(T.TEXT_DIM),
            font_style="Caption", bold=False,
            size_hint_x=0.34)

        row.add_widget(self._ind_lbl0)
        row.add_widget(self._dot0)
        row.add_widget(self._dot1)
        row.add_widget(self._ind_lbl1)
        return row

    def _update_indicator(self):
        if self._page == 0:
            self._dot0.set_color(T.PURPLE)
            self._dot1.set_color(T.TEXT_DIM)
            self._ind_lbl0.bold       = True
            self._ind_lbl0.text_color = T.k(T.PURPLE)
            self._ind_lbl1.bold       = False
            self._ind_lbl1.text_color = T.k(T.TEXT_DIM)
        else:
            self._dot0.set_color(T.TEXT_DIM)
            self._dot1.set_color(T.M_SHORT)
            self._ind_lbl0.bold       = False
            self._ind_lbl0.text_color = T.k(T.TEXT_DIM)
            self._ind_lbl1.bold       = True
            self._ind_lbl1.text_color = T.k(T.M_SHORT)

    def _go_page(self, page: int):
        if page == self._page:
            return
        self._page = page
        self._clear_mad_detail()
        self._content_area.clear_widgets()
        self._content_area.add_widget(self._sv0 if page == 0 else self._sv1)
        self._update_indicator()

    # ── Swipe + click-off detection ──────────────────────────────────────────

    def on_touch_down(self, touch):
        if self.collide_point(*touch.pos):
            touch.ud['sanity_swipe_start'] = (touch.x, touch.y)
            # If on page 0 and touch is not on any madness list item → clear detail
            if self._page == 0:
                if not any(c.collide_point(*touch.pos)
                           for c in list(self._madness_list_box.children)):
                    self._clear_mad_detail()
        return super().on_touch_down(touch)

    def on_touch_up(self, touch):
        start = touch.ud.get('sanity_swipe_start')
        if start:
            dx = touch.x - start[0]
            dy = touch.y - start[1]
            if abs(dx) > dp(50) and abs(dx) > abs(dy) * 1.5:
                if dx < 0:
                    self._go_page(1)
                elif dx > 0:
                    self._go_page(0)
        return super().on_touch_up(touch)

    # ── Build: Sanity Card ────────────────────────────────────────────────────

    def _build_sanity_card(self) -> BorderCard:
        card = BorderCard(border_hex=T.PURPLE)
        card.add_widget(SectionLabel("SANITY", color_hex=T.PURPLE))

        amt_row = MDBoxLayout(spacing=dp(6), size_hint_y=None, height=dp(52))
        self._amt_field = themed_field(
            hint_text="Enter amount...",
            accent_hex=T.PURPLE,
            input_filter="int",
            size_hint_x=0.45)
        amt_row.add_widget(self._amt_field)
        self._lose_btn = MDRaisedButton(
            text="LOSE",
            md_bg_color=T.k(T.BLOOD),
            size_hint_x=0.27,
            on_release=self._do_lose_input)
        self._rec_btn = MDRaisedButton(
            text="RECOVER",
            md_bg_color=T.k(T.GREEN),
            size_hint_x=0.27,
            on_release=self._do_recover_input)
        amt_row.add_widget(self._lose_btn)
        amt_row.add_widget(self._rec_btn)
        card.add_widget(amt_row)

        card.add_widget(CaptionLabel(
            "Enter a number, then tap LOSE or RECOVER.",
            color_hex=T.TEXT_DIM, height_dp=18))

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

    # ── Build: Add Madness Card (Page 1) ──────────────────────────────────────

    def _build_madness_add_card(self) -> BorderCard:
        card = BorderCard(border_hex=T.PURPLE)
        card.add_widget(SectionLabel("ADD MADNESS", color_hex=T.PURPLE))
        card.add_widget(CaptionLabel(
            "Pick from the D20 table. Auto-added at sanity thresholds.",
            color_hex=T.TEXT_DIM, height_dp=28))

        card.add_widget(self._build_madness_add_row(
            "SHORT-TERM", "1d10 minutes", T.M_SHORT, "short"))
        card.add_widget(Divider(color_hex=T.BORDER))
        card.add_widget(self._build_madness_add_row(
            "LONG-TERM", "1d10 × 10 hours", T.M_LONG, "long"))
        card.add_widget(Divider(color_hex=T.BORDER))
        card.add_widget(self._build_madness_add_row(
            "INDEFINITE", "Until cured", T.M_INDEF, "indefinite"))

        # Pending selection preview
        self._pending_card = DescriptionCard(
            title="SELECTED MADNESS",
            color_hex=T.PURPLE)
        self._pending_lbl = MDLabel(
            text="Select from a table above to preview.",
            theme_text_color="Custom", text_color=T.k(T.TEXT_DIM),
            font_style="Body2", size_hint_y=None, adaptive_height=True)
        self._pending_lbl.bind(
            width=lambda inst, val: setattr(inst, "text_size", (val, None)))
        self._pending_card.add_widget(self._pending_lbl)
        card.add_widget(self._pending_card)

        self._add_sel_btn = MDRaisedButton(
            text="Add Selected Madness",
            md_bg_color=T.k(T.PURPLE),
            disabled=True,
            size_hint_y=None, height=dp(44),
            on_release=self._on_add_pending)
        card.add_widget(self._add_sel_btn)

        return card

    def _build_madness_add_row(self, title, duration, color, kind) -> AccentCard:
        inner = AccentCard(accent_hex=color)
        tr = MDBoxLayout(size_hint_y=None, height=dp(22), spacing=dp(8))
        tr.add_widget(MDLabel(
            text=title, bold=True, font_style="Caption",
            theme_text_color="Custom", text_color=T.k(color)))
        tr.add_widget(MDLabel(
            text=f"({duration})", font_style="Overline",
            theme_text_color="Custom", text_color=T.k(T.TEXT_DIM)))
        inner.add_widget(tr)

        pick_btn = PickerButton(
            text=f"PICK {title} MADNESS",
            color_hex=color,
            on_press=lambda btn, k=kind: self._open_madness_menu(k, btn),
            size_hint_x=1.0)
        inner.add_widget(pick_btn)
        return inner

    # ── Build: Active Madness Card ────────────────────────────────────────────

    def _build_active_madness_card(self) -> BorderCard:
        card = BorderCard(border_hex=T.PURPLE)
        card.add_widget(SectionLabel("ACTIVE MADNESS", color_hex=T.PURPLE))

        self._madness_list_box = MDBoxLayout(
            orientation="vertical", adaptive_height=True, spacing=dp(2))
        card.add_widget(self._madness_list_box)

        card.add_widget(Divider(color_hex=T.PURPLE))

        self._mad_detail_card = DescriptionCard(
            title="ACTIVE MADNESS",
            color_hex=T.PURPLE)
        self._mad_detail = MDLabel(
            text="Select a madness entry to view its full effect.",
            theme_text_color="Custom",
            text_color=T.k(T.TEXT_DIM),
            font_style="Body1",
            size_hint_y=None,
            adaptive_height=True)
        self._mad_detail.bind(
            width=lambda inst, val: setattr(inst, "text_size", (val, None)))
        self._mad_detail_card.add_widget(self._mad_detail)
        card.add_widget(self._mad_detail_card)

        card.add_widget(MDFlatButton(
            text="Remove Selected",
            theme_text_color="Custom", text_color=T.k(T.RED),
            size_hint_y=None, height=dp(36),
            on_release=self._on_remove_madness))

        return card

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

    def _clear_mad_detail(self):
        if self._sel_mad_widget:
            self._sel_mad_widget.set_selected(False, persist=False)
        self._selected_madness_idx = None
        self._sel_mad_widget       = None
        self._mad_detail.text       = "Select a madness entry to view its full effect."
        self._mad_detail.text_color = T.k(T.TEXT_DIM)
        self._mad_detail_card.set_title("ACTIVE MADNESS", T.PURPLE)

    # ── Public refresh ─────────────────────────────────────────────────────────

    def refresh(self):
        app = self._app()
        self._clear_mad_detail()

        self._madness_list_box.clear_widgets()
        kind_colors = {"short": T.M_SHORT, "long": T.M_LONG, "indefinite": T.M_INDEF}

        if not app.state.madnesses:
            self._madness_list_box.add_widget(CaptionLabel(
                "No active madness effects.",
                color_hex=T.TEXT_DIM, height_dp=36))
        else:
            for idx, m in enumerate(app.state.madnesses):
                name_txt = m.name if m.name else f"{m.kind_label} Effect"
                color    = kind_colors.get(m.kind, T.PURPLE)
                item = ListItem(
                    primary=name_txt,
                    secondary=f"{m.kind_label}  |  {m.roll_range}",
                    accent_hex=color,
                    on_tap=lambda widget, i=idx: self._on_madness_tap(widget, i))
                self._madness_list_box.add_widget(item)

    # ── Sanity input ───────────────────────────────────────────────────────────

    def _get_input_amt(self) -> int | None:
        try:
            v = int(self._amt_field.text.strip())
            if v <= 0:
                raise ValueError
            return v
        except (ValueError, AttributeError):
            self._snack("Enter a positive whole number.", T.BORDER)
            return None

    def _do_lose_input(self, *_):
        amt = self._get_input_amt()
        if amt is None: return
        self._amt_field.text = ""
        app = self._app()
        self._push_undo()
        threshs = app.state.apply_loss(amt)
        self._log(f"Sanity loss: -{amt} > {app.state.current_sanity}/{app.state.max_sanity}")
        self._handle_thresholds(threshs)
        app.refresh_all()
        self._save()

    def _do_recover_input(self, *_):
        amt = self._get_input_amt()
        if amt is None: return
        self._amt_field.text = ""
        app = self._app()
        self._push_undo()
        app.state.apply_recovery(amt)
        self._log(f"Sanity recovery: +{amt} > {app.state.current_sanity}/{app.state.max_sanity}")
        app.refresh_all()
        self._save()

    def _on_dm_rec(self, dice: int):
        app   = self._app()
        rolls = roll_d(4, dice)
        amt   = sum(rolls)
        rt    = "+".join(map(str, rolls))
        self._push_undo()
        app.state.apply_recovery(amt)
        self._log(f"DM Recovery: {dice}d4 ({rt}) = +{amt} > "
                  f"{app.state.current_sanity}/{app.state.max_sanity}")
        app.refresh_all()
        self._save()

    def _on_restore_max(self, *_):
        app = self._app()
        self._push_undo()
        old = app.state.current_sanity
        app.state.current_sanity = app.state.max_sanity
        app.state.rebuild_thresholds()
        self._log(f"Restored to max: {old} > {app.state.max_sanity}")
        app.refresh_all()
        self._save()

    # ── Madness dropdown picker ────────────────────────────────────────────────

    def _open_madness_menu(self, kind: str, anchor_widget):
        table_map = {
            "short":      SHORT_TERM_MADNESS_TABLE,
            "long":       LONG_TERM_MADNESS_TABLE,
            "indefinite": INDEFINITE_MADNESS_TABLE,
        }
        table = table_map.get(kind, SHORT_TERM_MADNESS_TABLE)
        items = [
            {
                "text": f"{roll}. {name}",
                "viewclass": "OneLineListItem",
                "on_release": (
                    lambda r=roll, n=name, e=effect, k=kind:
                    self._on_table_select(k, r, n, e)
                ),
            }
            for roll, name, effect in table
        ]
        menu = MDDropdownMenu(
            caller=anchor_widget,
            items=items,
            width_mult=4,
            max_height=dp(300),
        )
        menu.open()
        setattr(self, f"_menu_{kind}", menu)

    def _on_table_select(self, kind: str, roll: str, name: str, effect: str):
        self._pending_madness = {"kind": kind, "roll": roll, "name": name, "effect": effect}
        color = {"short": T.M_SHORT, "long": T.M_LONG, "indefinite": T.M_INDEF}.get(kind, T.PURPLE)
        label = {"short": "SHORT-TERM MADNESS", "long": "LONG-TERM MADNESS",
                 "indefinite": "INDEFINITE MADNESS"}.get(kind, "SELECTED MADNESS")
        self._pending_card.set_title(f"SELECTED — {label}", color)
        self._pending_lbl.text_color = T.k(T.TEXT)
        body = (effect[:120] + "...") if len(effect) > 120 else effect
        self._pending_lbl.text = f"{roll}. {name}\n\n{body}"
        self._add_sel_btn.disabled = False
        m = getattr(self, f"_menu_{kind}", None)
        if m:
            m.dismiss()

    def _on_add_pending(self, *_):
        if not self._pending_madness:
            return
        p = self._pending_madness
        app = self._app()
        self._push_undo()
        m = MadnessEntry(
            kind=p["kind"],
            roll_range=p["roll"],
            effect=p["effect"],
            name=p["name"],
            timestamp=datetime.now().strftime("%H:%M"),
        )
        app.state.madnesses.append(m)
        label = {"short": "Short-Term", "long": "Long-Term",
                 "indefinite": "Indefinite"}.get(p["kind"], p["kind"])
        self._log(f"Madness added ({label}): [{p['roll']}] {p['name']}")
        self._snack(
            f"[{p['roll']}] {p['name']}",
            {"short": T.M_SHORT, "long": T.M_LONG, "indefinite": T.M_INDEF}.get(p["kind"], T.PURPLE))
        self._pending_madness = None
        self._pending_lbl.text = "Select from a table above to preview."
        self._pending_lbl.text_color = T.k(T.TEXT_DIM)
        self._pending_card.set_title("SELECTED MADNESS", T.PURPLE)
        self._add_sel_btn.disabled = True
        app.refresh_all()
        self._save()

    # ── Select madness entry ───────────────────────────────────────────────────

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
            color = {"short": T.M_SHORT, "long": T.M_LONG,
                     "indefinite": T.M_INDEF}.get(m.kind, T.PURPLE)
            kind_title = {"short": "SHORT-TERM MADNESS", "long": "LONG-TERM MADNESS",
                          "indefinite": "INDEFINITE MADNESS"}.get(m.kind, "ACTIVE MADNESS")
            self._mad_detail_card.set_title(kind_title, color)
            self._mad_detail.text_color = T.k(T.TEXT)
            self._mad_detail.text = (
                f"{display_name}  |  {m.roll_range}\n\n"
                f"{m.effect}")

    # ── Remove madness ─────────────────────────────────────────────────────────

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
                f"THRESHOLD: {label} > {m.kind_label}: "
                f"[{m.roll_range}] {m.name} -- {m.effect[:50]}")
        if threshs:
            app.refresh_all()
