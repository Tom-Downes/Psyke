"""
Tab 3: Wounds  (V2 redesign)

Two-page swipeable layout:
  Page 0 — Encounter & Wounds: encounter card, wound lists, rules
  Page 1 — Add Wound: minor/major picker, preview + Apply button

Swipe left/right to move between pages.
"""
from __future__ import annotations

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
    BorderCard, AccentCard, DescriptionCard, Divider,
    SectionLabel, CaptionLabel, MultilineLabel,
    ListItem, ExpandableSection, themed_field, PickerButton, PageDot
)
import theme as T

_ROLL_H = dp(20 + 48 + 44 + 44 + 20) + dp(4) * 4


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

        # Add-page: severity -> (detail MDBoxLayout, desc MDLabel, apply_btn)
        self._add_preview: dict = {}
        # Add-page pending: severity -> (roll, desc, effect)
        self._pending_wound: dict = {}

        # ── Page state ──────────────────────────────────────────────────────
        self._page = 0  # 0 = Encounter & Wounds, 1 = Add Wound

        self.add_widget(self._build_page_indicator())

        self._content_area = MDBoxLayout(orientation="vertical")
        self.add_widget(self._content_area)

        # ── Page 0 (Encounter & Wounds) ──────────────────────────────────────
        self._sv0 = ScrollView(do_scroll_x=False)
        p0 = MDBoxLayout(
            orientation="vertical",
            padding=dp(10), spacing=dp(8),
            size_hint_y=None, adaptive_height=True)
        p0.add_widget(self._build_encounter_card())
        p0.add_widget(self._build_minor_wounds_card())
        p0.add_widget(self._build_major_wounds_card())
        p0.add_widget(self._build_rules_panel())
        self._sv0.add_widget(p0)

        # ── Page 1 (Add Wound) ───────────────────────────────────────────────
        self._sv1 = ScrollView(do_scroll_x=False)
        p1 = MDBoxLayout(
            orientation="vertical",
            padding=dp(10), spacing=dp(8),
            size_hint_y=None, adaptive_height=True)
        p1.add_widget(self._build_add_wound_card())
        self._sv1.add_widget(p1)

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
            text="Encounter & Wounds", halign="right",
            theme_text_color="Custom", text_color=T.k(T.BLOOD),
            font_style="Caption", bold=True, size_hint_x=0.44)
        self._dot0 = PageDot(color_hex=T.BLOOD)
        self._dot1 = PageDot(color_hex=T.TEXT_DIM)
        self._ind_lbl1 = MDLabel(
            text="Add Wound", halign="left",
            theme_text_color="Custom", text_color=T.k(T.TEXT_DIM),
            font_style="Caption", bold=False, size_hint_x=0.32)

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

    # ── Swipe detection ──────────────────────────────────────────────────────

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

    # ── Build: Encounter Card ─────────────────────────────────────────────────

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
        field_row.add_widget(self._wdc_field)
        field_row.add_widget(self._dmg_field)
        card.add_widget(field_row)

        self._wenc_btn = MDRaisedButton(
            text="WOUND ENCOUNTER",
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

        wr1 = MDBoxLayout(spacing=dp(4), size_hint_y=None, height=dp(44))
        self._wpass5_btn = MDRaisedButton(
            text="Pass 5+", md_bg_color=T.k(T.GREEN_LT),
            size_hint_x=0.5, on_release=lambda *_: self._resolve("pass5"))
        self._wpass_btn = MDRaisedButton(
            text="Pass", md_bg_color=T.k(T.GREEN),
            size_hint_x=0.5, on_release=lambda *_: self._resolve("pass"))
        wr1.add_widget(self._wpass5_btn)
        wr1.add_widget(self._wpass_btn)
        self._w_roll_panel.add_widget(wr1)

        wr2 = MDBoxLayout(spacing=dp(4), size_hint_y=None, height=dp(44))
        self._wfail_btn = MDRaisedButton(
            text="Fail", md_bg_color=T.k(T.RED),
            size_hint_x=0.5, on_release=lambda *_: self._resolve("fail"))
        self._wfail5_btn = MDRaisedButton(
            text="Fail 5+", md_bg_color=T.k(T.BLOOD),
            size_hint_x=0.5, on_release=lambda *_: self._resolve("fail5"))
        wr2.add_widget(self._wfail_btn)
        wr2.add_widget(self._wfail5_btn)
        self._w_roll_panel.add_widget(wr2)

        self._w_result_lbl = MDLabel(
            text="", theme_text_color="Custom",
            text_color=T.k(T.TEXT_DIM), font_style="Caption",
            size_hint_y=None, height=dp(20))
        self._w_roll_panel.add_widget(self._w_result_lbl)
        card.add_widget(self._w_roll_panel)
        return card

    # ── Build: Active Wound Cards ─────────────────────────────────────────────

    def _build_minor_wounds_card(self) -> BorderCard:
        card = BorderCard(border_hex=T.WOUND_MIN)

        # Header with trash-can remove button (same pattern as fear list)
        hdr = MDBoxLayout(size_hint_y=None, height=dp(32), spacing=dp(8))
        hdr.add_widget(SectionLabel("ACTIVE MINOR WOUNDS", color_hex=T.WOUND_MIN))
        hdr.add_widget(Widget())
        hdr.add_widget(MDIconButton(
            icon="trash-can-outline",
            theme_icon_color="Custom", icon_color=T.k(T.RED),
            size_hint_x=None, width=dp(40),
            on_release=self._on_remove_minor))
        card.add_widget(hdr)

        self._minor_list_box = MDBoxLayout(
            orientation="vertical", adaptive_height=True, spacing=dp(2))
        card.add_widget(self._minor_list_box)
        return card

    def _build_major_wounds_card(self) -> BorderCard:
        card = BorderCard(border_hex=T.BLOOD)

        # Header with trash-can remove button
        hdr = MDBoxLayout(size_hint_y=None, height=dp(32), spacing=dp(8))
        hdr.add_widget(SectionLabel("ACTIVE MAJOR WOUNDS", color_hex=T.BLOOD))
        hdr.add_widget(Widget())
        hdr.add_widget(MDIconButton(
            icon="trash-can-outline",
            theme_icon_color="Custom", icon_color=T.k(T.RED),
            size_hint_x=None, width=dp(40),
            on_release=self._on_remove_major))
        card.add_widget(hdr)

        self._major_list_box = MDBoxLayout(
            orientation="vertical", adaptive_height=True, spacing=dp(2))
        card.add_widget(self._major_list_box)
        return card

    # ── Build: Add Wound Card (Page 1) ────────────────────────────────────────

    def _build_add_wound_card(self) -> BorderCard:
        card = BorderCard(border_hex=T.BLOOD)
        card.add_widget(SectionLabel("ADD WOUND", color_hex=T.BLOOD))
        card.add_widget(CaptionLabel(
            "Select from the table — preview appears below. Tap Apply to add.",
            color_hex=T.TEXT_DIM, height_dp=28))

        rows = [
            ("MINOR WOUND", "Heals on Long Rest",        T.WOUND_MIN, "minor"),
            ("MAJOR WOUND", "Requires Major Restoration", T.BLOOD,    "major"),
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

            # Preview panel — added directly to card, BENEATH the AccentCard
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
        """Store selection as pending and show preview — does NOT add yet."""
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
            desc_lbl.text = f"{roll}. {desc}\n\n{effect}"
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

    def _build_rules_panel(self) -> ExpandableSection:
        sec = ExpandableSection("Wound Rules", accent_hex=T.BLOOD)
        sec.add_content(MultilineLabel(text=WOUND_RULES_TEXT, color_hex=T.TEXT_DIM))
        return sec

    # ── Internal helpers ─────────────────────────────────────────────────────

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

    # ── Public refresh ─────────────────────────────────────────────────────────

    def refresh(self):
        app    = self._app()
        minors = app.state.minor_wounds
        majors = app.state.major_wounds

        # Preserve selection across rebuild
        prev_minor = self._sel_minor
        prev_major = self._sel_major

        # ── Minor wounds ──────────────────────────────────────────────────────
        self._minor_list_box.clear_widgets()
        self._minor_details.clear()
        self._sel_minor_widget = None

        if not minors:
            self._minor_list_box.add_widget(CaptionLabel(
                "No minor wounds. Treated with a Long Rest.",
                color_hex=T.TEXT_DIM, height_dp=28))
            self._sel_minor = None
        else:
            for i, w in enumerate(minors):
                is_sel = (w is prev_minor)
                item = ListItem(
                    primary=w.description,
                    secondary=w.effect[:60] + ("..." if len(w.effect) > 60 else ""),
                    accent_hex=T.WOUND_MIN,
                    on_tap=lambda widget, entry=w: self._on_minor_tap(widget, entry))

                if is_sel:
                    item.set_selected(True, persist=True)
                    self._sel_minor_widget = item

                self._minor_list_box.add_widget(item)

                detail = MDBoxLayout(
                    orientation="vertical", size_hint_y=None, height=0, opacity=0,
                    padding=[dp(0), dp(4), dp(0), dp(4)])
                inner = DescriptionCard(title="MINOR WOUND", color_hex=T.WOUND_MIN)
                _desc = MDLabel(
                    text=f"{w.description}\n\n{w.effect}",
                    theme_text_color="Custom", text_color=T.k(T.TEXT),
                    font_style="Body2", size_hint_y=None, adaptive_height=True)
                _desc.bind(width=lambda inst, val: setattr(inst, "text_size", (val, None)))
                inner.add_widget(_desc)
                detail.add_widget(inner)

                self._minor_list_box.add_widget(detail)
                self._minor_details[i] = detail

                if is_sel:
                    self._expand_panel(detail)

        # ── Major wounds ──────────────────────────────────────────────────────
        self._major_list_box.clear_widgets()
        self._major_details.clear()
        self._sel_major_widget = None

        if not majors:
            self._major_list_box.add_widget(CaptionLabel(
                "No major wounds. Requires Major Restoration to cure.",
                color_hex=T.TEXT_DIM, height_dp=28))
            self._sel_major = None
        else:
            for i, w in enumerate(majors):
                is_sel = (w is prev_major)
                item = ListItem(
                    primary=w.description,
                    secondary=w.effect[:60] + ("..." if len(w.effect) > 60 else ""),
                    accent_hex=T.BLOOD,
                    on_tap=lambda widget, entry=w: self._on_major_tap(widget, entry))

                if is_sel:
                    item.set_selected(True, persist=True)
                    self._sel_major_widget = item

                self._major_list_box.add_widget(item)

                detail = MDBoxLayout(
                    orientation="vertical", size_hint_y=None, height=0, opacity=0,
                    padding=[dp(0), dp(4), dp(0), dp(4)])
                inner = DescriptionCard(title="MAJOR WOUND", color_hex=T.BLOOD)
                _desc = MDLabel(
                    text=f"{w.description}\n\n{w.effect}",
                    theme_text_color="Custom", text_color=T.k(T.TEXT),
                    font_style="Body2", size_hint_y=None, adaptive_height=True)
                _desc.bind(width=lambda inst, val: setattr(inst, "text_size", (val, None)))
                inner.add_widget(_desc)
                detail.add_widget(inner)

                self._major_list_box.add_widget(detail)
                self._major_details[i] = detail

                if is_sel:
                    self._expand_panel(detail)

    # ── Encounter ─────────────────────────────────────────────────────────────

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
            roll_str = f"D20 Adv({rolls[0]},{rolls[1]})→{d20}"
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

        self._w_roll_panel.height  = _ROLL_H
        self._w_roll_panel.opacity = 1
        self._w_roll_lbl.text      = f"CON Save: {con_save} vs DC {actual_dc}"
        self._w_roll_big.text      = verdict
        color = T.GREEN if "PASS" in verdict else T.BLOOD
        self._w_roll_big.text_color = T.k(color)
        self._enc.result_text       = verdict
        self._wpass5_btn.disabled = False
        self._wpass_btn.disabled  = False
        self._wfail_btn.disabled  = False
        self._wfail5_btn.disabled = False

    def _resolve(self, outcome: str):
        app = self._app()
        self._push_undo()

        if outcome == "pass5":
            self._log("Wound Encounter: PASS by 5+ — no wound")
            self._w_result_lbl.text = "No wound!"
        elif outcome == "pass":
            _, desc, effect = roll_random_wound("minor")
            app.state.add_wound(desc, effect, "minor")
            self._log(f"Wound Encounter: PASS — Minor Wound: {desc}")
            self._w_result_lbl.text = f"Minor Wound: {desc}"
            app.refresh_all()
        elif outcome == "fail":
            _, desc, effect = roll_random_wound("major")
            app.state.add_wound(desc, effect, "major")
            self._log(f"Wound Encounter: FAIL — Major Wound: {desc}")
            self._w_result_lbl.text = f"Major Wound: {desc}"
            app.refresh_all()
        elif outcome == "fail5":
            _, desc, effect = roll_random_wound("major")
            app.state.add_wound(desc, effect, "major")
            app.state.exhaustion = int(clamp(app.state.exhaustion + 1, 0, 6))
            self._log(f"Wound Encounter: FAIL by 5+ — Major Wound: {desc} + Exhaustion")
            self._w_result_lbl.text = f"Major Wound: {desc} + 1 Exhaustion"
            app.refresh_all()

        self._wpass5_btn.disabled = True
        self._wpass_btn.disabled  = True
        self._wfail_btn.disabled  = True
        self._wfail5_btn.disabled = True
        self._enc.reset()
        self._save()

    # ── Add wound ────────────────────────────────────────────────────────────

    def _add_wound(self, severity: str, desc: str = "", effect: str = ""):
        app = self._app()
        self._push_undo()
        if not desc:
            _, desc, effect = roll_random_wound(severity)
        elif not effect:
            effect = "Custom wound."
        app.state.add_wound(desc, effect, severity)
        self._log(f"{severity.title()} wound added: {desc}")
        self.refresh()
        app.refresh_all()
        self._save()

    # ── Active list interactions ───────────────────────────────────────────────

    def _on_minor_tap(self, widget: ListItem, entry: WoundEntry):
        # Collapse previously selected
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
        # Collapse previously selected
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

    # ── Remove wound (header trash-can, same pattern as fear list) ─────────────

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
