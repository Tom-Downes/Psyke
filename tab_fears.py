"""
Tab 1: Fears & Fear Encounter
Full FSM-6 parity:
  - Severity naming (Low/Moderate/High/Extreme)
  - Desensitization tracker (4 rung buttons, teal)
  - Desensitization effects card
  - DC auto-fill from desens rung
  - Confront → desens +1
  - Avoid → desens -1
  - Extreme Severity: +1 exhaustion on encounter start
  - Extreme Severity Avoid: add random new fear
"""
from __future__ import annotations

from kivy.app import App
from kivy.clock import Clock
from kivy.graphics import Color, Line, Rectangle
from kivy.metrics import dp
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.gridlayout import GridLayout
from kivy.uix.scrollview import ScrollView
from kivy.uix.widget import Widget

from kivymd.uix.boxlayout import MDBoxLayout
from kivymd.uix.button import MDFlatButton, MDIconButton, MDRaisedButton
from kivymd.uix.label import MDLabel
from kivymd.uix.snackbar import MDSnackbar
from kivymd.uix.textfield import MDTextField

from models import (
    FEAR_STAGES, DESENS_DC, DESENS_NAMES, DESENS_DESCS, DESENS_RUNG_COLORS,
    DESENS_COLOR, DESENS_COLOR_DK,
    FEAR_ENC_DC, EncounterPhase, EncounterState,
    roll_d, clamp, FEAR_RULES_TEXT
)
from ui_utils import (
    BorderCard, AccentCard, Divider,
    SectionLabel, CaptionLabel, MultilineLabel,
    ListItem, ExpandableSection
)
import theme as T

# Roll panel height when visible
_ROLL_H = dp(20 + 48 + 44 + 44 + 20) + dp(4) * 4


# ────────────────────────────────────────────────────────────────────────────
# SEVERITY CARD  (replaces old StageCard — uses severity naming)
# ────────────────────────────────────────────────────────────────────────────

class SeverityCard(BoxLayout):
    """Single clickable severity card (2×2 grid)."""

    def __init__(self, stage_num: int, on_select, **kwargs):
        super().__init__(orientation="vertical", **kwargs)
        self.stage_num  = stage_num
        self._on_select = on_select
        self._selected  = False
        info = FEAR_STAGES[stage_num]
        self._color = info.color
        self.size_hint_y = None
        self.height = dp(60)
        self.padding = dp(2)

        inner = MDBoxLayout(orientation="horizontal")
        self._bar = Widget(size_hint_x=None, width=dp(4))

        text_col = MDBoxLayout(orientation="vertical",
                               padding=[dp(6), dp(4), dp(4), dp(4)],
                               spacing=dp(2))
        self._name_lbl = MDLabel(
            text=f"{info.name}  ·  {info.dice}d4",
            font_style="Caption",
            theme_text_color="Custom",
            text_color=T.k(info.color),
            bold=True,
            size_hint_y=None, height=dp(22))
        short_desc = info.desc[:42] + ("…" if len(info.desc) > 42 else "")
        self._desc_lbl = MDLabel(
            text=short_desc,
            font_style="Overline",
            theme_text_color="Custom",
            text_color=T.k(T.TEXT_DIM),
            size_hint_y=None, height=dp(16))
        text_col.add_widget(self._name_lbl)
        text_col.add_widget(self._desc_lbl)
        inner.add_widget(self._bar)
        inner.add_widget(text_col)
        self.add_widget(inner)

        self.bind(pos=self._draw_bg, size=self._draw_bg)
        Clock.schedule_once(self._draw_bg)

    def set_selected(self, sel: bool):
        self._selected = sel
        self._name_lbl.bold = sel
        self._draw_bg()

    def _draw_bg(self, *_):
        from models import hex_lerp
        self.canvas.before.clear()
        with self.canvas.before:
            bg = hex_lerp(T.BG_INSET, self._color, 0.22) if self._selected else T.BG_INSET
            Color(*T.k(bg))
            Rectangle(pos=self.pos, size=self.size)
            Color(*T.k(self._color if self._selected else T.BORDER))
            Line(rectangle=(self.x, self.y, self.width, self.height), width=1)
        self._bar.canvas.clear()
        with self._bar.canvas:
            Color(*T.k(self._color))
            Rectangle(pos=self._bar.pos, size=self._bar.size)

    def on_touch_down(self, touch):
        if self.collide_point(*touch.pos):
            self._on_select(self.stage_num)
            return True
        return super().on_touch_down(touch)


