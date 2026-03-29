"""
Tab 3: Wounds  (V2 redesign)

Two-page swipeable layout:
  Page 0 â€” Encounter & Wounds: encounter card, wound lists, rules
  Page 1 â€” Add Wound: minor/major picker, preview + Apply button

Swipe left/right to move between pages.
"""
from __future__ import annotations

from kivy.animation import Animation
from kivy.app import App
from kivy.clock import Clock
from kivy.graphics import Color, Rectangle
from kivy.metrics import dp
from kivy.uix.scrollview import ScrollView
from kivy.uix.widget import Widget

from kivymd.uix.boxlayout import MDBoxLayout
from kivymd.uix.button import MDFlatButton, MDIconButton, MDRaisedButton
from kivymd.uix.label import MDLabel
from kivymd.uix.menu import MDDropdownMenu
from kivymd.uix.snackbar import MDSnackbar

from models import (
    WoundEncPhase, WoundEncounterState, WoundEntry,
    MINOR_WOUND_TABLE, MAJOR_WOUND_TABLE,
    roll_d, safe_int, roll_random_wound, clamp, WOUND_RULES_TEXT
)
from ui_utils import (
    BorderCard, AccentCard, DescriptionCard, Divider, HopeButton,
    SectionLabel, CaptionLabel,
    ListItem, ExpandableSection, themed_field, PickerButton, PageDot,
    populate_rules_section
)
import theme as T



