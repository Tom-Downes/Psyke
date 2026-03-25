"""
Tab 2: Sanity & Insanity  (V2 redesign)

Two-page swipeable layout:
  Page 0 — Sanity & Insanity: sanity card, active insanity list, rules
  Page 1 — Add Insanity: D20 dropdown pickers, preview + Apply button

Swipe left/right to move between pages.
"""
from __future__ import annotations

from datetime import datetime

from kivy.app import App
from kivy.clock import Clock
from kivy.graphics import Color, Rectangle
from kivy.metrics import dp
from kivy.uix.scrollview import ScrollView
from kivy.uix.widget import Widget

from kivymd.uix.boxlayout import MDBoxLayout
from kivymd.uix.button import MDIconButton, MDRaisedButton
from kivymd.uix.label import MDLabel
from kivymd.uix.menu import MDDropdownMenu
from kivymd.uix.snackbar import MDSnackbar

from models import (
    SanityState, MADNESS_RULES_TEXT,
    SHORT_TERM_MADNESS_TABLE, LONG_TERM_MADNESS_TABLE, INDEFINITE_MADNESS_TABLE,
    roll_d, clamp, SANITY_BASE, MadnessEntry, roll_insanity_duration
)
from ui_utils import (
    BorderCard, AccentCard, DescriptionCard, Divider,
    SectionLabel, CaptionLabel,
    ListItem, ExpandableSection, themed_field, PickerButton, PageDot,
    populate_rules_section
)
import theme as T