# ────────────────────────────────────────────────────────────────────────────
# DESENS RUNG BUTTON
# ────────────────────────────────────────────────────────────────────────────

class DesensRungBtn(BoxLayout):
    """Single tappable desensitization rung button."""

    def __init__(self, rung: int, on_select, **kwargs):
        super().__init__(orientation="vertical", **kwargs)
        self.rung       = rung
        self._on_select = on_select
        self._selected  = False
        self._color     = DESENS_RUNG_COLORS[rung]
        self.size_hint_y = None
        self.height = dp(56)
        self.padding = dp(2)

        inner = MDBoxLayout(orientation="vertical",
                            padding=[dp(6), dp(4), dp(4), dp(4)],
                            spacing=dp(2))
        self._rung_lbl = MDLabel(
            text=f"{DESENS_NAMES[rung].split()[0]}",  # "Low", "Moderate", etc.
            font_style="Caption", bold=True,
            theme_text_color="Custom", text_color=T.k(self._color),
            size_hint_y=None, height=dp(20))
        self._dc_lbl = MDLabel(
            text=f"Rung {rung}  ·  DC {DESENS_DC[rung]}",
            font_style="Overline",
            theme_text_color="Custom", text_color=T.k(T.TEXT_DIM),
            size_hint_y=None, height=dp(16))
        inner.add_widget(self._rung_lbl)
        inner.add_widget(self._dc_lbl)
        self.add_widget(inner)

        self.bind(pos=self._draw, size=self._draw)
        Clock.schedule_once(self._draw)

    def set_selected(self, sel: bool):
        self._selected = sel
        self._rung_lbl.bold = sel
        self._draw()

    def _draw(self, *_):
        from models import hex_lerp
        self.canvas.before.clear()
        with self.canvas.before:
            bg = hex_lerp(T.BG_INSET, self._color, 0.25) if self._selected else T.BG_INSET
            Color(*T.k(bg))
            Rectangle(pos=self.pos, size=self.size)
            Color(*T.k(self._color if self._selected else T.BORDER))
            Line(rectangle=(self.x, self.y, self.width, self.height), width=1)

    def on_touch_down(self, touch):
        if self.collide_point(*touch.pos):
            self._on_select(self.rung)
            return True
        return super().on_touch_down(touch)


# ────────────────────────────────────────────────────────────────────────────
# FEARS TAB
# ────────────────────────────────────────────────────────────────────────────

