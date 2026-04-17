"""
Tab 2: Sanity & Insanity  (V2 redesign)

Two-page swipeable layout:
  Page 0 — Sanity & Insanity: sanity card, active insanity list, rules
  Page 1 — Add Insanity: D20 dropdown pickers, preview + Apply button

Swipe left/right to move between pages.
"""
from __future__ import annotations

from datetime import datetime

from kivy.animation import Animation
from kivy.app import App
from kivy.clock import Clock
from kivy.graphics import Color
from kivy.metrics import dp
from kivy.uix.anchorlayout import AnchorLayout
from kivy.uix.floatlayout import FloatLayout
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
    BorderCard, Divider,
    SectionLabel, CaptionLabel,
    ExpandingEffectCard, ExpandableSection, PickerListItem,
    themed_field, SwipePageIndicator,
    populate_rules_section
)
import theme as T


class SanityTab(MDBoxLayout):

    def __init__(self, **kwargs):
        kwargs.setdefault("orientation", "vertical")
        super().__init__(**kwargs)

        # Selection tracked by OBJECT identity (like fear tab tracks by name)
        self._selected_madness: MadnessEntry | None = None
        self._active_card: ExpandingEffectCard | None = None
        self._madness_items: dict = {}    # idx -> ExpandingEffectCard

        # Add-page: kind -> (detail MDBoxLayout, desc MDLabel, apply_btn)
        self._add_preview: dict = {}
        # Add-page pending selection: kind -> (roll, name, effect)
        self._pending: dict = {}

        # ── Page state ──────────────────────────────────────────────────────
        self._page = 0  # 0 = Sanity & Insanity, 1 = Add Insanity

        self.add_widget(self._build_page_indicator())


        # ── Page 0 (Sanity & Insanity) ───────────────────────────────────────
        self._sv0 = ScrollView(do_scroll_x=False, size_hint=(None, None))
        p0 = MDBoxLayout(
            orientation="vertical",
            padding=dp(10), spacing=dp(8),
            size_hint_y=None, adaptive_height=True)
        p0.add_widget(self._build_sanity_card())
        p0.add_widget(self._build_active_madness_card())
        p0.add_widget(self._build_rules_panel())
        self._sv0.add_widget(p0)

        # ── Page 1 (Add Insanity) ────────────────────────────────────────────
        self._sv1 = ScrollView(do_scroll_x=False, size_hint=(None, None))
        p1 = MDBoxLayout(
            orientation="vertical",
            padding=dp(10), spacing=dp(8),
            size_hint_y=None, adaptive_height=True)
        p1.add_widget(self._build_madness_add_card())
        p1.add_widget(self._build_rules_panel())
        self._sv1.add_widget(p1)

        self._content_area = FloatLayout()
        self._content_area.bind(
            size=lambda *_: Clock.schedule_once(lambda dt: self._update_sv_positions()),
            pos=lambda *_: Clock.schedule_once(lambda dt: self._update_sv_positions()),
        )
        self._content_area.add_widget(self._sv0)
        self._content_area.add_widget(self._sv1)
        self.add_widget(self._content_area)
        self._update_indicator()

    # ── Page indicator ───────────────────────────────────────────────────────

    def _build_page_indicator(self) -> MDBoxLayout:
        self._page_indicator = SwipePageIndicator(
            "Sanity & Insanity", "Add Insanity",
            left_hex=T.PURPLE, right_hex=T.PURPLE_LT, bg_hex=T.PURPLE)
        return self._page_indicator

    def _update_indicator(self, progress: float | None = None):
        self._page_indicator.set_progress(float(self._page) if progress is None else progress)

    def _reset_add_page(self):
        """Reset all add-page picker cards to default."""
        self._pending.clear()
        for entry in self._add_preview.values():
            entry["picker"].show_placeholder(entry["default_text"], animate=False)

    def _update_sv_positions(self, extra_offset: float = 0):
        w = self._content_area.width
        h = self._content_area.height
        if w == 0 or h == 0:
            return
        base = -self._page * w + extra_offset
        self._sv0.size = (w, h)
        self._sv1.size = (w, h)
        self._sv0.pos = (self._content_area.x + base, self._content_area.y)
        self._sv1.pos = (self._content_area.x + base + w, self._content_area.y)
        self._update_indicator(max(0.0, min(1.0, -base / w)))

    def _animate_to_page(self, page: int):
        if page == self._page:
            return
        if self._page == 1:
            self._reset_add_page()
        self._page = page
        w = self._content_area.width
        target_base = -page * w
        Animation.cancel_all(self._sv0)
        Animation.cancel_all(self._sv1)
        Animation.cancel_all(self._page_indicator, 'progress')
        anim0 = Animation(x=self._content_area.x + target_base,
                          duration=0.25, t='out_cubic')
        anim1 = Animation(x=self._content_area.x + target_base + w,
                          duration=0.25, t='out_cubic')
        Animation(progress=page, duration=0.25, t='out_cubic').start(self._page_indicator)
        anim0.start(self._sv0)
        anim1.start(self._sv1)

    def _animate_snap_back(self):
        w = self._content_area.width
        base = -self._page * w
        Animation.cancel_all(self._sv0)
        Animation.cancel_all(self._sv1)
        Animation.cancel_all(self._page_indicator, 'progress')
        anim0 = Animation(x=self._content_area.x + base,
                          duration=0.2, t='out_cubic')
        anim1 = Animation(x=self._content_area.x + base + w,
                          duration=0.2, t='out_cubic')
        Animation(progress=self._page, duration=0.2, t='out_cubic').start(self._page_indicator)
        anim0.start(self._sv0)
        anim1.start(self._sv1)

    def _go_page(self, page: int):
        self._animate_to_page(page)

    # ── Swipe detection ──────────────────────────────────────────────────────

    def on_touch_down(self, touch):
        if self.collide_point(*touch.pos):
            touch.ud['sanity_swipe_start'] = (touch.x, touch.y)
            touch.ud['sanity_swiping'] = False
        return super().on_touch_down(touch)

    def on_touch_move(self, touch):
        if touch.grab_current is self:
            start = touch.ud.get('sanity_swipe_start')
            if start:
                dx = touch.x - start[0]
                w = self._content_area.width
                if self._page == 0:
                    offset = max(-w, min(0.0, dx))
                else:
                    offset = max(0.0, min(w, dx))
                self._update_sv_positions(offset)
            return True
        start = touch.ud.get('sanity_swipe_start')
        if (start and not touch.ud.get('sanity_swiping')
                and self.collide_point(*touch.pos)):
            dx = touch.x - start[0]
            dy = touch.y - start[1]
            if abs(dx) > dp(10) and abs(dx) > abs(dy) * 1.5:
                touch.ud['sanity_swiping'] = True
                touch.grab(self)
                Animation.cancel_all(self._sv0)
                Animation.cancel_all(self._sv1)
                Animation.cancel_all(self._page_indicator, 'progress')
                w = self._content_area.width
                if self._page == 0:
                    offset = max(-w, min(0.0, dx))
                else:
                    offset = max(0.0, min(w, dx))
                self._update_sv_positions(offset)
                return True
        return super().on_touch_move(touch)

    def on_touch_up(self, touch):
        if touch.grab_current is self:
            touch.ungrab(self)
            start = touch.ud.get('sanity_swipe_start')
            if start:
                dx = touch.x - start[0]
                dy = touch.y - start[1]
                if abs(dx) > dp(50) and abs(dx) > abs(dy) * 1.5:
                    if dx < 0 and self._page == 0:
                        self._animate_to_page(1)
                    elif dx > 0 and self._page == 1:
                        self._animate_to_page(0)
                    else:
                        self._animate_snap_back()
                else:
                    self._animate_snap_back()
            return True
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

        rows = [
            ("SHORT-TERM", "1d10 minutes",    T.M_SHORT, "short"),
            ("LONG-TERM",  "1d10 × 10 hours", T.M_LONG,  "long"),
            ("INDEFINITE", "Until cured",      T.M_INDEF, "indefinite"),
        ]
        for i, (title, duration, color, kind) in enumerate(rows):
            default_text = f"Pick a {title.lower()} insanity"

            row_box = MDBoxLayout(
                orientation="vertical",
                adaptive_height=True,
                spacing=dp(6))
            tr = MDBoxLayout(size_hint_y=None, height=dp(22), spacing=dp(8))
            tr.add_widget(MDLabel(
                text=title, bold=True, font_style="Caption",
                theme_text_color="Custom", text_color=T.k(color)))
            tr.add_widget(MDLabel(
                text=f"({duration})", font_style="Overline",
                theme_text_color="Custom", text_color=T.k(T.TEXT_DIM)))
            row_box.add_widget(tr)

            picker = PickerListItem(
                on_tap=lambda wid, k=kind: self._open_madness_menu(k, wid),
                accent_hex=color,
            )
            picker.title_text = default_text
            picker.is_placeholder = True
            control_row = MDBoxLayout(
                orientation="horizontal",
                size_hint_y=None,
                spacing=dp(8),
            )
            control_row.bind(minimum_height=lambda inst, val: setattr(inst, "height", val))
            control_row.add_widget(picker)
            apply_slot = AnchorLayout(
                anchor_x="right",
                anchor_y="center",
                size_hint_x=None,
                size_hint_y=None,
                width=dp(88),
            )
            picker.bind(height=lambda inst, val, slot=apply_slot: setattr(slot, "height", val))
            apply_slot.height = picker.height
            apply_slot.add_widget(MDRaisedButton(
                text="APPLY",
                md_bg_color=T.k(color),
                size_hint_y=None, height=dp(44),
                size_hint_x=None, width=dp(80),
                on_release=lambda *_, k=kind: self._apply_insanity(k)))
            control_row.add_widget(apply_slot)
            row_box.add_widget(control_row)
            card.add_widget(row_box)
            self._add_preview[kind] = {
                "picker": picker,
                "default_text": default_text,
            }

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
        self._rules_sec = ExpandableSection(
            "INSANITY RULES",
            accent_hex=T.PURPLE_LT,
        )
        populate_rules_section(self._rules_sec, MADNESS_RULES_TEXT, T.PURPLE_LT)
        wrapper.add_widget(self._rules_sec)
        return wrapper

    def collapse_all(self):
        """Close all expandable panels — called on tab enter/leave."""
        if hasattr(self, "_rules_sec"):
            self._rules_sec.close()
        for card in self._madness_items.values():
            card.set_open(False, animate=False)
        self._active_card      = None
        self._selected_madness = None

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _app(self): return App.get_running_app()

    def _madness_summary(self, kind_label: str, roll: str, duration: str = "") -> str:
        parts = [kind_label, f"Roll: {roll}"]
        if duration:
            parts.append(duration)
        return " | ".join(parts)

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

    def _expand_panel(self, detail: MDBoxLayout, animate: bool = True):
        """Expand a plain MDBoxLayout preview panel (used by Add Insanity page)."""
        Animation.cancel_all(detail, 'height', 'opacity')
        detail.size_hint_y = None
        if not animate:
            detail.opacity = 1
            Clock.schedule_once(lambda dt, d=detail: setattr(d, 'height', d.minimum_height))
            return
        detail.height  = 0
        detail.opacity = 0
        Clock.schedule_once(
            lambda *_: Animation(
                height=detail.minimum_height or dp(80), opacity=1,
                duration=0.25, t='out_cubic').start(detail))

    def _collapse_panel(self, detail: MDBoxLayout):
        """Collapse a plain MDBoxLayout preview panel (used by Add Insanity page)."""
        Animation.cancel_all(detail, 'height', 'opacity')
        Animation(height=0, opacity=0, duration=0.2, t='in_cubic').start(detail)

    # ── Public refresh ─────────────────────────────────────────────────────────

    def refresh(self):
        app = self._app()

        # Preserve selection across rebuild (track by object identity)
        prev = self._selected_madness
        self._active_card = None
        self._madness_list_box.clear_widgets()
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

                card = ExpandingEffectCard(
                    on_tap=lambda w, entry=m: self._on_madness_tap(w, entry))
                card.title_text    = name_txt
                card.subtitle_text = self._madness_summary(m.kind_label, m.roll_range, m.duration)
                card.detail_body   = m.effect
                card.accent_rgba   = list(T.k(color))

                self._madness_list_box.add_widget(card)
                self._madness_items[idx] = card

                # Restore expanded state if this was the selected entry
                if is_sel:
                    card.set_open(True, animate=False)
                    self._active_card = card

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
                card = self._madness_items.get(i)
                if card:
                    if self._active_card is not card:
                        self._on_madness_tap(card, entry)
                    card.flash()
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
            f"Sanity: \u2212{amt} ({cur}/{mx})",
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
            f"Sanity: +{amt} ({cur}/{mx})",
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

        # Collapse all other pickers first (only one open at a time)
        for k, pair in self._add_preview.items():
            if k != kind:
                pair["picker"].show_placeholder(pair["default_text"], animate=True)
                self._pending.pop(k, None)

        duration = roll_insanity_duration(kind)
        self._pending[kind] = (roll, name, effect, duration)

        pair = self._add_preview.get(kind)
        if pair:
            kind_label = {"short": "Short-Term", "long": "Long-Term",
                          "indefinite": "Indefinite"}.get(kind, kind)
            summary = self._madness_summary(kind_label, roll, duration)
            pair["picker"].title_text = f"{roll}. {name}"
            pair["picker"].subtitle_text = summary
            pair["picker"].detail_body = effect
            pair["picker"].is_placeholder = False
            pair["picker"].set_open(True, animate=True)

    def _apply_insanity(self, kind: str):
        """Commit the pending selection to the active list."""
        pending = self._pending.pop(kind, None)
        if not pending:
            return
        roll, name, effect, duration = pending
        pair = self._add_preview.get(kind)
        if pair:
            pair["picker"].show_placeholder(pair["default_text"], animate=False)
        self._add_insanity_now(kind, roll, name, effect, duration)

    def _add_insanity_now(self, kind: str, roll: str, name: str, effect: str, duration: str):
        app = self._app()
        self._push_undo()
        entry = MadnessEntry(
            kind=kind, roll_range=roll, effect=effect, name=name,
            timestamp=datetime.now().strftime("%H:%M"),
            duration=duration)
        app.state.madnesses.append(entry)
        label = {"short": "Short-Term", "long": "Long-Term",
                 "indefinite": "Indefinite"}.get(kind, kind)
        self._log(f"Insanity added ({label}): [{roll}] {name}")
        color = {"short": T.M_SHORT, "long": T.M_LONG,
                 "indefinite": T.M_INDEF}.get(kind, T.PURPLE)
        app.refresh_all()
        self._save()
        Clock.schedule_once(
            lambda _, e=entry, lbl=label: app.notify_event(
                f"{lbl} Insanity: {name}",
                "sanity", color,
                action_cb=lambda _e=e: self.open_madness(_e)
            ), 0.15)

    # ── Select active insanity entry ──────────────────────────────────────────

    def _on_madness_tap(self, card: ExpandingEffectCard, entry: MadnessEntry):
        # Toggle: tapping the open card closes it
        if self._active_card is card:
            card.set_open(False)
            self._active_card      = None
            self._selected_madness = None
            return

        # Close the previously open card
        if self._active_card:
            self._active_card.set_open(False)

        card.set_open(True)
        self._active_card      = card
        self._selected_madness = entry

    # ── Remove madness (header trash-can, same pattern as fear list) ───────────

    def _on_remove_madness(self, *_):
        if not self._selected_madness:
            self._snack("Select an insanity first.", T.BORDER)
            return
        app = self._app()
        m = self._selected_madness
        if m not in app.state.madnesses:
            self._selected_madness = None
            self._active_card      = None
            return
        self._push_undo()
        name = m.name if m.name else m.kind_label
        app.state.madnesses.remove(m)
        self._log(f"Insanity removed: [{m.roll_range}] {name}")
        self._selected_madness = None
        self._active_card      = None
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
                app.notify_event(label, "sanity", T.BLOOD)
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
                events.append((color, None, cured_name, label))
            else:
                m = app.state.add_madness(kind)
                self._log(
                    f"THRESHOLD: {label} > {m.kind_label} insanity: "
                    f"[{m.roll_range}] {m.name} -- {m.effect[:50]}")
                events.append((color, m, None, label))
        if threshs:
            app.refresh_all()
            for color, entry, cured_name, lbl in events:
                if cured_name:
                    Clock.schedule_once(
                        lambda _, cn=cured_name, c=color: app.notify_event(
                            f"Threshold cured: {cn}", "sanity", c
                        ), 0.3)
                else:
                    Clock.schedule_once(
                        lambda _, e=entry, c=color: app.notify_event(
                            f"{e.kind_label} Insanity: {e.name}",
                            "sanity", c,
                            action_cb=lambda ee=e: self.open_madness(ee)
                        ), 0.3)
