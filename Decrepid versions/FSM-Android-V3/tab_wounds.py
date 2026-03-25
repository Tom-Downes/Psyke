"""
Tab 3: Wounds  (V2 redesign)

Two-page swipeable layout:
  Page 0 — Encounter & Wounds: encounter card, wound lists, rules
  Page 1 — Add Wound: minor/major picker, single pending preview, add button

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
from kivymd.uix.button import MDFlatButton, MDRaisedButton
from kivymd.uix.label import MDLabel
from kivymd.uix.menu import MDDropdownMenu
from kivymd.uix.snackbar import MDSnackbar

from models import (
    WoundEncPhase, WoundEncounterState, WoundEntry,
    MINOR_WOUND_TABLE, MAJOR_WOUND_TABLE,
    roll_d, safe_int, roll_random_wound, clamp, WOUND_RULES_TEXT
)
from ui_utils import (
    BorderCard, DescriptionCard, Divider,
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
        self._sel_minor: int | None = None
        self._sel_minor_widget: ListItem | None = None
        self._sel_major: int | None = None
        self._sel_major_widget: ListItem | None = None
        self._pending: dict | None = None   # {severity, desc, effect}

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
        p0.add_widget(self._build_wound_lists_card())
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
            self._dot1.set_color(T.WOUND_MIN)
            self._ind_lbl0.bold       = False
            self._ind_lbl0.text_color = T.k(T.TEXT_DIM)
            self._ind_lbl1.bold       = True
            self._ind_lbl1.text_color = T.k(T.WOUND_MIN)

    def _go_page(self, page: int):
        if page == self._page:
            return
        self._page = page
        self._clear_wound_details()
        self._content_area.clear_widgets()
        self._content_area.add_widget(self._sv0 if page == 0 else self._sv1)
        self._update_indicator()

    # ── Swipe + click-off detection ──────────────────────────────────────────

    def on_touch_down(self, touch):
        if self.collide_point(*touch.pos):
            touch.ud['wounds_swipe_start'] = (touch.x, touch.y)
            # If on page 0 and touch is not on any wound list item → clear descriptions
            if self._page == 0:
                all_items = (
                    list(self._minor_list_box.children) +
                    list(self._major_list_box.children)
                )
                if not any(c.collide_point(*touch.pos) for c in all_items):
                    self._clear_wound_details()
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
            text="Pass 5+", md_bg_color=T.k(T.BLUE),
            size_hint_x=0.5, on_release=lambda *_: self._resolve("pass5"))
        self._wpass_btn = MDRaisedButton(
            text="Pass", md_bg_color=T.k(T.BLUE),
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

    # ── Build: Wound Lists Card ───────────────────────────────────────────────

    def _build_wound_lists_card(self) -> BorderCard:
        card = BorderCard(border_hex=T.BLOOD)

        # Minor wounds
        card.add_widget(SectionLabel("MINOR WOUNDS", color_hex=T.WOUND_MIN))
        self._minor_list_box = MDBoxLayout(
            orientation="vertical", adaptive_height=True, spacing=dp(2))
        card.add_widget(self._minor_list_box)

        self._minor_detail_card = DescriptionCard(
            title="MINOR WOUND", color_hex=T.WOUND_MIN)
        self._minor_detail = MDLabel(
            text="Tap a wound to view its full effect.",
            theme_text_color="Custom", text_color=T.k(T.TEXT_DIM),
            font_style="Body1", size_hint_y=None, adaptive_height=True)
        self._minor_detail.bind(
            width=lambda inst, val: setattr(inst, "text_size", (val, None)))
        self._minor_detail_card.add_widget(self._minor_detail)
        card.add_widget(self._minor_detail_card)

        card.add_widget(MDFlatButton(
            text="Remove", theme_text_color="Custom", text_color=T.k(T.TEXT_DIM),
            size_hint_y=None, height=dp(36), on_release=self._on_remove_minor))

        # Major wounds
        card.add_widget(Divider(color_hex=T.BLOOD))
        card.add_widget(SectionLabel("MAJOR WOUNDS", color_hex=T.STAGE_4))
        self._major_list_box = MDBoxLayout(
            orientation="vertical", adaptive_height=True, spacing=dp(2))
        card.add_widget(self._major_list_box)

        self._major_detail_card = DescriptionCard(
            title="MAJOR WOUND", color_hex=T.BLOOD)
        self._major_detail = MDLabel(
            text="Tap a wound to view its full effect.",
            theme_text_color="Custom", text_color=T.k(T.TEXT_DIM),
            font_style="Body1", size_hint_y=None, adaptive_height=True)
        self._major_detail.bind(
            width=lambda inst, val: setattr(inst, "text_size", (val, None)))
        self._major_detail_card.add_widget(self._major_detail)
        card.add_widget(self._major_detail_card)

        card.add_widget(MDFlatButton(
            text="Remove", theme_text_color="Custom", text_color=T.k(T.TEXT_DIM),
            size_hint_y=None, height=dp(36), on_release=self._on_remove_major))

        return card

    # ── Build: Add Wound Card (Page 1) ────────────────────────────────────────

    def _build_add_wound_card(self) -> BorderCard:
        card = BorderCard(border_hex=T.BLOOD)
        card.add_widget(SectionLabel("ADD WOUND", color_hex=T.BLOOD))
        card.add_widget(CaptionLabel(
            "Pick from the table, then tap Add Wound.",
            color_hex=T.TEXT_DIM, height_dp=18))

        self._pick_minor_btn = PickerButton(
            text="PICK MINOR WOUND", color_hex=T.WOUND_MIN,
            on_press=lambda btn: self._open_wound_menu("minor", btn),
            size_hint_x=1.0)
        card.add_widget(self._pick_minor_btn)

        card.add_widget(Divider(color_hex=T.BORDER))

        self._pick_major_btn = PickerButton(
            text="PICK MAJOR WOUND", color_hex=T.BLOOD,
            on_press=lambda btn: self._open_wound_menu("major", btn),
            size_hint_x=1.0)
        card.add_widget(self._pick_major_btn)

        # Single shared pending preview (appears after selection)
        self._pending_card = DescriptionCard(
            title="SELECTED WOUND", color_hex=T.BLOOD)
        self._pending_lbl = MDLabel(
            text="Pick a wound from the tables above.",
            theme_text_color="Custom", text_color=T.k(T.TEXT_DIM),
            font_style="Body2", size_hint_y=None, adaptive_height=True)
        self._pending_lbl.bind(
            width=lambda inst, val: setattr(inst, "text_size", (val, None)))
        self._pending_card.add_widget(self._pending_lbl)
        card.add_widget(self._pending_card)

        self._add_wound_btn = MDRaisedButton(
            text="ADD WOUND",
            md_bg_color=T.k(T.BLOOD),
            disabled=True,
            size_hint_x=1.0, size_hint_y=None, height=dp(44),
            on_release=self._on_add_pending)
        card.add_widget(self._add_wound_btn)

        return card

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

    def _clear_wound_details(self):
        if self._sel_minor_widget:
            self._sel_minor_widget.set_selected(False, persist=False)
        if self._sel_major_widget:
            self._sel_major_widget.set_selected(False, persist=False)
        self._sel_minor        = None
        self._sel_minor_widget = None
        self._sel_major        = None
        self._sel_major_widget = None
        self._minor_detail.text       = "Tap a wound to view its full effect."
        self._minor_detail.text_color = T.k(T.TEXT_DIM)
        self._major_detail.text       = "Tap a wound to view its full effect."
        self._major_detail.text_color = T.k(T.TEXT_DIM)

    # ── Wound dropdown ────────────────────────────────────────────────────────

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
        m = getattr(self, f"_menu_{severity}", None)
        if m: m.dismiss()
        color = T.WOUND_MIN if severity == "minor" else T.BLOOD
        title = "SELECTED — MINOR WOUND" if severity == "minor" else "SELECTED — MAJOR WOUND"
        self._pending = {"severity": severity, "desc": desc, "effect": effect}
        self._pending_card.set_title(title, color)
        self._pending_lbl.text = f"{roll}. {desc}\n\n{effect}"
        self._pending_lbl.text_color = T.k(T.TEXT)
        self._add_wound_btn.disabled = False

    def _on_add_pending(self, *_):
        if not self._pending: return
        p = self._pending
        self._add_wound(p["severity"], p["desc"], p["effect"])
        self._pending = None
        self._pending_lbl.text = "Pick a wound from the tables above."
        self._pending_lbl.text_color = T.k(T.TEXT_DIM)
        self._pending_card.set_title("SELECTED WOUND", T.BLOOD)
        self._add_wound_btn.disabled = True

    # ── Public refresh ─────────────────────────────────────────────────────────

    def refresh(self):
        app    = self._app()
        minors = app.state.minor_wounds
        majors = app.state.major_wounds

        self._minor_list_box.clear_widgets()
        self._sel_minor        = None
        self._sel_minor_widget = None
        self._minor_detail.text = "Tap a wound to view its full effect."
        self._minor_detail.text_color = T.k(T.TEXT_DIM)

        if not minors:
            self._minor_list_box.add_widget(CaptionLabel(
                "No minor wounds. Treated with a Long Rest.",
                color_hex=T.TEXT_DIM, height_dp=28))
        else:
            for i, w in enumerate(minors):
                item = ListItem(
                    primary=w.description,
                    secondary=w.effect[:60] + ("..." if len(w.effect) > 60 else ""),
                    accent_hex=T.WOUND_MIN,
                    on_tap=lambda widget, idx=i: self._on_minor_tap(widget, idx))
                self._minor_list_box.add_widget(item)

        self._major_list_box.clear_widgets()
        self._sel_major        = None
        self._sel_major_widget = None
        self._major_detail.text = "Tap a wound to view its full effect."
        self._major_detail.text_color = T.k(T.TEXT_DIM)

        if not majors:
            self._major_list_box.add_widget(CaptionLabel(
                "No major wounds. Requires Major Restoration to cure.",
                color_hex=T.TEXT_DIM, height_dp=28))
        else:
            for i, w in enumerate(majors):
                item = ListItem(
                    primary=w.description,
                    secondary=w.effect[:60] + ("..." if len(w.effect) > 60 else ""),
                    accent_hex=T.BLOOD,
                    on_tap=lambda widget, idx=i: self._on_major_tap(widget, idx))
                self._major_list_box.add_widget(item)

    # ── Encounter ─────────────────────────────────────────────────────────────

    def _on_wound_encounter(self, *_):
        app = self._app()
        try:
            dc  = safe_int(self._wdc_field.text or "10", lo=1)
            dmg = safe_int(self._dmg_field.text or "0",  lo=0)
        except Exception:
            self._snack("Enter valid DC and damage.", T.BORDER); return

        actual_dc = max(dc, dmg // 2)
        d20       = roll_d(20)[0]
        con_save  = d20 + app.state.con_mod

        self._enc.dc           = actual_dc
        self._enc.damage_taken = dmg
        self._enc.roll_total   = con_save
        self._enc.con_mod_used = app.state.con_mod
        self._enc.phase        = WoundEncPhase.AWAITING_SAVE

        self._log("=== WOUND ENCOUNTER ===")
        self._log(
            f"CON Save: d20({d20}) + {app.state.con_mod:+d} = {con_save} "
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
        color = T.BLUE if "PASS" in verdict else T.BLOOD
        self._w_roll_big.text_color = T.k(color)
        self._enc.result_text       = verdict

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

    # ── List interactions ─────────────────────────────────────────────────────

    def _on_minor_tap(self, widget: ListItem, idx: int):
        if self._sel_minor_widget and self._sel_minor_widget is not widget:
            self._sel_minor_widget.set_selected(False, persist=False)
        self._sel_minor        = idx
        self._sel_minor_widget = widget
        widget.set_selected(True, persist=True)
        app = self._app()
        minors = app.state.minor_wounds
        if idx < len(minors):
            w = minors[idx]
            self._minor_detail.text_color = T.k(T.TEXT)
            self._minor_detail.text = f"{w.description}\n\n{w.effect}"

    def _on_major_tap(self, widget: ListItem, idx: int):
        if self._sel_major_widget and self._sel_major_widget is not widget:
            self._sel_major_widget.set_selected(False, persist=False)
        self._sel_major        = idx
        self._sel_major_widget = widget
        widget.set_selected(True, persist=True)
        app = self._app()
        majors = app.state.major_wounds
        if idx < len(majors):
            w = majors[idx]
            self._major_detail.text_color = T.k(T.TEXT)
            self._major_detail.text = f"{w.description}\n\n{w.effect}"

    def _remove(self, severity: str, idx: int | None):
        if idx is None:
            self._snack(f"Select a {severity} wound.", T.BORDER); return
        app    = self._app()
        wounds = [w for w in app.state.wounds if w.severity == severity]
        if idx >= len(wounds): return
        target = wounds[idx]
        self._push_undo()
        app.state.wounds.remove(target)
        self._log(f"{severity.title()} wound removed: {target.description}")
        if severity == "minor":
            self._sel_minor        = None
            self._sel_minor_widget = None
        else:
            self._sel_major        = None
            self._sel_major_widget = None
        self.refresh()
        app.refresh_all()
        self._save()

    def _on_remove_minor(self, *_): self._remove("minor", self._sel_minor)
    def _on_remove_major(self, *_): self._remove("major", self._sel_major)