class FearsTab(ScrollView):

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.do_scroll_x = False
        self._enc   = EncounterState()
        self._stage = 1
        self._severity_cards: dict[int, SeverityCard] = {}
        self._desens_btns: dict[int, DesensRungBtn]   = {}
        self._selected_fear: str | None = None
        self._sel_fear_widget: ListItem | None = None
        self._fear_items: dict[str, ListItem] = {}

        # Pulse animation state for desens card
        self._desens_pulse       = 0.0
        self._desens_pulse_dir   = 1
        self._desens_pulse_evt   = None
        self._desens_pulse_remain = 0

        root = MDBoxLayout(
            orientation="vertical",
            padding=dp(10),
            spacing=dp(8),
            size_hint_y=None,
            adaptive_height=True
        )
        self.add_widget(root)

        root.add_widget(self._build_encounter_card())
        root.add_widget(self._build_severity_selector())
        root.add_widget(self._build_severity_effects())
        root.add_widget(self._build_desens_tracker())
        root.add_widget(self._build_desens_effects())
        root.add_widget(self._build_fear_add_row())
        root.add_widget(self._build_fear_list())
        root.add_widget(self._build_rules_panel())

    # ── Build: Encounter Card ────────────────────────────────────────────────

    def _build_encounter_card(self) -> BorderCard:
        card = BorderCard(border_hex=T.GOLD)
        card.add_widget(SectionLabel("FEAR ENCOUNTER", color_hex=T.GOLD))

        self._enc_fear_lbl = CaptionLabel(
            "Select a fear from the list below first.",
            color_hex=T.TEXT_DIM, height_dp=20)
        card.add_widget(self._enc_fear_lbl)

        dc_row = MDBoxLayout(spacing=dp(8), size_hint_y=None, height=dp(48))
        dc_row.add_widget(MDLabel(
            text="DC:", size_hint_x=None, width=dp(26),
            theme_text_color="Custom", text_color=T.k(T.TEXT_DIM)))
        self._dc_field = MDTextField(
            hint_text=str(FEAR_ENC_DC), text=str(FEAR_ENC_DC),
            size_hint_x=0.22, input_filter="int",
            mode="rectangle", line_color_normal=T.k(T.BORDER))
        dc_row.add_widget(self._dc_field)
        self._enc_btn = MDRaisedButton(
            text="ENCOUNTER",
            md_bg_color=T.k(T.BLOOD),
            size_hint_x=0.72,
            disabled=True,
            on_release=self._on_encounter)
        dc_row.add_widget(self._enc_btn)
        card.add_widget(dc_row)

        # Roll panel (hidden until encounter is triggered)
        self._roll_panel = MDBoxLayout(
            orientation="vertical", spacing=dp(4),
            size_hint_y=None, height=0)
        self._roll_panel.opacity = 0

        self._roll_lbl = MDLabel(
            text="", theme_text_color="Custom",
            text_color=T.k(T.TEXT_DIM), font_style="Caption",
            size_hint_y=None, height=dp(20))
        self._roll_big = MDLabel(
            text="", bold=True,
            theme_text_color="Custom", text_color=T.k(T.TEXT_BRIGHT),
            font_style="H5", size_hint_y=None, height=dp(48))
        self._roll_panel.add_widget(self._roll_lbl)
        self._roll_panel.add_widget(self._roll_big)

        btn_row1 = MDBoxLayout(spacing=dp(4), size_hint_y=None, height=dp(44))
        self._fail_btn = MDRaisedButton(
            text="Failed Save", md_bg_color=T.k(T.RED),
            size_hint_x=0.5, on_release=self._on_fail)
        self._pass_btn = MDRaisedButton(
            text="Passed", md_bg_color=T.k(T.BLUE),
            size_hint_x=0.5, on_release=self._on_pass)
        btn_row1.add_widget(self._fail_btn)
        btn_row1.add_widget(self._pass_btn)
        self._roll_panel.add_widget(btn_row1)

        btn_row2 = MDBoxLayout(spacing=dp(4), size_hint_y=None, height=dp(44))
        self._push_btn = MDRaisedButton(
            text="Confront", md_bg_color=T.k(T.BLOOD),
            size_hint_x=0.5, disabled=True, on_release=self._on_push)
        self._avoid_btn = MDRaisedButton(
            text="Avoid", md_bg_color=T.k(T.GREEN),
            size_hint_x=0.5, disabled=True, on_release=self._on_avoid)
        btn_row2.add_widget(self._push_btn)
        btn_row2.add_widget(self._avoid_btn)
        self._roll_panel.add_widget(btn_row2)

        self._pend_lbl = MDLabel(
            text="", theme_text_color="Custom",
            text_color=T.k(T.TEXT_DIM), font_style="Caption",
            size_hint_y=None, height=dp(20))
        self._roll_panel.add_widget(self._pend_lbl)
        card.add_widget(self._roll_panel)
        return card

    # ── Build: Severity Selector ─────────────────────────────────────────────

    def _build_severity_selector(self) -> BorderCard:
        card = BorderCard(border_hex=T.GOLD_DK)
        card.add_widget(SectionLabel("SEVERITY", color_hex=T.GOLD))

        grid = GridLayout(cols=2, spacing=dp(4),
                          size_hint_y=None,
                          row_default_height=dp(60),
                          row_force_default=True)
        grid.bind(minimum_height=grid.setter("height"))
        for s in range(1, 5):
            sc = SeverityCard(s, self._on_severity_select)
            self._severity_cards[s] = sc
            grid.add_widget(sc)
        card.add_widget(grid)
        self._update_severity_visuals()
        return card

    # ── Build: Severity Effects Card ─────────────────────────────────────────

    def _build_severity_effects(self) -> AccentCard:
        self._sev_eff_card = AccentCard(accent_hex=T.STAGE_1)
        self._sev_title = MDLabel(
            text="Low Severity  —  Low Severity",
            bold=True,
            theme_text_color="Custom", text_color=T.k(T.STAGE_1),
            font_style="Body2", size_hint_y=None, height=dp(22))
        self._sev_dice = MDLabel(
            text="Fail → roll 1d4  |  Pass → encounter ends",
            theme_text_color="Custom", text_color=T.k(T.TEXT_DIM),
            font_style="Caption", size_hint_y=None, height=dp(18))
        self._sev_detail = MultilineLabel(
            text=FEAR_STAGES[1].desc, color_hex=T.TEXT_DIM)
        self._sev_eff_card.add_widget(self._sev_title)
        self._sev_eff_card.add_widget(self._sev_dice)
        self._sev_eff_card.add_widget(self._sev_detail)
        return self._sev_eff_card

    # ── Build: Desensitization Tracker ───────────────────────────────────────

    def _build_desens_tracker(self) -> BorderCard:
        card = BorderCard(border_hex=T.DESENS)
        card.add_widget(SectionLabel("DESENSITIZATION", color_hex=T.DESENS))

        # 4 rung buttons in a horizontal row
        row = MDBoxLayout(spacing=dp(4), size_hint_y=None, height=dp(56))
        for r in range(1, 5):
            btn = DesensRungBtn(r, self._on_desens_select)
            btn.size_hint_x = 0.25
            self._desens_btns[r] = btn
            row.add_widget(btn)
        card.add_widget(row)
        self._update_desens_visuals()
        return card

    # ── Build: Desensitization Effects Card ──────────────────────────────────

    def _build_desens_effects(self) -> AccentCard:
        self._desens_eff_card = AccentCard(accent_hex=T.DESENS)
        self._desens_title = MDLabel(
            text="Low Desensitization  —  Rung 1",
            bold=True,
            theme_text_color="Custom", text_color=T.k(T.DESENS),
            font_style="Body2", size_hint_y=None, height=dp(22))
        self._desens_dc_lbl = MDLabel(
            text="DC 16",
            theme_text_color="Custom", text_color=T.k(T.DESENS_LT),
            font_style="Caption", size_hint_y=None, height=dp(18))
        self._desens_detail = MultilineLabel(
            text=DESENS_DESCS[1], color_hex=T.TEXT_DIM)
        self._desens_eff_card.add_widget(self._desens_title)
        self._desens_eff_card.add_widget(self._desens_dc_lbl)
        self._desens_eff_card.add_widget(self._desens_detail)
        return self._desens_eff_card

    # ── Build: Fear Add Row ──────────────────────────────────────────────────

    def _build_fear_add_row(self) -> MDBoxLayout:
        row = MDBoxLayout(spacing=dp(6), size_hint_y=None, height=dp(56))
        self._fear_input = MDTextField(
            hint_text="Fear name…", mode="rectangle",
            line_color_normal=T.k(T.BORDER), size_hint_x=0.55)
        self._fear_input.bind(
            on_text_validate=self._on_add_fear)
        sug_btn = MDIconButton(
            icon="dice-multiple",
            theme_icon_color="Custom", icon_color=T.k(T.GOLD),
            on_release=self._on_suggest)
        add_btn = MDRaisedButton(
            text="Add Fear", md_bg_color=T.k(T.GOLD_DK),
            size_hint_x=None, width=dp(90),
            on_release=self._on_add_fear)
        row.add_widget(self._fear_input)
        row.add_widget(sug_btn)
        row.add_widget(add_btn)
        return row

    # ── Build: Fear List Card ────────────────────────────────────────────────

    def _build_fear_list(self) -> BorderCard:
        card = BorderCard(border_hex=T.GOLD)
        hdr = MDBoxLayout(size_hint_y=None, height=dp(32), spacing=dp(8))
        hdr.add_widget(SectionLabel("FEARS", color_hex=T.GOLD))
        hdr.add_widget(Widget())
        rm_btn = MDIconButton(
            icon="trash-can-outline",
            theme_icon_color="Custom", icon_color=T.k(T.RED),
            size_hint_x=None, width=dp(40),
            on_release=self._on_remove_fear)
        hdr.add_widget(rm_btn)
        card.add_widget(hdr)

        self._fear_list_box = MDBoxLayout(
            orientation="vertical", adaptive_height=True, spacing=dp(2))
        card.add_widget(self._fear_list_box)
        return card

    # ── Build: Rules Panel ───────────────────────────────────────────────────

    def _build_rules_panel(self) -> ExpandableSection:
        sec = ExpandableSection("Fear Rules", accent_hex=T.GOLD_DK)
        sec.add_content(MultilineLabel(text=FEAR_RULES_TEXT, color_hex=T.TEXT_DIM))
        return sec

    # ── Internal helpers ─────────────────────────────────────────────────────

    def _app(self): return App.get_running_app()

    def _push_undo(self):
        app = self._app()
        app.undo_stack.push(app.state, app.fm)

    def _save(self):
        app = self._app()
        app.save_manager.save(app.state, app.fm, app.char_name, app.enc_history)

    def _log(self, msg: str):
        app = self._app()
        app.enc_history.append(msg)
        if hasattr(app, "session_log"):
            app.session_log.add_entry(msg)

    def _snack(self, msg: str, color=T.BG_CARD):
        MDSnackbar(
            MDLabel(text=msg, theme_text_color="Custom", text_color=(1, 1, 1, 1)),
            md_bg_color=T.k(color), duration=2.5
        ).open()

    def _show_roll_panel(self):
        self._roll_panel.height  = _ROLL_H
        self._roll_panel.opacity = 1
        Clock.schedule_once(lambda dt: setattr(self, "scroll_y", 1), 0.05)

    def _end_enc(self):
        self._enc.reset()
        self._roll_panel.height  = 0
        self._roll_panel.opacity = 0
        self._push_btn.disabled  = True
        self._avoid_btn.disabled = True
        self._pend_lbl.text      = ""

    def _update_severity_visuals(self):
        for s, card in self._severity_cards.items():
            card.set_selected(s == self._stage)
        info = FEAR_STAGES[self._stage]
        if hasattr(self, "_sev_title"):
            self._sev_title.text = f"{info.name}  —  {info.dice}d4"
            self._sev_title.text_color = T.k(info.color)
            self._sev_dice.text = f"Fail → roll {info.dice}d4  |  Pass → encounter ends"
            self._sev_detail.text = info.desc
        if hasattr(self, "_sev_eff_card"):
            self._sev_eff_card.set_accent(info.color)

    def _update_desens_visuals(self):
        """Update desens rung button highlights for the selected fear."""
        app = self._app()
        name = self._selected_fear
        cur_rung = app.fm.get_desens(name) if name else 1
        for r, btn in self._desens_btns.items():
            btn.set_selected(r == cur_rung)
        self._refresh_desens_effects(cur_rung)

    def _refresh_desens_effects(self, rung: int = 1):
        """Update the desensitization effects card text."""
        if not hasattr(self, "_desens_title"):
            return
        color = DESENS_RUNG_COLORS.get(rung, T.DESENS)
        self._desens_title.text = f"{DESENS_NAMES[rung]}  —  Rung {rung}"
        self._desens_title.text_color = T.k(color)
        self._desens_dc_lbl.text = f"DC {DESENS_DC[rung]}"
        self._desens_detail.text = DESENS_DESCS[rung]
        if hasattr(self, "_desens_eff_card"):
            self._desens_eff_card.set_accent(color)

    def _pulse_desens_card(self, cycles: int = 5):
        """Start pulse animation on desens effects card (like the desktop version)."""
        if self._desens_pulse_evt:
            self._desens_pulse_evt.cancel()
        self._desens_pulse        = 0.0
        self._desens_pulse_dir    = 1
        self._desens_pulse_remain = cycles * 2
        self._desens_pulse_evt    = Clock.schedule_interval(
            self._desens_pulse_step, 1 / 20)

    def _desens_pulse_step(self, dt):
        self._desens_pulse += self._desens_pulse_dir * 0.15
        if self._desens_pulse >= 1.0:
            self._desens_pulse = 1.0; self._desens_pulse_dir = -1
        elif self._desens_pulse <= 0.0:
            self._desens_pulse = 0.0; self._desens_pulse_dir = 1
            self._desens_pulse_remain -= 1
            if self._desens_pulse_remain <= 0:
                self._desens_pulse_evt.cancel()
                self._desens_pulse_evt = None
        # Pulse: briefly brighten the desens effects card accent
        name  = self._selected_fear
        app   = self._app()
        rung  = app.fm.get_desens(name) if name else 1
        from models import hex_lerp
        base  = DESENS_RUNG_COLORS.get(rung, T.DESENS)
        pulsed = hex_lerp(base, T.TEXT_BRIGHT, self._desens_pulse * 0.4)
        if hasattr(self, "_desens_eff_card"):
            self._desens_eff_card.set_accent(pulsed)

    def _autofill_dc(self):
        """Set DC field from current fear's desens DC."""
        app = self._app()
        name = self._selected_fear
        if name:
            rung = app.fm.get_desens(name)
            self._dc_field.text = str(DESENS_DC.get(rung, FEAR_ENC_DC))

    # ── Public refresh ────────────────────────────────────────────────────────

    def refresh(self):
        app   = self._app()
        names = app.fm.sorted_names
        self._fear_list_box.clear_widgets()
        self._fear_items.clear()
        self._sel_fear_widget = None

        if not names:
            self._fear_list_box.add_widget(CaptionLabel(
                "No fears tracked yet. Type a name above and tap Add Fear.",
                color_hex=T.TEXT_DIM, height_dp=36))
        else:
            for name in names:
                stage = app.fm.get_stage(name)
                rung  = app.fm.get_desens(name)
                info  = FEAR_STAGES[stage]
                sev_short = info.name.split()[0]          # "Low", "Moderate", etc.
                des_short = DESENS_NAMES[rung].split()[0] # "Low", "Moderate", etc.
                item = ListItem(
                    primary=name,
                    secondary=f"{sev_short} Severity  ·  {des_short} Desens  ·  {info.dice}d4",
                    accent_hex=info.color,
                    on_tap=lambda widget, n=name: self._on_fear_tap(widget, n))
                self._fear_list_box.add_widget(item)
                self._fear_items[name] = item

        # Handle removed selected fear
        if self._selected_fear and self._selected_fear not in app.fm.fears:
            self._selected_fear   = None
            self._sel_fear_widget = None
            self._enc_fear_lbl.text       = "Select a fear from the list below first."
            self._enc_fear_lbl.text_color = T.k(T.TEXT_DIM)
            self._enc_btn.disabled = True

        # Auto-select first fear if nothing selected
        if not self._selected_fear and names:
            self._selected_fear = names[0]

        # Restore selection highlight
        if self._selected_fear and self._selected_fear in self._fear_items:
            w = self._fear_items[self._selected_fear]
            w.set_selected(True, persist=True)
            self._sel_fear_widget = w
            stage = app.fm.get_stage(self._selected_fear)
            info  = FEAR_STAGES[stage]
            self._enc_fear_lbl.text = (
                f"Encountering: {self._selected_fear}  "
                f"({info.name})")
            self._enc_fear_lbl.text_color = T.k(info.color)
            self._enc_btn.disabled = False
            self._stage = stage
            self._update_severity_visuals()
            self._update_desens_visuals()
            self._autofill_dc()
        else:
            self._enc_btn.disabled = True

    # ── Event: Severity selection ─────────────────────────────────────────────

    def _on_severity_select(self, s: int):
        self._stage = s
        self._update_severity_visuals()
        if self._selected_fear:
            app = self._app()
            self._push_undo()
            app.fm.set_stage(self._selected_fear, s)
            self.refresh()
            self._save()

    # ── Event: Desens rung selection ──────────────────────────────────────────

    def _on_desens_select(self, rung: int):
        if not self._selected_fear:
            self._snack("Select a fear first.", T.BORDER); return
        app = self._app()
        self._push_undo()
        app.fm.set_desens(self._selected_fear, rung)
        self._update_desens_visuals()
        self._autofill_dc()
        self._log(f"  {self._selected_fear}: Desensitization → {DESENS_NAMES[rung]}")
        self._save()

    # ── Event: Fear tap ───────────────────────────────────────────────────────

    def _on_fear_tap(self, widget: ListItem, name: str):
        if self._sel_fear_widget and self._sel_fear_widget is not widget:
            self._sel_fear_widget.set_selected(False, persist=False)
        self._selected_fear   = name
        self._sel_fear_widget = widget
        widget.set_selected(True, persist=True)
        app   = self._app()
        stage = app.fm.get_stage(name)
        rung  = app.fm.get_desens(name)
        info  = FEAR_STAGES[stage]
        self._enc_fear_lbl.text       = f"Encountering: {name}  ({info.name})"
        self._enc_fear_lbl.text_color = T.k(info.color)
        self._enc_btn.disabled        = False
        self._stage = stage
        self._update_severity_visuals()
        self._update_desens_visuals()
        self._autofill_dc()

    # ── Event: Add fear ───────────────────────────────────────────────────────

    def _on_add_fear(self, *_):
        name = self._fear_input.text.strip()
        if not name: return
        app = self._app()
        self._push_undo()
        err = app.fm.add(name)
        if err:
            self._snack(err, T.RED_DK); return
        self._fear_input.text = ""
        self._fear_input.focus = False
        self._log(f"Fear added: {name}")
        self.refresh()
        self._save()

    def _on_suggest(self, *_):
        s = self._app().fm.suggest()
        if s: self._fear_input.text = s

    def _on_remove_fear(self, *_):
        if not self._selected_fear:
            self._snack("Select a fear first.", T.BORDER); return
        app = self._app()
        self._push_undo()
        name = self._selected_fear
        app.fm.remove(name)
        self._log(f"Fear removed: {name}")
        self._selected_fear   = None
        self._sel_fear_widget = None
        self.refresh()
        self._save()

    # ── Event: Encounter ─────────────────────────────────────────────────────

    def _on_encounter(self, *_):
        if not self._selected_fear:
            self._snack("Select a fear from the list.", T.BORDER); return
        app = self._app()
        if self._enc.active:
            self._snack("Encounter already active.", T.BORDER); return

        name  = self._selected_fear
        stage = app.fm.get_stage(name)
        rung  = app.fm.get_desens(name)
        self._stage = stage
        self._update_severity_visuals()

        self._enc.fear_name  = name
        self._enc.fear_stage = stage
        self._enc.phase      = EncounterPhase.AWAITING_SAVE

        try:
            dc = int(self._dc_field.text.strip() or str(FEAR_ENC_DC))
        except ValueError:
            dc = FEAR_ENC_DC

        # ── EXTREME SEVERITY: apply +1 exhaustion before roll ────────────────
        if stage == 4:
            self._push_undo()
            app.state.exhaustion = int(clamp(app.state.exhaustion + 1, 0, 6))
            self._log(f"Extreme Severity — +1 Exhaustion applied before encounter")
            app.refresh_all()

        d20      = roll_d(20)[0]
        wis_save = d20 + app.state.wis_mod
        self._enc.wis_save_total = wis_save

        info = FEAR_STAGES[stage]
        self._log(f"=== ENCOUNTER: {name} ({info.name}) ===")
        self._log(f"Desens: {DESENS_NAMES[rung]}  ·  Rung {rung}  ·  DC {dc}")
        self._log(f"WIS Save: d20({d20}) + {app.state.wis_mod:+d} = {wis_save} vs DC {dc}")

        self._show_roll_panel()

        if wis_save >= dc:
            self._roll_lbl.text       = f"WIS Save: {wis_save} vs DC {dc}"
            self._roll_big.text       = "PASSED!"
            self._roll_big.text_color = T.k(T.STAGE_1)
            self._pend_lbl.text       = "Encounter ended."
            self._log("Result: PASSED — encounter ends.")
            self._enc.phase          = EncounterPhase.AWAITING_CHOICE
            self._fail_btn.disabled  = True
            self._pass_btn.disabled  = False
            self._push_btn.disabled  = True
            self._avoid_btn.disabled = True
        else:
            rolls = roll_d(4, info.dice)
            total = sum(rolls)
            self._enc.roll_total = total
            rt = "+".join(map(str, rolls))
            self._roll_lbl.text       = f"WIS Save: {wis_save} vs DC {dc} — FAILED"
            self._roll_big.text       = f"{total}"
            self._roll_big.text_color = T.k(T.BLOOD)
            self._pend_lbl.text       = f"Sanity at stake: {total}  ({rt})"
            self._log(f"FAILED — {info.dice}d4: {rt} = {total} sanity at stake")
            self._enc.phase          = EncounterPhase.AWAITING_CHOICE
            self._fail_btn.disabled  = False
            self._pass_btn.disabled  = True
            self._push_btn.disabled  = False
            self._avoid_btn.disabled = False

    # ── Event: Pass ──────────────────────────────────────────────────────────

    def _on_pass(self, *_):
        self._log("Passed — encounter ends cleanly.")
        self._end_enc()
        self._save()

    # ── Event: Fail (shortcut → Confront) ────────────────────────────────────

    def _on_fail(self, *_):
        self._on_push()

    # ── Event: Confront (Push Through) ───────────────────────────────────────

    def _on_push(self, *_):
        app  = self._app()
        amt  = self._enc.roll_total or 0
        name = self._enc.fear_name
        self._push_undo()
        threshs = app.state.apply_loss(amt)
        # Desensitization rung +1 (harder to encounter next time)
        new_rung = app.fm.incr_desens(name)
        self._log(f"Confront — lost {amt} sanity  |  {name}: desens → {DESENS_NAMES[new_rung]}")
        self._handle_thresholds(threshs)
        self._update_desens_visuals()
        self._autofill_dc()
        self._pulse_desens_card()
        app.refresh_all()
        self._end_enc()
        self._save()

    # ── Event: Avoid ─────────────────────────────────────────────────────────

    def _on_avoid(self, *_):
        app   = self._app()
        amt   = self._enc.roll_total or 0
        name  = self._enc.fear_name
        stage = self._enc.fear_stage or 1
        self._push_undo()
        app.state.apply_recovery(amt)
        new_stage = app.fm.increment_stage(name)   # severity +1
        new_rung  = app.fm.decr_desens(name)        # desens rung -1 (easier DC)
        self._log(
            f"Avoided — recovered {amt} sanity  |  "
            f"{name}: severity {stage}→{new_stage}  |  "
            f"desens → {DESENS_NAMES[new_rung]}")
        # ── EXTREME SEVERITY AVOID: add random new fear ──────────────────────
        if stage == 4:
            new_fear = app.fm.add_random()
            if new_fear:
                self._log(f"Extreme Avoid — panic: new fear added: {new_fear}")
                self._snack(f"Panic! New fear: {new_fear}", T.STAGE_4)
        self._update_desens_visuals()
        self._autofill_dc()
        self._pulse_desens_card()
        app.refresh_all()
        self.refresh()
        self._end_enc()
        self._save()

    # ── Threshold handling ────────────────────────────────────────────────────

    def _handle_thresholds(self, threshs):
        app = self._app()
        for label, kind in threshs:
            if kind == "zero":
                self._log(f"WARNING: {label}")
                continue
            m = app.state.add_madness(kind)
            self._log(
                f"THRESHOLD: {label} → {m.kind_label} madness: "
                f"[{m.roll_range}] {m.name}  —  {m.effect[:50]}")
        if threshs:
            app.refresh_all()

    def cancel_encounter(self):
        if self._enc.active:
            self._log("Encounter cancelled.")
            self._end_enc()
