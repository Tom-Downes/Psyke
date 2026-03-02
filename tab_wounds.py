"""
Tab 3: Wounds
Wound encounter (CON save), Add Wound, Minor/Major wound lists.
Identical logic to V1; uses BorderCard from ui_utils.
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
    WoundEncPhase, WoundEncounterState, WoundEntry,
    roll_d, safe_int, roll_random_wound, clamp, WOUND_RULES_TEXT
)
from ui_utils import (
    BorderCard, Divider,
    SectionLabel, CaptionLabel, MultilineLabel,
    ListItem, ExpandableSection
)
import theme as T

_ROLL_H = dp(20 + 48 + 44 + 44 + 20) + dp(4) * 4


class WoundsTab(ScrollView):

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.do_scroll_x = False
        self._enc = WoundEncounterState()
        self._sel_minor: int | None = None
        self._sel_minor_widget: ListItem | None = None
        self._sel_major: int | None = None
        self._sel_major_widget: ListItem | None = None

        root = MDBoxLayout(
            orientation="vertical", padding=dp(10), spacing=dp(8),
            size_hint_y=None, adaptive_height=True
        )
        self.add_widget(root)
        root.add_widget(self._build_encounter_card())
        root.add_widget(self._build_wounds_card())
        root.add_widget(self._build_rules_panel())

    # ── Build: Encounter Card ─────────────────────────────────────────────────

    def _build_encounter_card(self) -> BorderCard:
        card = BorderCard(border_hex=T.BLOOD)
        card.add_widget(SectionLabel("WOUND ENCOUNTER", color_hex=T.BLOOD))

        inp_row = MDBoxLayout(spacing=dp(6), size_hint_y=None, height=dp(52))
        inp_row.add_widget(MDLabel(
            text="DC:", size_hint_x=None, width=dp(26),
            theme_text_color="Custom", text_color=T.k(T.TEXT_DIM)))
        self._wdc_field = MDTextField(
            hint_text="10", text="10",
            input_filter="int", mode="rectangle",
            line_color_normal=T.k(T.BORDER), size_hint_x=0.18)
        inp_row.add_widget(self._wdc_field)
        inp_row.add_widget(MDLabel(
            text="Dmg:", size_hint_x=None, width=dp(34),
            theme_text_color="Custom", text_color=T.k(T.TEXT_DIM)))
        self._dmg_field = MDTextField(
            hint_text="0", text="0",
            input_filter="int", mode="rectangle",
            line_color_normal=T.k(T.BORDER), size_hint_x=0.18)
        inp_row.add_widget(self._dmg_field)
        self._wenc_btn = MDRaisedButton(
            text="WOUND ENC", md_bg_color=T.k(T.BLOOD),
            size_hint_x=0.4, on_release=self._on_wound_encounter)
        inp_row.add_widget(self._wenc_btn)
        card.add_widget(inp_row)

        # Roll panel
        self._w_roll_panel = MDBoxLayout(
            orientation="vertical", spacing=dp(4),
            size_hint_y=None, height=0)
        self._w_roll_panel.opacity = 0

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

    # ── Build: Wounds Card ────────────────────────────────────────────────────

    def _build_wounds_card(self) -> BorderCard:
        card = BorderCard(border_hex=T.BLOOD)

        card.add_widget(SectionLabel("ADD WOUND", color_hex=T.BLOOD))
        self._desc_field = MDTextField(
            hint_text="Wound description (blank = random)",
            mode="rectangle", line_color_normal=T.k(T.BORDER),
            size_hint_y=None, height=dp(52))
        self._desc_field.bind(on_text_validate=self._on_add_minor)
        card.add_widget(self._desc_field)

        btn_row = MDBoxLayout(spacing=dp(4), size_hint_y=None, height=dp(44))
        btn_row.add_widget(MDRaisedButton(
            text="+ Minor", md_bg_color=T.k(T.WOUND_MIN),
            size_hint_x=0.5, on_release=self._on_add_minor))
        btn_row.add_widget(MDRaisedButton(
            text="+ Major", md_bg_color=T.k(T.BLOOD),
            size_hint_x=0.5, on_release=self._on_add_major))
        card.add_widget(btn_row)

        rand_row = MDBoxLayout(spacing=dp(4), size_hint_y=None, height=dp(36))
        rand_row.add_widget(MDFlatButton(
            text="Random Minor",
            theme_text_color="Custom", text_color=T.k(T.WOUND_MIN),
            on_release=self._on_random_minor))
        rand_row.add_widget(MDFlatButton(
            text="Random Major",
            theme_text_color="Custom", text_color=T.k(T.BLOOD),
            on_release=self._on_random_major))
        card.add_widget(rand_row)

        # ── Minor wounds ─────────────────────────────────────────────────────
        card.add_widget(Divider(color_hex=T.WOUND_MIN))
        minor_hdr = MDBoxLayout(size_hint_y=None, height=dp(28), spacing=dp(6))
        self._minor_title = SectionLabel("MINOR WOUNDS  (0)", color_hex=T.WOUND_MIN)
        minor_hdr.add_widget(self._minor_title)
        minor_hdr.add_widget(Widget())
        minor_hdr.add_widget(MDLabel(
            text="Long Rest cures", font_style="Overline",
            theme_text_color="Custom", text_color=T.k(T.TEXT_DIM),
            size_hint_x=None, width=dp(96)))
        card.add_widget(minor_hdr)

        self._minor_list_box = MDBoxLayout(
            orientation="vertical", adaptive_height=True, spacing=dp(2))
        card.add_widget(self._minor_list_box)

        self._minor_detail = MultilineLabel(text="", color_hex=T.TEXT_DIM)
        card.add_widget(self._minor_detail)

        minor_btns = MDBoxLayout(spacing=dp(4), size_hint_y=None, height=dp(36))
        minor_btns.add_widget(MDFlatButton(
            text="Cure", theme_text_color="Custom", text_color=T.k(T.GREEN),
            on_release=self._on_cure_minor))
        minor_btns.add_widget(MDFlatButton(
            text="Remove", theme_text_color="Custom", text_color=T.k(T.TEXT_DIM),
            on_release=self._on_remove_minor))
        card.add_widget(minor_btns)

        # ── Major wounds ─────────────────────────────────────────────────────
        card.add_widget(Divider(color_hex=T.BLOOD))
        major_hdr = MDBoxLayout(size_hint_y=None, height=dp(28), spacing=dp(6))
        self._major_title = SectionLabel("MAJOR WOUNDS  (0)", color_hex=T.STAGE_4)
        major_hdr.add_widget(self._major_title)
        major_hdr.add_widget(Widget())
        major_hdr.add_widget(MDLabel(
            text="Major Restoration", font_style="Overline",
            theme_text_color="Custom", text_color=T.k(T.TEXT_DIM),
            size_hint_x=None, width=dp(120)))
        card.add_widget(major_hdr)

        self._major_list_box = MDBoxLayout(
            orientation="vertical", adaptive_height=True, spacing=dp(2))
        card.add_widget(self._major_list_box)

        self._major_detail = MultilineLabel(text="", color_hex=T.TEXT_DIM)
        card.add_widget(self._major_detail)

        major_btns = MDBoxLayout(spacing=dp(4), size_hint_y=None, height=dp(36))
        major_btns.add_widget(MDFlatButton(
            text="Cure", theme_text_color="Custom", text_color=T.k(T.GREEN),
            on_release=self._on_cure_major))
        major_btns.add_widget(MDFlatButton(
            text="Remove", theme_text_color="Custom", text_color=T.k(T.TEXT_DIM),
            on_release=self._on_remove_major))
        card.add_widget(major_btns)

        return card

    def _build_rules_panel(self) -> ExpandableSection:
        sec = ExpandableSection("Wound Rules", accent_hex=T.BLOOD)
        sec.add_content(MultilineLabel(text=WOUND_RULES_TEXT, color_hex=T.TEXT_DIM))
        return sec

    # ── Helpers ───────────────────────────────────────────────────────────────

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

    # ── Public refresh ─────────────────────────────────────────────────────────

    def refresh(self):
        app    = self._app()
        minors = app.state.minor_wounds
        majors = app.state.major_wounds

        self._minor_title.text = f"MINOR WOUNDS  ({len(minors)})"
        self._minor_list_box.clear_widgets()
        self._sel_minor        = None
        self._sel_minor_widget = None
        self._minor_detail.text = ""

        if not minors:
            self._minor_list_box.add_widget(CaptionLabel(
                "No minor wounds. Treated with a Long Rest.",
                color_hex=T.TEXT_DIM, height_dp=28))
        else:
            for i, w in enumerate(minors):
                item = ListItem(
                    primary=w.description,
                    secondary=w.effect[:60] + ("…" if len(w.effect) > 60 else ""),
                    accent_hex=T.WOUND_MIN,
                    on_tap=lambda widget, idx=i: self._on_minor_tap(widget, idx))
                self._minor_list_box.add_widget(item)

        self._major_title.text = f"MAJOR WOUNDS  ({len(majors)})"
        self._major_list_box.clear_widgets()
        self._sel_major        = None
        self._sel_major_widget = None
        self._major_detail.text = ""

        if not majors:
            self._major_list_box.add_widget(CaptionLabel(
                "No major wounds. Requires Major Restoration to cure.",
                color_hex=T.TEXT_DIM, height_dp=28))
        else:
            for i, w in enumerate(majors):
                item = ListItem(
                    primary=w.description,
                    secondary=w.effect[:60] + ("…" if len(w.effect) > 60 else ""),
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
        if diff >= 5:    verdict = "PASS by 5+"
        elif diff >= 0:  verdict = "PASS"
        elif diff >= -4: verdict = "FAIL"
        else:            verdict = "FAIL by 5+"

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

    # ── Add wound manually ────────────────────────────────────────────────────

    def _add_wound(self, severity: str, custom_desc: str = ""):
        app = self._app()
        self._push_undo()
        if custom_desc:
            desc, effect = custom_desc, "Custom wound."
        else:
            _, desc, effect = roll_random_wound(severity)
        app.state.add_wound(desc, effect, severity)
        self._log(f"{severity.title()} wound added: {desc}")
        self.refresh()
        app.refresh_all()
        self._save()

    def _on_add_minor(self, *_):
        desc = self._desc_field.text.strip()
        self._desc_field.text  = ""
        self._desc_field.focus = False
        self._add_wound("minor", custom_desc=desc)

    def _on_add_major(self, *_):
        desc = self._desc_field.text.strip()
        self._desc_field.text  = ""
        self._desc_field.focus = False
        self._add_wound("major", custom_desc=desc)

    def _on_random_minor(self, *_): self._add_wound("minor")
    def _on_random_major(self, *_): self._add_wound("major")

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
            self._minor_detail.text = f"{w.description}\n{w.timestamp}\n\n{w.effect}"

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
            self._major_detail.text = f"{w.description}\n{w.timestamp}\n\n{w.effect}"

    def _cure_or_remove(self, severity: str, idx: int | None):
        if idx is None:
            self._snack(f"Select a {severity} wound.", T.BORDER); return
        app    = self._app()
        wounds = [w for w in app.state.wounds if w.severity == severity]
        if idx >= len(wounds): return
        target = wounds[idx]
        self._push_undo()
        app.state.wounds.remove(target)
        self._log(f"{severity.title()} wound cured: {target.description}")
        if severity == "minor":
            self._sel_minor        = None
            self._sel_minor_widget = None
        else:
            self._sel_major        = None
            self._sel_major_widget = None
        self.refresh()
        app.refresh_all()
        self._save()

    def _on_cure_minor(self, *_):   self._cure_or_remove("minor", self._sel_minor)
    def _on_remove_minor(self, *_): self._cure_or_remove("minor", self._sel_minor)
    def _on_cure_major(self, *_):   self._cure_or_remove("major", self._sel_major)
    def _on_remove_major(self, *_): self._cure_or_remove("major", self._sel_major)