class SanityTab(MDBoxLayout):

    def __init__(self, **kwargs):
        kwargs.setdefault("orientation", "vertical")
        super().__init__(**kwargs)

        # Selection tracked by OBJECT identity (like fear tab tracks by name)
        self._selected_madness: MadnessEntry | None = None
        self._sel_mad_widget: ListItem | None = None
        self._madness_details: dict = {}   # idx -> detail MDBoxLayout
        self._madness_items: dict = {}    # idx -> ListItem widget

        # Add-page: kind -> (detail MDBoxLayout, desc MDLabel, apply_btn)
        self._add_preview: dict = {}
        # Add-page pending selection: kind -> (roll, name, effect)
        self._pending: dict = {}

        # ── Page state ──────────────────────────────────────────────────────
        self._page = 0  # 0 = Sanity & Insanity, 1 = Add Insanity

        self.add_widget(self._build_page_indicator())

        self._content_area = MDBoxLayout(orientation="vertical")
        self.add_widget(self._content_area)

        # ── Page 0 (Sanity & Insanity) ───────────────────────────────────────
        self._sv0 = ScrollView(do_scroll_x=False)
        p0 = MDBoxLayout(
            orientation="vertical",
            padding=dp(10), spacing=dp(8),
            size_hint_y=None, adaptive_height=True)
        p0.add_widget(self._build_sanity_card())
        p0.add_widget(self._build_active_madness_card())
        p0.add_widget(self._build_rules_panel())
        self._sv0.add_widget(p0)

        # ── Page 1 (Add Insanity) ────────────────────────────────────────────
        self._sv1 = ScrollView(do_scroll_x=False)
        p1 = MDBoxLayout(
            orientation="vertical",
            padding=dp(10), spacing=dp(8),
            size_hint_y=None, adaptive_height=True)
        p1.add_widget(self._build_madness_add_card())
        p1.add_widget(self._build_rules_panel())
        self._sv1.add_widget(p1)

        self._content_area.add_widget(self._sv0)
        self._update_indicator()

    # ── Page indicator ───────────────────────────────────────────────────────

    def _build_page_indicator(self) -> MDBoxLayout:
        row = MDBoxLayout(
            size_hint_y=None, height=dp(26),
            spacing=dp(4), padding=[dp(10), dp(2), dp(10), dp(2)])

        with row.canvas.before:
            Color(*T.k(T.PURPLE, 0.15))
            self._ind_bg = Rectangle()
        row.bind(pos=lambda w, _: setattr(self._ind_bg, 'pos', w.pos),
                 size=lambda w, _: setattr(self._ind_bg, 'size', w.size))

        self._ind_lbl0 = MDLabel(
            text="Sanity & Insanity", halign="right",
            theme_text_color="Custom", text_color=T.k(T.WHITE),
            font_style="Caption", bold=True, size_hint_x=0.42)

        self._dot0 = PageDot(color_hex=T.PURPLE)
        self._dot1 = PageDot(color_hex=T.TEXT_DIM)

        self._ind_lbl1 = MDLabel(
            text="Add Insanity", halign="left",
            theme_text_color="Custom", text_color=T.k(T.TEXT_DIM),
            font_style="Caption", bold=False, size_hint_x=0.34)

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
            self._dot1.set_color(T.PURPLE_LT)
            self._ind_lbl0.bold       = False
            self._ind_lbl0.text_color = T.k(T.TEXT_DIM)
            self._ind_lbl1.bold       = True
            self._ind_lbl1.text_color = T.k(T.PURPLE_LT)

    def _reset_add_page(self):
        """Reset all add-page picker buttons and preview panels to default."""
        self._pending.clear()
        for kind, pair in self._add_preview.items():
            detail, desc_lbl, pick_btn, default_text = pair
            self._collapse_panel(detail)
            desc_lbl.text = ""
            pick_btn._lbl.text = default_text

    def _go_page(self, page: int):
        if page == self._page:
            return
        if self._page == 1:
            self._reset_add_page()
        self._page = page
        self._content_area.clear_widgets()
        self._content_area.add_widget(self._sv0 if page == 0 else self._sv1)
        self._update_indicator()

    # ── Swipe detection ──────────────────────────────────────────────────────

    def on_touch_down(self, touch):
        if self.collide_point(*touch.pos):
            touch.ud['sanity_swipe_start'] = (touch.x, touch.y)
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
            text="LOSE", md_bg_color=T.k(T.BLOOD),
            size_hint_x=0.27, on_release=self._do_lose_input)
        self._rec_btn = MDRaisedButton(
            text="RECOVER", md_bg_color=T.k(T.GREEN),
            size_hint_x=0.27, on_release=self._do_recover_input)
        amt_row.add_widget(self._lose_btn)
        amt_row.add_widget(self._rec_btn)
        card.add_widget(amt_row)

        card.add_widget(CaptionLabel(
            "Enter a number, then tap LOSE or RECOVER.",
            color_hex=T.TEXT_DIM, height_dp=18))

        return card

    # ── Build: Add Insanity Card (Page 1) ─────────────────────────────────────

    def _build_madness_add_card(self) -> BorderCard:
        card = BorderCard(border_hex=T.PURPLE)
        card.add_widget(SectionLabel("ADD INSANITY", color_hex=T.PURPLE))
        card.add_widget(CaptionLabel(
            "Select from the table — preview appears below. Tap Apply to add.",
            color_hex=T.TEXT_DIM, height_dp=28))

        rows = [
            ("SHORT-TERM", "1d10 minutes",    T.M_SHORT, "short"),
            ("LONG-TERM",  "1d10 × 10 hours", T.M_LONG,  "long"),
            ("INDEFINITE", "Until cured",      T.M_INDEF, "indefinite"),
        ]
        for i, (title, duration, color, kind) in enumerate(rows):
            default_text = f"PICK {title} INSANITY"

            # AccentCard: title row + [PickerButton | Apply button]
            inner = AccentCard(accent_hex=color)
            tr = MDBoxLayout(size_hint_y=None, height=dp(22), spacing=dp(8))
            tr.add_widget(MDLabel(
                text=title, bold=True, font_style="Caption",
                theme_text_color="Custom", text_color=T.k(color)))
            tr.add_widget(MDLabel(
                text=f"({duration})", font_style="Overline",
                theme_text_color="Custom", text_color=T.k(T.TEXT_DIM)))
            inner.add_widget(tr)

            btn_row = MDBoxLayout(
                size_hint_y=None, height=dp(48), spacing=dp(6))
            pick_btn = PickerButton(
                text=default_text,
                color_hex=color,
                on_press=lambda btn, k=kind: self._open_madness_menu(k, btn),
                size_hint_x=1.0)
            btn_row.add_widget(pick_btn)
            btn_row.add_widget(MDRaisedButton(
                text="APPLY",
                md_bg_color=T.k(color),
                size_hint_x=None, width=dp(80),
                on_release=lambda *_, k=kind: self._apply_insanity(k)))
            inner.add_widget(btn_row)
            card.add_widget(inner)

            # Preview panel — added directly to card, BENEATH the AccentCard
            detail = MDBoxLayout(
                orientation="vertical", size_hint_y=None, height=0, opacity=0,
                padding=[dp(0), dp(4), dp(0), dp(4)])
            desc_card = DescriptionCard(title=f"{title} INSANITY", color_hex=color)
            desc_lbl = MDLabel(
                text="",
                theme_text_color="Custom", text_color=T.k(T.TEXT),
                font_style="Body2", size_hint_y=None, adaptive_height=True)
            desc_lbl.bind(width=lambda inst, val: setattr(inst, "text_size", (val, None)))
            desc_card.add_widget(desc_lbl)
            detail.add_widget(desc_card)
            card.add_widget(detail)
            # Store (detail, desc_lbl, pick_btn, default_text) for later update
            self._add_preview[kind] = (detail, desc_lbl, pick_btn, default_text)

            if i < len(rows) - 1:
                card.add_widget(Divider(color_hex=T.BORDER))

        return card

    # ── Build: Active Insanity Card ───────────────────────────────────────────

    def _build_active_madness_card(self) -> BorderCard:
        card = BorderCard(border_hex=T.PURPLE)

        # Header with trash-can remove button (same pattern as fear list)
        hdr = MDBoxLayout(size_hint_y=None, height=dp(32), spacing=dp(8))
        hdr.add_widget(SectionLabel("ACTIVE INSANITY", color_hex=T.PURPLE))
        hdr.add_widget(Widget())
        hdr.add_widget(MDIconButton(
            icon="trash-can-outline",
            theme_icon_color="Custom", icon_color=T.k(T.RED),
            size_hint_x=None, width=dp(40),
            on_release=self._on_remove_madness))
        card.add_widget(hdr)

        self._madness_list_box = MDBoxLayout(
            orientation="vertical", adaptive_height=True, spacing=dp(2))
        card.add_widget(self._madness_list_box)

        return card

    def _build_rules_panel(self) -> BorderCard:
        wrapper = BorderCard(border_hex=T.PURPLE)
        sec = ExpandableSection(
            "INSANITY RULES",
            accent_hex=T.PURPLE_LT,
        )
        populate_rules_section(sec, MADNESS_RULES_TEXT, T.PURPLE_LT)
        wrapper.add_widget(sec)
        return wrapper

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

    def _sync_panel_height(self, panel):
        """Set panel height to its content height — called via Clock after layout."""
        panel.height = panel.minimum_height

    def _expand_panel(self, detail: MDBoxLayout):
        """Expand a detail panel — exact same pattern as Fear Severity/Desens."""
        detail.size_hint_y = None
        detail.opacity     = 1
        Clock.schedule_once(lambda dt, d=detail: self._sync_panel_height(d))

    def _collapse_panel(self, detail: MDBoxLayout):
        """Collapse a detail panel — exact same pattern as Fear Severity/Desens."""
        detail.size_hint_y = None
        detail.height      = 0
        detail.opacity     = 0

    # ── Public refresh ─────────────────────────────────────────────────────────

    def refresh(self):
        app = self._app()

        # Preserve selection across rebuild (track by object identity)
        prev = self._selected_madness
        self._sel_mad_widget = None
        self._madness_list_box.clear_widgets()
        self._madness_details.clear()
        self._madness_items.clear()

        kind_colors = {"short": T.M_SHORT, "long": T.M_LONG, "indefinite": T.M_INDEF}

        if not app.state.madnesses:
            self._madness_list_box.add_widget(CaptionLabel(
                "No active insanity effects.",
                color_hex=T.TEXT_DIM, height_dp=36))
            self._selected_madness = None
        else:
            for idx, m in enumerate(app.state.madnesses):
                name_txt = m.name if m.name else f"{m.kind_label} Effect"
                color    = kind_colors.get(m.kind, T.PURPLE)
                is_sel   = (m is prev)

                dur_str = f"  |  {m.duration}" if m.duration else ""
                item = ListItem(
                    primary=name_txt,
                    secondary=f"{m.kind_label}  |  {m.roll_range}{dur_str}",
                    accent_hex=color,
                    on_tap=lambda widget, entry=m: self._on_madness_tap(widget, entry))

                if is_sel:
                    item.set_selected(True, persist=True)
                    self._sel_mad_widget = item

                self._madness_list_box.add_widget(item)
                self._madness_items[idx] = item

                kind_title = {
                    "short": "SHORT-TERM INSANITY",
                    "long": "LONG-TERM INSANITY",
                    "indefinite": "INDEFINITE INSANITY"}.get(m.kind, "ACTIVE INSANITY")

                detail = MDBoxLayout(
                    orientation="vertical", size_hint_y=None, height=0, opacity=0,
                    padding=[dp(0), dp(4), dp(0), dp(4)])
                inner = DescriptionCard(title=kind_title, color_hex=color)
                dur_detail = f"\nDuration: {m.duration}" if m.duration else ""
                _desc = MDLabel(
                    text=f"{name_txt}  |  {m.roll_range}{dur_detail}\n\n{m.effect}",
                    theme_text_color="Custom", text_color=T.k(T.TEXT),
                    font_style="Body2",
                    size_hint_y=None, adaptive_height=True)
                _desc.bind(width=lambda inst, val: setattr(inst, "text_size", (val, None)))
                inner.add_widget(_desc)
                detail.add_widget(inner)

                self._madness_list_box.add_widget(detail)
                self._madness_details[idx] = detail

                # Restore expanded state if this was the selected entry
                if is_sel:
                    self._expand_panel(detail)

    def highlight_last_madness(self):
        """Flash the most recently added madness entry."""
        app = self._app()
        if not app.state.madnesses:
            return
        last_idx = len(app.state.madnesses) - 1
        item = self._madness_items.get(last_idx)
        if item:
            item.flash()

    def open_madness(self, entry):
        """Navigate to main page, open the detail panel, and flash the entry."""
        self._go_page(0)
        app = self._app()
        for i, m in enumerate(app.state.madnesses):
            if m is entry:
                item = self._madness_items.get(i)
                if item:
                    self._on_madness_tap(item, entry)
                    item.flash()
                return

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
        cur, mx = app.state.current_sanity, app.state.max_sanity
        self._log(f"Sanity loss: -{amt} > {cur}/{mx}")
        self._handle_thresholds(threshs)
        app.refresh_all()
        app.notify_event(
            f"Lost {amt} sanity  ({cur}/{mx})",
            "sanity", T.BLOOD,
            action_cb=lambda: self._go_page(0))
        self._save()

    def _do_recover_input(self, *_):
        amt = self._get_input_amt()
        if amt is None: return
        self._amt_field.text = ""
        app = self._app()
        self._push_undo()
        cleared = app.state.apply_recovery(amt)
        cur, mx = app.state.current_sanity, app.state.max_sanity
        self._log(f"Sanity recovery: +{amt} > {cur}/{mx}")
        self._handle_recovery_thresholds(cleared)
        app.refresh_all()
        app.notify_event(
            f"Recovered {amt} sanity  ({cur}/{mx})",
            "sanity", T.GREEN,
            action_cb=lambda: self._go_page(0))
        self._save()

    # ── Insanity dropdown picker ───────────────────────────────────────────────

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
            caller=anchor_widget, items=items,
            width_mult=4, max_height=dp(300))
        menu.open()
        setattr(self, f"_menu_{kind}", menu)

    def _on_table_select(self, kind: str, roll: str, name: str, effect: str):
        """Store selection as pending and show preview — does NOT add yet."""
        m = getattr(self, f"_menu_{kind}", None)
        if m: m.dismiss()

        # Collapse all other previews first (only one open at a time)
        for k, pair in self._add_preview.items():
            if k != kind:
                d, lbl, pbtn, dtext = pair
                self._collapse_panel(d)
                lbl.text = ""
                pbtn._lbl.text = dtext
                self._pending.pop(k, None)

        self._pending[kind] = (roll, name, effect)

        pair = self._add_preview.get(kind)
        if pair:
            detail, desc_lbl, pick_btn, _ = pair
            desc_lbl.text = f"{roll}. {name}\n\n{effect}"
            pick_btn._lbl.text = f"{roll}. {name}"
            self._expand_panel(detail)

    def _apply_insanity(self, kind: str):
        """Commit the pending selection to the active list."""
        pending = self._pending.pop(kind, None)
        if not pending:
            return
        roll, name, effect = pending
        pair = self._add_preview.get(kind)
        if pair:
            detail, desc_lbl, pick_btn, default_text = pair
            self._collapse_panel(detail)
            desc_lbl.text      = ""
            pick_btn._lbl.text = default_text
        self._add_insanity_now(kind, roll, name, effect)

    def _add_insanity_now(self, kind: str, roll: str, name: str, effect: str):
        app = self._app()
        self._push_undo()
        entry = MadnessEntry(
            kind=kind, roll_range=roll, effect=effect, name=name,
            timestamp=datetime.now().strftime("%H:%M"),
            duration=roll_insanity_duration(kind))
        app.state.madnesses.append(entry)
        label = {"short": "Short-Term", "long": "Long-Term",
                 "indefinite": "Indefinite"}.get(kind, kind)
        self._log(f"Insanity added ({label}): [{roll}] {name}")
        color = {"short": T.M_SHORT, "long": T.M_LONG,
                 "indefinite": T.M_INDEF}.get(kind, T.PURPLE)
        app.refresh_all()
        self._save()
        Clock.schedule_once(
            lambda _, e=entry: app.notify_event(
                f"Insanity: [{roll}] {name}",
                "sanity", color,
                action_cb=lambda _e=e: self.open_madness(_e)
            ), 0.15)

    # ── Select active insanity entry ──────────────────────────────────────────

    def _on_madness_tap(self, widget: ListItem, entry: MadnessEntry):
        # Collapse previously selected panel
        if self._sel_mad_widget and self._sel_mad_widget is not widget:
            self._sel_mad_widget.set_selected(False, persist=False)
            app = self._app()
            for i, m in enumerate(app.state.madnesses):
                if m is self._selected_madness:
                    d = self._madness_details.get(i)
                    if d:
                        self._collapse_panel(d)
                    break

        self._selected_madness = entry
        self._sel_mad_widget   = widget
        widget.set_selected(True, persist=True)

        # Expand this entry's detail panel
        app = self._app()
        for i, m in enumerate(app.state.madnesses):
            if m is entry:
                detail = self._madness_details.get(i)
                if detail:
                    self._expand_panel(detail)
                break

    # ── Remove madness (header trash-can, same pattern as fear list) ───────────

    def _on_remove_madness(self, *_):
        if not self._selected_madness:
            self._snack("Select an insanity first.", T.BORDER)
            return
        app = self._app()
        m = self._selected_madness
        if m not in app.state.madnesses:
            self._selected_madness = None
            self._sel_mad_widget   = None
            return
        self._push_undo()
        name = m.name if m.name else m.kind_label
        app.state.madnesses.remove(m)
        self._log(f"Insanity removed: [{m.roll_range}] {name}")
        self._selected_madness = None
        self._sel_mad_widget   = None
        app.refresh_all()
        self._save()

    # ── Threshold handling ────────────────────────────────────────────────────

    def _handle_recovery_thresholds(self, cleared):
        """When sanity recovers past a threshold, remove the most recent matching madness."""
        if not cleared:
            return
        app = self._app()
        events = []
        for label, _c, kind in cleared:
            if kind == "zero":
                continue
            color = {"short": T.M_SHORT, "long": T.M_LONG,
                     "indefinite": T.M_INDEF}.get(kind, T.PURPLE)
            existing = [m for m in reversed(app.state.madnesses) if m.kind == kind]
            if existing:
                cured = existing[0]
                app.state.madnesses.remove(cured)
                cured_name = cured.name if cured.name else cured.kind_label
                self._log(f"THRESHOLD CLEARED: {label} — {cured_name} cured")
                events.append((color, cured_name))
            else:
                self._log(f"THRESHOLD CLEARED: {label} — no matching insanity to cure")
        if events:
            app.refresh_all()
            for color, cured_name in events:
                Clock.schedule_once(
                    lambda _, cn=cured_name, c=color: app.notify_event(
                        f"Insanity cured: {cn}", "sanity", c
                    ), 0.3)

    def _handle_thresholds(self, threshs):
        app = self._app()
        events = []   # list of (color, entry_or_None, cured_name_or_None)
        for label, kind in threshs:
            if kind == "zero":
                self._log(f"WARNING: {label}")
                app.notify_event(label, "sanity", T.BLOOD_DK)
                continue
            color = {"short": T.M_SHORT, "long": T.M_LONG,
                     "indefinite": T.M_INDEF}.get(kind, T.PURPLE)
            # Re-crossing: cure last insanity of same kind instead of adding
            existing = [m for m in reversed(app.state.madnesses) if m.kind == kind]
            if existing:
                cured = existing[0]
                app.state.madnesses.remove(cured)
                cured_name = cured.name if cured.name else cured.kind_label
                self._log(f"THRESHOLD re-crossed: {label} — cured {cured_name}")
                events.append((color, None, cured_name))
            else:
                m = app.state.add_madness(kind)
                self._log(
                    f"THRESHOLD: {label} > {m.kind_label} insanity: "
                    f"[{m.roll_range}] {m.name} -- {m.effect[:50]}")
                events.append((color, m, None))
        if threshs:
            app.refresh_all()
            for color, entry, cured_name in events:
                if cured_name:
                    Clock.schedule_once(
                        lambda _, cn=cured_name, c=color: app.notify_event(
                            f"Threshold cured: {cn}", "sanity", c
                        ), 0.3)
                else:
                    Clock.schedule_once(
                        lambda _, e=entry, c=color: app.notify_event(
                            f"Insanity: [{e.roll_range}] {e.name}",
                            "sanity", c,
                            action_cb=lambda ee=e: self.open_madness(ee)
                        ), 0.3)