class WoundsTab(MDBoxLayout):

    def __init__(self, **kwargs):
        kwargs.setdefault("orientation", "vertical")
        super().__init__(**kwargs)

        self._enc = WoundEncounterState()

        # Selection tracked by OBJECT identity (like fear tab)
        self._sel_minor: WoundEntry | None = None
        self._sel_minor_widget: ListItem | None = None
        self._sel_major: WoundEntry | None = None
        self._sel_major_widget: ListItem | None = None
        self._minor_details: dict = {}   # idx -> detail MDBoxLayout
        self._major_details: dict = {}   # idx -> detail MDBoxLayout
        self._minor_items: dict = {}   # idx -> ListItem
        self._major_items: dict = {}   # idx -> ListItem

        # Add-page: severity -> (detail MDBoxLayout, desc MDLabel, apply_btn)
        self._add_preview: dict = {}
        # Add-page pending: severity -> (roll, desc, effect)
        self._pending_wound: dict = {}

        # â”€â”€ Page state â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
        self._page = 0  # 0 = Encounter & Wounds, 1 = Add Wound

        self.add_widget(self._build_page_indicator())

        self._content_area = MDBoxLayout(orientation="vertical")
        self.add_widget(self._content_area)

        # â”€â”€ Page 0 (Encounter & Wounds) â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
        self._sv0 = ScrollView(do_scroll_x=False)
        p0 = MDBoxLayout(
            orientation="vertical",
            padding=dp(10), spacing=dp(8),
            size_hint_y=None, adaptive_height=True)
        p0.add_widget(self._build_encounter_card())
        p0.add_widget(self._build_active_wounds_card())
        p0.add_widget(self._build_rules_panel())
        self._sv0.add_widget(p0)

        # â”€â”€ Page 1 (Add Wound) â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
        self._sv1 = ScrollView(do_scroll_x=False)
        p1 = MDBoxLayout(
            orientation="vertical",
            padding=dp(10), spacing=dp(8),
            size_hint_y=None, adaptive_height=True)
        p1.add_widget(self._build_add_wound_card())
        p1.add_widget(self._build_rules_panel())
        self._sv1.add_widget(p1)

        self._content_area.add_widget(self._sv0)
        self._update_indicator()

    # â”€â”€ Page indicator â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

    def _build_page_indicator(self) -> MDBoxLayout:
        row = MDBoxLayout(
            size_hint_y=None, height=dp(26),
            spacing=dp(4), padding=[dp(10), dp(2), dp(10), dp(2)])
        with row.canvas.before:
            Color(*T.k(T.BLOOD, 0.12))
            self._ind_bg = Rectangle()
        row.bind(pos=lambda w, _: setattr(self._ind_bg, 'pos', w.pos),
                 size=lambda w, _: setattr(self._ind_bg, 'size', w.size))

        self._ind_lbl0 = MDLabel(
            text="Wounds", halign="right",
            theme_text_color="Custom", text_color=T.k(T.BLOOD),
            font_style="Caption", bold=True, size_hint_x=0.44)
        self._dot0 = PageDot(color_hex=T.BLOOD)
        self._dot1 = PageDot(color_hex=T.TEXT_DIM)
        self._ind_lbl1 = MDLabel(
            text="Add Wound", halign="left",
            theme_text_color="Custom", text_color=T.k(T.TEXT_DIM),
            font_style="Caption", bold=False, size_hint_x=0.44)

        row.add_widget(self._ind_lbl0)
        row.add_widget(self._dot0)
        row.add_widget(self._dot1)
        row.add_widget(self._ind_lbl1)
        return row

    def _update_indicator(self):
        if self._page == 0:
            self._dot0.set_color(T.BLOOD)
            self._dot1.set_color(T.TEXT_DIM)
            self._ind_lbl0.bold       = True
            self._ind_lbl0.text_color = T.k(T.BLOOD)
            self._ind_lbl1.bold       = False
            self._ind_lbl1.text_color = T.k(T.TEXT_DIM)
        else:
            self._dot0.set_color(T.TEXT_DIM)
            self._dot1.set_color(T.BLOOD_LT)
            self._ind_lbl0.bold       = False
            self._ind_lbl0.text_color = T.k(T.TEXT_DIM)
            self._ind_lbl1.bold       = True
            self._ind_lbl1.text_color = T.k(T.BLOOD_LT)

    def _reset_add_page(self):
        """Reset all add-page picker buttons and preview panels to default."""
        self._pending_wound.clear()
        for severity, pair in self._add_preview.items():
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
        self._clear_wound_details()
        self._content_area.clear_widgets()
        self._content_area.add_widget(self._sv0 if page == 0 else self._sv1)
        self._update_indicator()

    # â”€â”€ Swipe detection â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

    def on_touch_down(self, touch):
        if self.collide_point(*touch.pos):
            touch.ud['wounds_swipe_start'] = (touch.x, touch.y)
        return super().on_touch_down(touch)

    def on_touch_up(self, touch):
        start = touch.ud.get('wounds_swipe_start')
        if start:
            dx = touch.x - start[0]
            dy = touch.y - start[1]
            if abs(dx) > dp(50) and abs(dx) > abs(dy) * 1.5:
                if dx < 0:
                    self._go_page(1)
                elif dx > 0:
                    self._go_page(0)
        return super().on_touch_up(touch)

    # â”€â”€ Build: Encounter Card â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

    def _build_encounter_card(self) -> BorderCard:
        card = BorderCard(border_hex=T.BLOOD)
        card.add_widget(SectionLabel("WOUND ENCOUNTER", color_hex=T.BLOOD))

        field_row = MDBoxLayout(spacing=dp(8), size_hint_y=None, height=dp(52))
        self._wdc_field = themed_field(
            hint_text="DC (default 10)", text="10",
            accent_hex=T.BLOOD, input_filter="int", size_hint_x=0.5)
        self._dmg_field = themed_field(
            hint_text="Damage taken", text="0",
            accent_hex=T.BLOOD, input_filter="int", size_hint_x=0.5)
        self._dmg_field.bind(text=self._on_dmg_text)
        field_row.add_widget(self._wdc_field)
        field_row.add_widget(self._dmg_field)
        card.add_widget(field_row)

        self._wenc_btn = MDRaisedButton(
            text="ENCOUNTER",
            md_bg_color=T.k(T.BLOOD),
            size_hint_x=1.0, size_hint_y=None, height=dp(48),
            on_release=self._on_wound_encounter)
        card.add_widget(self._wenc_btn)

        self._w_roll_panel = MDBoxLayout(
            orientation="vertical", spacing=dp(4),
            size_hint_y=None, height=0, opacity=0)

        self._w_roll_lbl = MDLabel(
            text="", theme_text_color="Custom",
            text_color=T.k(T.TEXT_DIM), font_style="Caption",
            size_hint_y=None, height=dp(20))
        self._w_roll_big = MDLabel(
            text="", bold=True,
            theme_text_color="Custom", text_color=T.k(T.TEXT_BRIGHT),
            font_style="H5", size_hint_y=None, height=dp(48))
        self._w_roll_panel.add_widget(self._w_roll_lbl)
        self._w_roll_panel.add_widget(self._w_roll_big)

        # Hope row â€” centred, hidden until a fail result with active hope
        self._w_hope_row = MDBoxLayout(
            size_hint_y=None, height=0, opacity=0,
            padding=[0, dp(4), 0, dp(4)])
        self._w_hope_btn = HopeButton(on_use=self._use_hope)
        self._w_hope_row.add_widget(self._w_hope_btn)
        self._w_hope_row.add_widget(Widget())
        self._w_roll_panel.add_widget(self._w_hope_row)

        wr1 = MDBoxLayout(spacing=dp(4), size_hint_y=None, height=dp(44))
        self._wpass5_btn = MDRaisedButton(
            text="Pass 5+", md_bg_color=T.k(T.GREEN_LT),
            size_hint_x=0.5, disabled=True,
            on_release=lambda *_: self._resolve("pass5"))
        self._wpass_btn = MDRaisedButton(
            text="Pass", md_bg_color=T.k(T.GREEN),
            size_hint_x=0.5, disabled=True,
            on_release=lambda *_: self._resolve("pass"))
        wr1.add_widget(self._wpass5_btn)
        wr1.add_widget(self._wpass_btn)
        self._w_roll_panel.add_widget(wr1)

        wr2 = MDBoxLayout(spacing=dp(4), size_hint_y=None, height=dp(44))
        self._wfail_btn = MDRaisedButton(
            text="Fail", md_bg_color=T.k(T.RED),
            size_hint_x=0.5, disabled=True,
            on_release=lambda *_: self._resolve("fail"))
        self._wfail5_btn = MDRaisedButton(
            text="Fail 5+", md_bg_color=T.k(T.BLOOD),
            size_hint_x=0.5, disabled=True,
            on_release=lambda *_: self._resolve("fail5"))
        wr2.add_widget(self._wfail_btn)
        wr2.add_widget(self._wfail5_btn)
        self._w_roll_panel.add_widget(wr2)

        card.add_widget(self._w_roll_panel)
        return card

    # â”€â”€ Build: Active Wound Card â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

    def _build_active_wounds_card(self) -> BorderCard:
        card = BorderCard(border_hex=T.BLOOD)

        hdr = MDBoxLayout(size_hint_y=None, height=dp(32), spacing=dp(8))
        hdr.add_widget(SectionLabel("ACTIVE WOUNDS", color_hex=T.BLOOD))
        hdr.add_widget(Widget())
        hdr.add_widget(MDIconButton(
            icon="trash-can-outline",
            theme_icon_color="Custom", icon_color=T.k(T.RED),
            size_hint_x=None, width=dp(40),
            on_release=self._on_remove_wound))
        card.add_widget(hdr)

        self._minor_list_box = MDBoxLayout(
            orientation="vertical", adaptive_height=True, spacing=dp(2))
        card.add_widget(self._minor_list_box)

        self._major_list_box = MDBoxLayout(
            orientation="vertical", adaptive_height=True, spacing=dp(2))
        card.add_widget(self._major_list_box)
        return card

    # â”€â”€ Build: Add Wound Card (Page 1) â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

    def _build_add_wound_card(self) -> BorderCard:
        card = BorderCard(border_hex=T.BLOOD)
        card.add_widget(SectionLabel("ADD WOUND", color_hex=T.BLOOD))

        rows = [
            ("MINOR WOUND", "1d4 Sanity loss", T.WOUND_MIN, "minor"),
            ("MAJOR WOUND", "2d4 Sanity loss", T.BLOOD, "major"),
        ]
        for i, (title, subtitle, color, severity) in enumerate(rows):
            default_text = f"PICK {title}"

            # AccentCard: title row + [PickerButton | Apply button]
            inner = AccentCard(accent_hex=color)
            tr = MDBoxLayout(size_hint_y=None, height=dp(22), spacing=dp(8))
            tr.add_widget(MDLabel(
                text=title, bold=True, font_style="Caption",
                theme_text_color="Custom", text_color=T.k(color)))
            tr.add_widget(MDLabel(
                text=f"({subtitle})", font_style="Overline",
                theme_text_color="Custom", text_color=T.k(T.TEXT_DIM)))
            inner.add_widget(tr)

            btn_row = MDBoxLayout(
                size_hint_y=None, height=dp(48), spacing=dp(6))
            pick_btn = PickerButton(
                text=default_text,
                color_hex=color,
                on_press=lambda btn, s=severity: self._open_wound_menu(s, btn),
                size_hint_x=1.0)
            btn_row.add_widget(pick_btn)
            btn_row.add_widget(MDRaisedButton(
                text="APPLY",
                md_bg_color=T.k(color),
                size_hint_x=None, width=dp(80),
                on_release=lambda *_, s=severity: self._apply_wound(s)))
            inner.add_widget(btn_row)
            card.add_widget(inner)

            # Preview panel â€” added directly to card, BENEATH the AccentCard
            detail = MDBoxLayout(
                orientation="vertical", size_hint_y=None, height=0, opacity=0,
                padding=[dp(0), dp(4), dp(0), dp(4)])
            desc_card = DescriptionCard(title=title, color_hex=color)
            desc_lbl = MDLabel(
                text="", theme_text_color="Custom", text_color=T.k(T.TEXT),
                font_style="Body2", size_hint_y=None, adaptive_height=True)
            desc_lbl.bind(width=lambda inst, val: setattr(inst, "text_size", (val, None)))
            desc_card.add_widget(desc_lbl)
            detail.add_widget(desc_card)
            card.add_widget(detail)
            # Store (detail, desc_lbl, pick_btn, default_text) for later update
            self._add_preview[severity] = (detail, desc_lbl, pick_btn, default_text)

            if i < len(rows) - 1:
                card.add_widget(Divider(color_hex=T.BORDER))

        return card

    def _open_wound_menu(self, severity: str, anchor):
        table = MINOR_WOUND_TABLE if severity == "minor" else MAJOR_WOUND_TABLE
        items = [
            {
                "text": f"{roll}. {desc}",
                "viewclass": "OneLineListItem",
                "on_release": (
                    lambda r=roll, d=desc, e=effect, s=severity:
                    self._on_wound_select(s, r, d, e)
                ),
            }
            for roll, desc, effect in table
        ]
        menu = MDDropdownMenu(caller=anchor, items=items,
                              width_mult=4, max_height=dp(300))
        menu.open()
        setattr(self, f"_menu_{severity}", menu)

    def _on_wound_select(self, severity: str, roll, desc: str, effect: str):
        """Store selection as pending and show preview â€” does NOT add yet."""
        m = getattr(self, f"_menu_{severity}", None)
        if m: m.dismiss()

        # Collapse all other previews first (only one open at a time)
        for s, pair in self._add_preview.items():
            if s != severity:
                d, lbl, pbtn, dtext = pair
                self._collapse_panel(d)
                lbl.text = ""
                pbtn._lbl.text = dtext
                self._pending_wound.pop(s, None)

        self._pending_wound[severity] = (roll, desc, effect)

        pair = self._add_preview.get(severity)
        if pair:
            detail, desc_lbl, pick_btn, _ = pair
            desc_lbl.text = self._wound_roll_preview_text(severity, roll)
            pick_btn._lbl.text = f"{roll}. {desc}"
            self._expand_panel(detail)

    def _apply_wound(self, severity: str):
        """Commit the pending selection."""
        pending = self._pending_wound.pop(severity, None)
        if not pending:
            return
        roll, desc, effect = pending
        pair = self._add_preview.get(severity)
        if pair:
            detail, desc_lbl, pick_btn, default_text = pair
            self._collapse_panel(detail)
            desc_lbl.text      = ""
            pick_btn._lbl.text = default_text
        self._add_wound(severity, desc, effect)

    def _build_rules_panel(self) -> BorderCard:
        wrapper = BorderCard(border_hex=T.BLOOD)
        sec = ExpandableSection(
            "WOUND RULES",
            accent_hex=T.BLOOD_LT,
        )
        populate_rules_section(sec, WOUND_RULES_TEXT, T.BLOOD_LT)
        wrapper.add_widget(sec)
        return wrapper

    def _wound_roll_preview_text(self, severity: str, roll) -> str:
        label = "Minor Wound" if severity == "minor" else "Major Wound"
        sanity_loss = "1d4 Sanity loss" if severity == "minor" else "2d4 Sanity loss"
        return f"{label} | Roll: {roll} | {sanity_loss}"

    # â”€â”€ Internal helpers â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

    def _on_dmg_text(self, _, value):
        try:
            dmg = max(0, int(value.strip()))
            self._wdc_field.text = str(max(10, dmg // 2))
        except (ValueError, AttributeError):
            pass

    def _app(self): return App.get_running_app()

    def _push_undo(self):
        app = self._app(); app.undo_stack.push(app.state, app.fm)

    def _save(self):
        app = self._app()
        app.save_manager.save(app.state, app.fm, app.char_name, app.enc_history)

    def _log(self, msg):
        app = self._app(); app.enc_history.append(msg)
        if hasattr(app, "session_log"): app.session_log.add_entry(msg)

    def _snack(self, msg, color=T.BG_CARD):
        MDSnackbar(
            MDLabel(text=msg, theme_text_color="Custom", text_color=(1, 1, 1, 1)),
            md_bg_color=T.k(color), duration=2.5
        ).open()

    def _sync_panel_height(self, panel):
        """Set panel height to its content height â€” called via Clock after layout."""
        panel.height = panel.minimum_height

    def _expand_panel(self, detail: MDBoxLayout):
        """Expand a detail panel â€” exact same pattern as Fear Severity/Desens."""
        detail.size_hint_y = None
        detail.opacity     = 1
        Clock.schedule_once(lambda dt, d=detail: self._sync_panel_height(d))

    def _collapse_panel(self, detail: MDBoxLayout):
        """Collapse a detail panel â€” exact same pattern as Fear Severity/Desens."""
        detail.size_hint_y = None
        detail.height      = 0
        detail.opacity     = 0

    def _kind_label(self, kind: str) -> str:
        return {
            "short": "Short-Term",
            "long": "Long-Term",
            "indefinite": "Indefinite",
        }.get(kind, "Unknown")

    def _kind_color(self, kind: str) -> str:
        return {
            "short": T.M_SHORT,
            "long": T.M_LONG,
            "indefinite": T.M_INDEF,
        }.get(kind, T.PURPLE_LT)

    def _threshold_suffix_for_notif(self, threshs, pre_kind_counts) -> str:
        suffix = ""
        for _, kind in threshs:
            if kind == "zero":
                continue
            c = self._kind_color(kind)
            if pre_kind_counts.get(kind, 0) > 0 and kind != "indefinite":
                suffix = f" [color={c}][font=Symbols]\u2192[/font] Cured {self._kind_label(kind)} Insanity[/color]"
            elif pre_kind_counts.get(kind, 0) > 0 and kind == "indefinite":
                continue
            else:
                suffix = f" [color={c}][font=Symbols]\u2192[/font] {self._kind_label(kind)} Insanity[/color]"
        return suffix

    def _handle_thresholds(self, threshs):
        app = self._app()
        sanity_tab = app._sanity_tab
        extra_actions = []
        for label, kind in threshs:
            if kind == "zero":
                self._log(f"WARNING: {label}")
                app.notify_event(label, "sanity", T.BLOOD)
                continue
            color = self._kind_color(kind)
            existing = [m for m in reversed(app.state.madnesses) if m.kind == kind]
            if existing and kind != "indefinite":
                cured = existing[0]
                app.state.madnesses.remove(cured)
                cured_name = cured.name if cured.name else cured.kind_label
                self._log(f"THRESHOLD re-crossed (wound): {label} - cured {cured_name}")
            elif existing and kind == "indefinite":
                self._log(f"THRESHOLD re-crossed (wound): {label}")
            else:
                m = app.state.add_madness(kind)
                self._log(
                    f"THRESHOLD (wound): {label} > {m.kind_label} insanity: "
                    f"[{m.roll_range}] {m.name}"
                )
                extra_actions.append(
                    ("INSANITY >", "sanity", lambda ee=m: sanity_tab.open_madness(ee))
                )
        if threshs:
            app.refresh_all()
        return extra_actions

    def _clear_wound_details(self):
        """Collapse all open panels and reset selection (used on page switch)."""
        if self._sel_minor_widget:
            self._sel_minor_widget.set_selected(False, persist=False)
        if self._sel_major_widget:
            self._sel_major_widget.set_selected(False, persist=False)
        for d in self._minor_details.values():
            self._collapse_panel(d)
        for d in self._major_details.values():
            self._collapse_panel(d)
        self._sel_minor        = None
        self._sel_minor_widget = None
        self._sel_major        = None
        self._sel_major_widget = None

    # â”€â”€ Public refresh â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

    def refresh(self):
        app    = self._app()
        minors = app.state.minor_wounds
        majors = app.state.major_wounds

        # Preserve selection across rebuild
        prev_minor = self._sel_minor
        prev_major = self._sel_major

        # â”€â”€ Minor wounds â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
        self._minor_list_box.clear_widgets()
        self._minor_details.clear()
        self._minor_items.clear()
        self._sel_minor_widget = None

        if not minors:
            self._sel_minor = None
        else:
            for i, w in enumerate(minors):
                is_sel = (w is prev_minor)
                _mroll = next((r for r, d, _ in MINOR_WOUND_TABLE if d == w.description), "?")
                item = ListItem(
                    primary=w.description,
                    secondary=f"Minor Wound | Roll: {_mroll} | 1d4 Sanity Loss",
                    accent_hex=T.WOUND_MIN,
                    on_tap=lambda widget, entry=w: self._on_minor_tap(widget, entry))

                if is_sel:
                    item.set_selected(True, persist=True)
                    self._sel_minor_widget = item

                self._minor_list_box.add_widget(item)
                self._minor_items[i] = item

                detail = MDBoxLayout(
                    orientation="vertical", size_hint_y=None, height=0, opacity=0,
                    padding=[dp(0), dp(4), dp(0), dp(4)])
                inner = DescriptionCard(title="MINOR WOUND", color_hex=T.WOUND_MIN)
                _roll = next((r for r, d, _ in MINOR_WOUND_TABLE if d == w.description), "?")
                _desc = MDLabel(
                    text=f"{self._wound_roll_preview_text('minor', _roll)}\n\n{w.effect}",
                    theme_text_color="Custom", text_color=T.k(T.TEXT),
                    font_style="Body2", size_hint_y=None, adaptive_height=True)
                _desc.bind(width=lambda inst, val: setattr(inst, "text_size", (val, None)))
                inner.add_widget(_desc)
                detail.add_widget(inner)

                self._minor_list_box.add_widget(detail)
                self._minor_details[i] = detail

                if is_sel:
                    self._expand_panel(detail)

        # â”€â”€ Major wounds â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
        self._major_list_box.clear_widgets()
        self._major_details.clear()
        self._major_items.clear()
        self._sel_major_widget = None

        if not majors:
            self._sel_major = None
        else:
            for i, w in enumerate(majors):
                is_sel = (w is prev_major)
                _Mroll = next((r for r, d, _ in MAJOR_WOUND_TABLE if d == w.description), "?")
                item = ListItem(
                    primary=w.description,
                    secondary=f"Major Wound | Roll: {_Mroll} | 2d4 Sanity Loss",
                    accent_hex=T.BLOOD,
                    on_tap=lambda widget, entry=w: self._on_major_tap(widget, entry))

                if is_sel:
                    item.set_selected(True, persist=True)
                    self._sel_major_widget = item

                self._major_list_box.add_widget(item)
                self._major_items[i] = item

                detail = MDBoxLayout(
                    orientation="vertical", size_hint_y=None, height=0, opacity=0,
                    padding=[dp(0), dp(4), dp(0), dp(4)])
                inner = DescriptionCard(title="MAJOR WOUND", color_hex=T.BLOOD)
                _roll = next((r for r, d, _ in MAJOR_WOUND_TABLE if d == w.description), "?")
                _desc = MDLabel(
                    text=f"{self._wound_roll_preview_text('major', _roll)}\n\n{w.effect}",
                    theme_text_color="Custom", text_color=T.k(T.TEXT),
                    font_style="Body2", size_hint_y=None, adaptive_height=True)
                _desc.bind(width=lambda inst, val: setattr(inst, "text_size", (val, None)))
                inner.add_widget(_desc)
                detail.add_widget(inner)

                self._major_list_box.add_widget(detail)
                self._major_details[i] = detail

                if is_sel:
                    self._expand_panel(detail)

    def highlight_last_wound(self, severity: str):
        """Flash the most recently added wound entry."""
        items = self._minor_items if severity == "minor" else self._major_items
        if not items:
            return
        last_idx = max(items.keys())
        item = items.get(last_idx)
        if item:
            item.flash()

    # â”€â”€ Encounter â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

    def _on_wound_encounter(self, *_):
        app = self._app()
        try:
            dc  = safe_int(self._wdc_field.text or "10", lo=1)
            dmg = safe_int(self._dmg_field.text or "0",  lo=0)
        except Exception:
            self._snack("Enter valid DC and damage.", T.BORDER); return

        actual_dc = max(dc, dmg // 2)
        con_mod = app.state.con_mod
        if getattr(app, 'con_adv', False):
            rolls = roll_d(20, 2)
            d20 = max(rolls)
            roll_str = f"D20 Adv({rolls[0]},{rolls[1]}) >> {d20}"
        else:
            d20 = roll_d(20)[0]
            roll_str = f"D20({d20})"
        con_save  = d20 + con_mod

        self._enc.dc           = actual_dc
        self._enc.damage_taken = dmg
        self._enc.roll_total   = con_save
        self._enc.con_mod_used = con_mod
        self._enc.phase        = WoundEncPhase.AWAITING_SAVE

        self._log("=== WOUND ENCOUNTER ===")
        self._log(
            f"CON Save: {roll_str} + {con_mod:+d} = {con_save} "
            f"vs DC {actual_dc}")

        diff = con_save - actual_dc
        if diff >= 5:    verdict = "PASS  5+"
        elif diff >= 0:  verdict = "PASS"
        elif diff >= -4: verdict = "FAIL"
        else:            verdict = "FAIL  5+"

        is_fail = "FAIL" in verdict
        show_hope = is_fail and app.state.hope
        self._w_hope_row.height  = dp(108) if show_hope else 0
        self._w_hope_row.opacity = 1       if show_hope else 0
        # Animate panel open â€” measure height after children are set, then grow
        panel = self._w_roll_panel
        panel.height  = 0
        panel.opacity = 0
        def _open_panel(dt):
            Animation(height=panel.minimum_height, opacity=1,
                      duration=0.18, t="out_quart").start(panel)
        Clock.schedule_once(_open_panel, 0)
        self._w_roll_lbl.text      = f"CON Save: {con_save} vs DC {actual_dc}"
        self._w_roll_big.text      = verdict
        color = T.GREEN if "PASS" in verdict else T.BLOOD
        self._w_roll_big.text_color = T.k(color)
        self._enc.result_text        = verdict
        self._wpass5_btn.disabled = (verdict != "PASS  5+")
        self._wpass_btn.disabled  = (verdict != "PASS")
        self._wfail_btn.disabled  = (verdict != "FAIL")
        self._wfail5_btn.disabled = (verdict != "FAIL  5+")

    def _use_hope(self):
        app = self._app()
        self._push_undo()
        app.state.hope = False
        self._w_hope_row.height  = 0
        self._w_hope_row.opacity = 0
        app.refresh_all()
        # Hope guarantees a pass â€” auto-resolve as no wound
        self._resolve("pass5")

    def _end_enc(self):
        self._enc.reset()
        Animation(height=0, opacity=0, duration=0.15, t="in_quart").start(self._w_roll_panel)
        self._wpass5_btn.disabled  = True
        self._wpass_btn.disabled   = True
        self._wfail_btn.disabled   = True
        self._wfail5_btn.disabled  = True

    def _resolve(self, outcome: str):
        app = self._app()
        self._push_undo()

        sanity_loss = 0

        if outcome == "pass5":
            self._log("Wound Encounter: PASS by 5+ - no wound")
        elif outcome == "pass":
            _, desc, effect = roll_random_wound("minor")
            _we = app.state.add_wound(desc, effect, "minor")
            sanity_loss = sum(roll_d(4, 1))
            old_sanity = app.state.current_sanity
            pre_madness_kinds = [m.kind for m in app.state.madnesses]
            threshs = app.state.apply_loss(sanity_loss)
            new_sanity = app.state.current_sanity
            self._log(f"Wound Encounter: PASS - Minor Wound: {desc} | Sanity -{sanity_loss}")
            threshold_actions = self._handle_thresholds(threshs)
            app.refresh_all()
            pct = int(new_sanity / app.state.max_sanity * 100) if app.state.max_sanity else 0
            pre_counts = {k: pre_madness_kinds.count(k) for k in ("short", "long", "indefinite")}
            thresh_suffix = self._threshold_suffix_for_notif(threshs, pre_counts)
            Clock.schedule_once(
                lambda _, e=_we, d=desc: app.notify_event(
                    f"Minor Wound: [color={T.BLOOD}]{d}[/color]", "wounds", T.BLOOD,
                    action_cb=lambda ee=e: self.open_wound(ee, "minor")
                ), 0.15)
            Clock.schedule_once(
                lambda _, e=_we, os=old_sanity, sl=sanity_loss, ns=new_sanity, p=pct, ts=thresh_suffix: app.notify_event(
                    f"Sanity: [color={T.PURPLE_LT}]{os} - {sl} = {ns} ({p}%)[/color]{ts}",
                    "wounds", T.BLOOD,
                    action_cb=lambda ee=e: self.open_wound(ee, "minor"),
                    extra_actions=threshold_actions
                ), 0.15)
        elif outcome == "fail":
            _, desc, effect = roll_random_wound("major")
            _we = app.state.add_wound(desc, effect, "major")
            sanity_loss = sum(roll_d(4, 2))
            old_sanity = app.state.current_sanity
            pre_madness_kinds = [m.kind for m in app.state.madnesses]
            threshs = app.state.apply_loss(sanity_loss)
            new_sanity = app.state.current_sanity
            self._log(f"Wound Encounter: FAIL - Major Wound: {desc} | Sanity -{sanity_loss}")
            threshold_actions = self._handle_thresholds(threshs)
            app.refresh_all()
            pct = int(new_sanity / app.state.max_sanity * 100) if app.state.max_sanity else 0
            pre_counts = {k: pre_madness_kinds.count(k) for k in ("short", "long", "indefinite")}
            thresh_suffix = self._threshold_suffix_for_notif(threshs, pre_counts)
            Clock.schedule_once(
                lambda _, e=_we, d=desc: app.notify_event(
                    f"Major Wound: [color={T.BLOOD}]{d}[/color]", "wounds", T.BLOOD,
                    action_cb=lambda ee=e: self.open_wound(ee, "major")
                ), 0.15)
            Clock.schedule_once(
                lambda _, e=_we, os=old_sanity, sl=sanity_loss, ns=new_sanity, p=pct, ts=thresh_suffix: app.notify_event(
                    f"Sanity: [color={T.PURPLE_LT}]{os} - {sl} = {ns} ({p}%)[/color]{ts}",
                    "wounds", T.BLOOD,
                    action_cb=lambda ee=e: self.open_wound(ee, "major"),
                    extra_actions=threshold_actions
                ), 0.15)
        elif outcome == "fail5":
            _, desc, effect = roll_random_wound("major")
            _we = app.state.add_wound(desc, effect, "major")
            sanity_loss = sum(roll_d(4, 2))
            old_sanity = app.state.current_sanity
            pre_madness_kinds = [m.kind for m in app.state.madnesses]
            threshs = app.state.apply_loss(sanity_loss)
            new_sanity = app.state.current_sanity
            app.state.exhaustion = int(clamp(app.state.exhaustion + 1, 0, 6))
            self._log(
                f"Wound Encounter: FAIL by 5+ - Major Wound: {desc} + Exhaustion | "
                f"Sanity -{sanity_loss}"
            )
            threshold_actions = self._handle_thresholds(threshs)
            app.refresh_all()
            pct = int(new_sanity / app.state.max_sanity * 100) if app.state.max_sanity else 0
            pre_counts = {k: pre_madness_kinds.count(k) for k in ("short", "long", "indefinite")}
            thresh_suffix = self._threshold_suffix_for_notif(threshs, pre_counts)
            Clock.schedule_once(
                lambda _, e=_we, d=desc: app.notify_event(
                    f"Major Wound + Exhaustion: [color={T.BLOOD}]{d}[/color]",
                    "wounds", T.BLOOD,
                    action_cb=lambda ee=e: self.open_wound(ee, "major")
                ), 0.15)
            Clock.schedule_once(
                lambda _, e=_we, os=old_sanity, sl=sanity_loss, ns=new_sanity, p=pct, ts=thresh_suffix: app.notify_event(
                    f"Sanity: [color={T.PURPLE_LT}]{os} - {sl} = {ns} ({p}%)[/color]{ts}",
                    "wounds", T.BLOOD,
                    action_cb=lambda ee=e: self.open_wound(ee, "major"),
                    extra_actions=threshold_actions
                ), 0.15)
            _exh = app.state.exhaustion
            Clock.schedule_once(lambda _: app.notify_exhaustion(_exh), 0.5)

        Clock.schedule_once(lambda _: self._end_enc(), 0.6)
        self._save()
    # â”€â”€ Add wound â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

    def _add_wound(self, severity: str, desc: str = "", effect: str = ""):
        app = self._app()
        self._push_undo()
        if not desc:
            _, desc, effect = roll_random_wound(severity)
        elif not effect:
            effect = "Custom wound."
        entry = app.state.add_wound(desc, effect, severity)
        self._log(f"{severity.title()} wound added: {desc}")
        self.refresh()
        app.refresh_all()
        self._save()
        color = T.WOUND_MIN if severity == "minor" else T.BLOOD
        Clock.schedule_once(
            lambda _, e=entry, s=severity, c=color: app.notify_event(
                f"{s.title()} Wound: [color={c}]{desc}[/color]",
                "wounds", c,
                action_cb=lambda _e=e, _s=s: self.open_wound(_e, _s)
            ), 0.15)

    # â”€â”€ Active list interactions â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

    def _on_minor_tap(self, widget: ListItem, entry: WoundEntry):
        # Collapse any open major selection first
        if self._sel_major_widget:
            self._sel_major_widget.set_selected(False, persist=False)
            app = self._app()
            for i, w in enumerate(app.state.major_wounds):
                if w is self._sel_major:
                    d = self._major_details.get(i)
                    if d:
                        self._collapse_panel(d)
                    break
            self._sel_major        = None
            self._sel_major_widget = None
        # Collapse previously selected minor
        if self._sel_minor_widget and self._sel_minor_widget is not widget:
            self._sel_minor_widget.set_selected(False, persist=False)
            app = self._app()
            for i, w in enumerate(app.state.minor_wounds):
                if w is self._sel_minor:
                    d = self._minor_details.get(i)
                    if d:
                        self._collapse_panel(d)
                    break

        self._sel_minor        = entry
        self._sel_minor_widget = widget
        widget.set_selected(True, persist=True)

        app = self._app()
        for i, w in enumerate(app.state.minor_wounds):
            if w is entry:
                detail = self._minor_details.get(i)
                if detail:
                    self._expand_panel(detail)
                break

    def _on_major_tap(self, widget: ListItem, entry: WoundEntry):
        # Collapse any open minor selection first
        if self._sel_minor_widget:
            self._sel_minor_widget.set_selected(False, persist=False)
            app = self._app()
            for i, w in enumerate(app.state.minor_wounds):
                if w is self._sel_minor:
                    d = self._minor_details.get(i)
                    if d:
                        self._collapse_panel(d)
                    break
            self._sel_minor        = None
            self._sel_minor_widget = None
        # Collapse previously selected major
        if self._sel_major_widget and self._sel_major_widget is not widget:
            self._sel_major_widget.set_selected(False, persist=False)
            app = self._app()
            for i, w in enumerate(app.state.major_wounds):
                if w is self._sel_major:
                    d = self._major_details.get(i)
                    if d:
                        self._collapse_panel(d)
                    break

        self._sel_major        = entry
        self._sel_major_widget = widget
        widget.set_selected(True, persist=True)

        app = self._app()
        for i, w in enumerate(app.state.major_wounds):
            if w is entry:
                detail = self._major_details.get(i)
                if detail:
                    self._expand_panel(detail)
                break

    def open_wound(self, entry, severity: str):
        """Navigate to main page, open the detail panel, and flash the entry."""
        self._go_page(0)
        app = self._app()
        wound_list = app.state.minor_wounds if severity == "minor" else app.state.major_wounds
        items = self._minor_items if severity == "minor" else self._major_items
        for i, w in enumerate(wound_list):
            if w is entry:
                item = items.get(i)
                if item:
                    if severity == "minor":
                        self._on_minor_tap(item, entry)
                    else:
                        self._on_major_tap(item, entry)
                    item.flash()
                return

    # â”€â”€ Remove wound (header trash-can, same pattern as fear list) â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

    def _on_remove_wound(self, *_):
        if self._sel_minor:
            self._on_remove_minor()
        elif self._sel_major:
            self._on_remove_major()
        else:
            self._snack("Select a wound first.", T.BORDER)

    def _on_remove_minor(self, *_):
        if not self._sel_minor:
            self._snack("Select a minor wound first.", T.BORDER)
            return
        app = self._app()
        w = self._sel_minor
        if w not in app.state.wounds:
            self._sel_minor        = None
            self._sel_minor_widget = None
            return
        self._push_undo()
        app.state.wounds.remove(w)
        self._log(f"Minor wound removed: {w.description}")
        self._sel_minor        = None
        self._sel_minor_widget = None
        self.refresh()
        app.refresh_all()
        self._save()

    def _on_remove_major(self, *_):
        if not self._sel_major:
            self._snack("Select a major wound first.", T.BORDER)
            return
        app = self._app()
        w = self._sel_major
        if w not in app.state.wounds:
            self._sel_major        = None
            self._sel_major_widget = None
            return
        self._push_undo()
        app.state.wounds.remove(w)
        self._log(f"Major wound removed: {w.description}")
        self._sel_major        = None
        self._sel_major_widget = None
        self.refresh()
        app.refresh_all()
        self._save()

