"""
Tab 1: Fears & Fear Encounter  (V2 — redesigned layout)

Two-page swipeable layout:
  Page 0 — Main:   Encounter card, Add Fear, Fear List, Rules
  Page 1 — Detail: Fear Severity, Fear Desensitization

Swipe left/right to move between pages.
"""
from __future__ import annotations

from kivy.app import App
from kivy.clock import Clock
from kivy.graphics import Color, Rectangle, RoundedRectangle
from kivy.metrics import dp
from kivy.uix.scrollview import ScrollView
from kivy.uix.widget import Widget

from kivymd.uix.boxlayout import MDBoxLayout
from kivymd.uix.button import MDFlatButton, MDIconButton, MDRaisedButton
from kivymd.uix.label import MDLabel
from kivymd.uix.snackbar import MDSnackbar

from models import (
    FEAR_STAGES, DESENS_DC, DESENS_NAMES, DESENS_DESCS, DESENS_RUNG_COLORS,
    DESENS_COLOR, DESENS_COLOR_DK, THRESHOLDS,
    FEAR_ENC_DC, EncounterPhase, EncounterState,
    roll_d, clamp, FEAR_RULES_TEXT
)
from ui_utils import (
    BorderCard, Divider, HopeButton,
    SectionLabel, CaptionLabel,
    ListItem, ExpandableSection, DescriptionCard, PageDot, themed_field,
    populate_rules_section
)
import theme as T


# ────────────────────────────────────────────────────────────────────────────
# FEARS TAB
# ────────────────────────────────────────────────────────────────────────────

class FearsTab(MDBoxLayout):

    def __init__(self, **kwargs):
        kwargs.setdefault("orientation", "vertical")
        super().__init__(**kwargs)

        self._enc   = EncounterState()
        self._stage = 1
        self._sev_items: dict[int, tuple]    = {}
        self._desens_items: dict[int, tuple] = {}
        self._selected_fear: str | None      = None
        self._sel_fear_widget: ListItem | None = None
        self._fear_items: dict[str, ListItem] = {}
        self._save_confirmed = False
        self._sev_expanded   = False
        self._des_expanded   = False

        # ── Page state ──────────────────────────────────────────────────────
        self._page = 0   # 0 = Main, 1 = Severity & Desens

        # Page indicator bar
        self.add_widget(self._build_page_indicator())

        # Content area — holds exactly one ScrollView at a time
        self._content_area = MDBoxLayout(orientation="vertical")
        self.add_widget(self._content_area)

        # ── Page 0 (Main) ───────────────────────────────────────────────────
        self._sv0 = ScrollView(do_scroll_x=False)
        p0 = MDBoxLayout(
            orientation="vertical",
            padding=dp(10), spacing=dp(8),
            size_hint_y=None, adaptive_height=True)
        p0.add_widget(self._build_encounter_card())
        p0.add_widget(self._build_fear_add_row())
        p0.add_widget(self._build_fear_list())
        p0.add_widget(self._build_rules_panel())
        self._sv0.add_widget(p0)

        # ── Page 1 (Detail) ─────────────────────────────────────────────────
        self._sv1 = ScrollView(do_scroll_x=False)
        p1 = MDBoxLayout(
            orientation="vertical",
            padding=dp(10), spacing=dp(8),
            size_hint_y=None, adaptive_height=True)

        # ── Selected fear context banner ─────────────────────────────────────
        self._effects_banner = MDBoxLayout(
            orientation="vertical", spacing=dp(6),
            padding=[dp(14), dp(10), dp(14), dp(10)],
            size_hint_y=None, adaptive_height=True)
        with self._effects_banner.canvas.before:
            Color(*T.k(T.GOLD, 0.70))
            _ban_bd = RoundedRectangle(radius=[dp(10)])
            Color(*T.k(T.BG_HOVER))
            _ban_bg = RoundedRectangle(radius=[dp(9)])
            Color(*T.k(T.GOLD, 0.06))
            _ban_tint = RoundedRectangle(radius=[dp(9)])
        def _upd_ban(w, *_):
            _ban_bd.pos    = w.pos;   _ban_bd.size   = w.size
            _ban_bg.pos    = (w.x+2, w.y+2)
            _ban_bg.size   = (max(0, w.width-4), max(0, w.height-4))
            _ban_tint.pos  = (w.x+2, w.y+2)
            _ban_tint.size = (max(0, w.width-4), max(0, w.height-4))
        self._effects_banner.bind(pos=_upd_ban, size=_upd_ban)

        # "Selected Fear:" label
        self._effects_banner.add_widget(MDLabel(
            text="Selected Fear:",
            theme_text_color="Custom", text_color=T.k(T.TEXT_DIM),
            font_style="Caption",
            size_hint_y=None, height=dp(16)))

        # Fear name — Subtitle1
        self._effects_fear_name = MDLabel(
            text="", markup=True, bold=True,
            theme_text_color="Custom", text_color=T.k(T.TEXT_BRIGHT),
            font_style="Subtitle1",
            size_hint_y=None, height=dp(28))
        self._effects_banner.add_widget(self._effects_fear_name)

        # Thin gold divider
        self._effects_banner.add_widget(Divider(color_hex=T.GOLD_DK))

        # Severity badge (stacked above desens)
        self._effects_sev_chip = MDLabel(
            text="", markup=True,
            theme_text_color="Custom", text_color=T.k(T.TEXT_DIM),
            font_style="Caption", bold=True,
            size_hint_y=None, height=dp(20))
        self._effects_banner.add_widget(self._effects_sev_chip)

        # Desensitization badge
        self._effects_des_chip = MDLabel(
            text="", markup=True,
            theme_text_color="Custom", text_color=T.k(T.TEXT_DIM),
            font_style="Caption", bold=True,
            size_hint_y=None, height=dp(20))
        self._effects_banner.add_widget(self._effects_des_chip)
        p1.add_widget(self._effects_banner)

        p1.add_widget(self._build_severity_section())
        p1.add_widget(self._build_desens_section())
        p1.add_widget(self._build_rules_panel())
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
            text="Fear", halign="right",
            theme_text_color="Custom", text_color=T.k(T.GOLD),
            font_style="Caption", bold=True,
            size_hint_x=0.38)

        self._dot0 = PageDot(color_hex=T.GOLD)
        self._dot1 = PageDot(color_hex=T.TEXT_DIM)

        self._ind_lbl1 = MDLabel(
            text="Fear Effects", halign="left",
            theme_text_color="Custom", text_color=T.k(T.TEXT_DIM),
            font_style="Caption", bold=False,
            size_hint_x=0.38)

        row.add_widget(self._ind_lbl0)
        row.add_widget(self._dot0)
        row.add_widget(self._dot1)
        row.add_widget(self._ind_lbl1)
        return row

    def _update_indicator(self):
        if self._page == 0:
            self._dot0.set_color(T.GOLD)
            self._dot1.set_color(T.TEXT_DIM)
            self._ind_lbl0.bold       = True
            self._ind_lbl0.text_color = T.k(T.GOLD)
            self._ind_lbl1.bold       = False
            self._ind_lbl1.text_color = T.k(T.TEXT_DIM)
        else:
            self._dot0.set_color(T.TEXT_DIM)
            self._dot1.set_color(T.GOLD)
            self._ind_lbl0.bold       = False
            self._ind_lbl0.text_color = T.k(T.TEXT_DIM)
            self._ind_lbl1.bold       = True
            self._ind_lbl1.text_color = T.k(T.GOLD)

    def _update_effects_banner(self):
        """Refresh the fear name + severity/desens badges on the effects page."""
        name = self._selected_fear
        if not name:
            self._effects_fear_name.text = "[color=#6b6050]No fear active[/color]"
            self._effects_sev_chip.text  = ""
            self._effects_des_chip.text  = ""
            return
        app      = self._app()
        stage    = self._stage or 1
        rung     = app.fm.get_desens(name)
        sev_col  = FEAR_STAGES[stage].color
        des_col  = DESENS_RUNG_COLORS[rung]
        sev_name = FEAR_STAGES[stage].name
        des_name = DESENS_NAMES[rung]
        self._effects_fear_name.text = f"[color={T.GOLD_LT}]{name}[/color]"
        self._effects_sev_chip.text  = f"[color={sev_col}]Severity: {sev_name}[/color]"
        self._effects_des_chip.text  = f"[color={des_col}]Desensitization: {des_name}[/color]"

    def _go_page(self, page: int):
        if page == self._page:
            return
        self._page = page
        self._content_area.clear_widgets()
        self._content_area.add_widget(self._sv0 if page == 0 else self._sv1)
        self._update_indicator()
        if page == 1:
            self._update_effects_banner()
            # Expand the current severity and desens panels immediately
            self._update_severity_visuals(expand=True)
            self._update_desens_visuals(expand=True)

    # ── Swipe detection ──────────────────────────────────────────────────────

    def on_touch_down(self, touch):
        if self.collide_point(*touch.pos):
            touch.ud['fears_swipe_start'] = (touch.x, touch.y)
        return super().on_touch_down(touch)

    def on_touch_up(self, touch):
        start = touch.ud.get('fears_swipe_start')
        if start:
            dx = touch.x - start[0]
            dy = touch.y - start[1]
            # Horizontal swipe: must be > 50dp and clearly more horizontal than vertical
            if abs(dx) > dp(50) and abs(dx) > abs(dy) * 1.5:
                if dx < 0:
                    self._go_page(1)
                elif dx > 0:
                    self._go_page(0)
        return super().on_touch_up(touch)

    # ── Build: Encounter Card ────────────────────────────────────────────────

    def _build_encounter_card(self) -> BorderCard:
        card = BorderCard(border_hex=T.GOLD)
        card.add_widget(SectionLabel("FEAR ENCOUNTER", color_hex=T.GOLD))

        self._enc_fear_lbl = CaptionLabel(
            "Select a fear from the list below first.",
            color_hex=T.TEXT_DIM, height_dp=20)
        # (not added to card — kept as data holder only)

        dc_row = MDBoxLayout(spacing=dp(8), size_hint_y=None, height=dp(48))
        dc_row.add_widget(MDLabel(
            text="DC:", size_hint_x=None, width=dp(26),
            theme_text_color="Custom", text_color=T.k(T.TEXT_DIM)))
        self._dc_field = themed_field(
            hint_text="", text=str(FEAR_ENC_DC),
            accent_hex=T.GOLD,
            size_hint_x=0.22, input_filter="int")
        dc_row.add_widget(self._dc_field)
        self._enc_btn = MDRaisedButton(
            text="ENCOUNTER",
            md_bg_color=T.k(T.BLOOD),
            size_hint_x=0.72,
            disabled=True,
            on_release=self._on_encounter)
        dc_row.add_widget(self._enc_btn)
        card.add_widget(dc_row)

        # ── Roll panel (hidden until encounter triggered) ──
        self._roll_panel = MDBoxLayout(
            orientation="vertical", spacing=dp(6),
            size_hint_y=None, height=0, opacity=0)

        # Info line: "WIS Save: D20(16) + WIS(+1) = 17 VS DC 16"
        self._roll_info_lbl = MDLabel(
            text="", theme_text_color="Custom",
            text_color=T.k(T.TEXT_DIM), font_style="Caption",
            size_hint_y=None, height=dp(20))

        # Big result: "PASSED: 17" or "FAILED: 12" / "Sanity Roll: 14"
        self._roll_big = MDLabel(
            text="", bold=True,
            theme_text_color="Custom", text_color=T.k(T.TEXT_BRIGHT),
            font_style="H5", size_hint_y=None, height=dp(48))

        # Confirm row — [Failed Save] [Passed Save]
        self._confirm_row = MDBoxLayout(spacing=dp(4), size_hint_y=None, height=dp(44))
        self._fail_btn = MDRaisedButton(
            text="Failed Save", md_bg_color=T.k(T.RED),
            size_hint_x=0.5, on_release=self._on_confirm_fail)
        self._pass_btn = MDRaisedButton(
            text="Passed Save", md_bg_color=T.k(T.GREEN),
            size_hint_x=0.5, on_release=self._on_pass)
        self._confirm_row.add_widget(self._fail_btn)
        self._confirm_row.add_widget(self._pass_btn)

        # Preview box — shown after fail confirmed (two separate cards)
        self._preview_box = MDBoxLayout(
            orientation="vertical", spacing=dp(8),
            size_hint_y=None, height=0, opacity=0)

        # ── Card + metric-row factory helpers ─────────────────────────────────
        def _mk_outer_card(border_hex):
            """Outer card shell: 2dp colored border + BG_HOVER fill."""
            box = MDBoxLayout(
                orientation="vertical", spacing=dp(6),
                padding=[dp(10), dp(10), dp(10), dp(10)],
                adaptive_height=True)
            with box.canvas.before:
                Color(*T.k(border_hex))
                _bd = RoundedRectangle(radius=[dp(7)])
                Color(*T.k(T.BG_HOVER))
                _bg = RoundedRectangle(radius=[dp(6)])
            def _upd(w, *_, _bd=_bd, _bg=_bg):
                _bd.pos = w.pos; _bd.size = w.size
                _bg.pos = (w.x + 2, w.y + 2)
                _bg.size = (max(0, w.width - 4), max(0, w.height - 4))
            box.bind(pos=_upd, size=_upd)
            return box

        def _mk_metric_row(cat_text, accent_hex):
            """Inset metric block: 4dp left accent strip, category label, value label."""
            row = MDBoxLayout(orientation="horizontal",
                              adaptive_height=True, spacing=0)
            with row.canvas.before:
                Color(*T.k(T.BG_INSET))
                _bg = RoundedRectangle(radius=[dp(5)])
                Color(*T.k(accent_hex))
                _acc = Rectangle()
            def _upd_r(w, *_, _bg=_bg, _acc=_acc):
                _bg.pos  = w.pos;  _bg.size  = w.size
                _acc.pos = w.pos;  _acc.size = (dp(4), w.height)
            row.bind(pos=_upd_r, size=_upd_r)

            content = MDBoxLayout(
                orientation="vertical",
                padding=[dp(12), dp(6), dp(8), dp(6)],
                spacing=dp(2), adaptive_height=True)

            content.add_widget(MDLabel(
                text=cat_text, bold=True,
                theme_text_color="Custom", text_color=T.k(accent_hex, 0.85),
                font_style="Caption",
                size_hint_y=None, height=dp(16)))

            val_lbl = MDLabel(
                text="", markup=True,
                theme_text_color="Custom", text_color=T.k(T.TEXT_BRIGHT),
                font_style="Caption",
                size_hint_y=None, adaptive_height=True)
            val_lbl.bind(width=lambda inst, v: setattr(inst, "text_size", (v, None)))

            content.add_widget(val_lbl)
            row.add_widget(content)
            return row, val_lbl

        # ─── CONFRONT card ───────────────────────────────────────────────────
        self._confront_card = _mk_outer_card(T.BLOOD_LT)
        self._confront_card.add_widget(MDLabel(
            text="CONFRONT", bold=True,
            theme_text_color="Custom", text_color=T.k(T.BLOOD_LT),
            font_style="Caption", size_hint_y=None, height=dp(20)))

        _csan_row, self._conf_sanity_lbl = _mk_metric_row("SANITY", T.PURPLE_LT)
        self._confront_card.add_widget(_csan_row)

        _cdes_row, self._conf_desens_lbl = _mk_metric_row("DESENSITIZATION", T.DESENS_LT)
        self._confront_card.add_widget(_cdes_row)

        self._push_btn = MDRaisedButton(
            text="Confront", md_bg_color=T.k(T.BLOOD),
            size_hint_x=1, size_hint_y=None, height=dp(40),
            disabled=True, on_release=self._on_push)
        self._confront_card.add_widget(self._push_btn)

        # ─── AVOID card ──────────────────────────────────────────────────────
        self._avoid_card = _mk_outer_card(T.STAGE_1)
        self._avoid_card.add_widget(MDLabel(
            text="AVOID", bold=True,
            theme_text_color="Custom", text_color=T.k(T.STAGE_1),
            font_style="Caption", size_hint_y=None, height=dp(20)))

        _asan_row, self._avd_sanity_lbl = _mk_metric_row("SANITY", T.PURPLE_LT)
        self._avoid_card.add_widget(_asan_row)

        _asev_row, self._avd_sev_lbl = _mk_metric_row("SEVERITY", T.GOLD_LT)
        self._avoid_card.add_widget(_asev_row)

        _ades_row, self._avd_desens_lbl = _mk_metric_row("DESENSITIZATION", T.DESENS_LT)
        self._avoid_card.add_widget(_ades_row)

        self._avoid_btn = MDRaisedButton(
            text="Avoid", md_bg_color=T.k(T.GREEN),
            size_hint_x=1, size_hint_y=None, height=dp(40),
            disabled=True, on_release=self._on_avoid)
        self._avoid_card.add_widget(self._avoid_btn)

        self._preview_box.add_widget(self._confront_card)
        self._preview_box.add_widget(self._avoid_card)

        # Sanity result shown after resolving
        self._san_result_lbl = MDLabel(
            text="", theme_text_color="Custom",
            text_color=T.k(T.WHITE), font_style="Caption",
            size_hint_y=None, height=0)

        # Hope row — centred, hidden until a fail result with active hope
        self._hope_row = MDBoxLayout(
            size_hint_y=None, height=0, opacity=0,
            padding=[0, dp(4), 0, dp(4)])
        self._hope_btn = HopeButton(on_use=self._use_hope)
        self._hope_row.add_widget(self._hope_btn)
        self._hope_row.add_widget(Widget())

        self._roll_panel.add_widget(self._roll_info_lbl)
        self._roll_panel.add_widget(self._roll_big)
        self._roll_panel.add_widget(self._hope_row)
        self._roll_panel.add_widget(self._confirm_row)
        self._roll_panel.add_widget(self._preview_box)
        self._roll_panel.add_widget(self._san_result_lbl)

        card.add_widget(self._roll_panel)
        return card

    # ── Build: Fear Add Row ──────────────────────────────────────────────────

    def _build_fear_add_row(self) -> BorderCard:
        card = BorderCard(border_hex=T.GOLD_DK)
        card.add_widget(SectionLabel("ADD FEAR", color_hex=T.GOLD))
        row = MDBoxLayout(spacing=dp(6), size_hint_y=None, height=dp(52))
        self._fear_input = themed_field(
            hint_text="Fear name...", accent_hex=T.GOLD,
            size_hint_x=0.55)
        self._fear_input.bind(on_text_validate=self._on_add_fear)
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
        card.add_widget(row)
        return card

    # ── Build: Fear List Card ────────────────────────────────────────────────

    def _build_fear_list(self) -> BorderCard:
        card = BorderCard(border_hex=T.GOLD)
        hdr = MDBoxLayout(size_hint_y=None, height=dp(32), spacing=dp(8))
        hdr.add_widget(SectionLabel("FEAR LIST", color_hex=T.GOLD))
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

    # ── Build: Severity Section (accordion) ──────────────────────────────────

    def _build_severity_section(self) -> BorderCard:
        card = BorderCard(border_hex=T.GOLD_DK)
        card.add_widget(SectionLabel("FEAR SEVERITY", color_hex=T.GOLD))
        card.add_widget(CaptionLabel(
            "Tap to set severity — also updates the selected fear.",
            color_hex=T.TEXT_DIM, height_dp=18))

        self._sev_items = {}

        for s in range(1, 5):
            info = FEAR_STAGES[s]

            row = ListItem(
                primary=info.name,
                secondary=f"{info.dice}d4 on fail",
                accent_hex=info.color,
                on_tap=lambda w, stage=s: self._on_severity_select(stage))
            card.add_widget(row)

            detail = MDBoxLayout(
                orientation="vertical",
                size_hint_y=None, height=0, opacity=0,
                padding=[dp(0), dp(4), dp(0), dp(6)],
                spacing=dp(0))
            inner = DescriptionCard(
                title=info.name.upper(),
                color_hex=info.color)
            inner.add_widget(CaptionLabel(
                f"Fail > roll {info.dice}d4  |  Pass > encounter ends",
                color_hex=info.color, height_dp=20))
            _desc = MDLabel(
                text=info.desc,
                theme_text_color="Custom", text_color=T.k(T.TEXT),
                font_style="Body2",
                size_hint_y=None, adaptive_height=True)
            _desc.bind(width=lambda inst, val: setattr(inst, "text_size", (val, None)))
            inner.add_widget(_desc)
            detail.add_widget(inner)
            card.add_widget(detail)

            self._sev_items[s] = (row, detail)

        return card

    # ── Build: Fear Desensitization Section (accordion) ──────────────────────

    def _build_desens_section(self) -> BorderCard:
        card = BorderCard(border_hex=T.GOLD_DK)
        card.add_widget(SectionLabel("FEAR DESENSITIZATION", color_hex=T.GOLD))
        card.add_widget(CaptionLabel(
            "Tap to set rung for the selected fear.",
            color_hex=T.TEXT_DIM, height_dp=18))

        self._desens_items = {}

        for r in range(1, 5):
            color = DESENS_RUNG_COLORS[r]

            row = ListItem(
                primary=DESENS_NAMES[r],
                secondary=f"Rung {r}  |  DC {DESENS_DC[r]}",
                accent_hex=color,
                on_tap=lambda w, rung=r: self._on_desens_select(rung))
            card.add_widget(row)

            detail = MDBoxLayout(
                orientation="vertical",
                size_hint_y=None, height=0, opacity=0,
                padding=[dp(0), dp(4), dp(0), dp(6)],
                spacing=dp(0))
            inner = DescriptionCard(
                title=DESENS_NAMES[r].upper(),
                color_hex=color)
            _desc = MDLabel(
                text=DESENS_DESCS[r],
                theme_text_color="Custom", text_color=T.k(T.TEXT),
                font_style="Body2",
                size_hint_y=None, adaptive_height=True)
            _desc.bind(width=lambda inst, val: setattr(inst, "text_size", (val, None)))
            inner.add_widget(_desc)
            detail.add_widget(inner)
            card.add_widget(detail)

            self._desens_items[r] = (row, detail)

        return card

    # ── Build: Rules Panel ───────────────────────────────────────────────────

    def _build_rules_panel(self) -> BorderCard:
        wrapper = BorderCard(border_hex=T.GOLD)
        sec = ExpandableSection(
            "FEAR RULES",
            accent_hex=T.GOLD,
        )
        populate_rules_section(sec, FEAR_RULES_TEXT, T.GOLD)
        wrapper.add_widget(sec)
        return wrapper

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

    def _sync_panel_height(self, panel):
        """Sync a panel's height to its current minimum_height (call via Clock)."""
        panel.height = panel.minimum_height

    def _show_roll_panel(self):
        self._roll_panel.size_hint_y = None
        self._roll_panel.opacity = 1
        # Reset sub-widget states
        self._confirm_row.height  = dp(44)
        self._confirm_row.opacity = 1
        self._hope_row.height     = 0
        self._hope_row.opacity    = 0
        self._preview_box.height  = 0
        self._preview_box.opacity = 0
        self._conf_sanity_lbl.text = ""
        self._conf_desens_lbl.text = ""
        self._avd_sanity_lbl.text  = ""
        self._avd_sev_lbl.text     = ""
        self._avd_desens_lbl.text  = ""
        self._san_result_lbl.text  = ""
        self._roll_big.text       = ""
        self._roll_info_lbl.text  = ""
        # Schedule height sync
        Clock.schedule_once(lambda dt: self._sync_panel_height(self._roll_panel))
        Clock.schedule_once(lambda dt: setattr(self._sv0, "scroll_y", 1), 0.05)

    def _end_enc(self):
        self._enc.reset()
        self._save_confirmed      = False
        self._roll_panel.size_hint_y = None
        self._roll_panel.height   = 0
        self._roll_panel.opacity  = 0
        self._push_btn.disabled   = True
        self._avoid_btn.disabled  = True
        self._san_result_lbl.text = ""
        # Restore confirm row for next encounter
        self._confirm_row.height  = dp(44)
        self._confirm_row.opacity = 1
        self._preview_box.height  = 0
        self._preview_box.opacity = 0

    def _update_severity_visuals(self, expand=None):
        if not self._sev_items:
            return
        if expand is not None:
            self._sev_expanded = expand
        if not self._selected_fear:
            for s, (row, detail) in self._sev_items.items():
                row.set_selected(False, persist=False)
                detail.size_hint_y = None
                detail.height      = 0
                detail.opacity     = 0
            return
        for s, (row, detail) in self._sev_items.items():
            is_sel = (s == self._stage)
            row.set_selected(is_sel, persist=is_sel)
            if is_sel and self._sev_expanded:
                detail.size_hint_y = None
                detail.opacity     = 1
                Clock.schedule_once(lambda dt, d=detail: self._sync_panel_height(d))
            else:
                detail.size_hint_y = None
                detail.height      = 0
                detail.opacity     = 0

    def _update_desens_visuals(self, expand=None):
        if not self._desens_items:
            return
        if expand is not None:
            self._des_expanded = expand
        app  = self._app()
        name = self._selected_fear
        if not name:
            for r, (row, detail) in self._desens_items.items():
                row.set_selected(False, persist=False)
                detail.size_hint_y = None
                detail.height      = 0
                detail.opacity     = 0
            return
        cur_rung = app.fm.get_desens(name)
        for r, (row, detail) in self._desens_items.items():
            is_sel = (r == cur_rung)
            row.set_selected(is_sel, persist=is_sel)
            if is_sel and self._des_expanded:
                detail.size_hint_y = None
                detail.opacity     = 1
                Clock.schedule_once(lambda dt, d=detail: self._sync_panel_height(d))
            else:
                detail.size_hint_y = None
                detail.height      = 0
                detail.opacity     = 0

    def _autofill_dc(self):
        app  = self._app()
        name = self._selected_fear
        if name:
            rung = app.fm.get_desens(name)
            self._dc_field.text = str(DESENS_DC.get(rung, FEAR_ENC_DC))
        else:
            self._dc_field.text = str(FEAR_ENC_DC)

    def _calc_threshold_preview(self, cur: int, roll: int, max_s: int) -> str:
        """Return a label describing what threshold (if any) would be crossed."""
        if max_s == 0:
            return "No threshold"
        new_val = max(0, cur - roll)
        if new_val == 0:
            return "Sanity reaches 0!"
        old_pct = cur / max_s
        new_pct = new_val / max_s
        crossed = []
        kind_labels = {
            "short":      "Short-Term Madness",
            "long":       "Long-Term Madness",
            "indefinite": "Indefinite Madness",
        }
        for _label, thresh, kind in THRESHOLDS:
            if kind == "zero":
                continue
            if old_pct > thresh >= new_pct:
                crossed.append(kind_labels.get(kind, kind))
        return crossed[-1] if crossed else "No threshold crossed"

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
                des_color = DESENS_RUNG_COLORS[rung]
                secondary = (
                    f"[color={info.color}]{info.name}[/color]"
                    f"  |  [color={des_color}]{DESENS_NAMES[rung]}[/color]"
                )
                item = ListItem(
                    primary=name,
                    secondary=secondary,
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
                f"Encountering: {self._selected_fear}  ({info.name})")
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
        # Toggle: tap the active row again to collapse it
        same_stage = (s == self._stage)
        self._stage = s
        self._sev_expanded = not (same_stage and self._sev_expanded)
        self._update_severity_visuals()
        self._update_effects_banner()
        if self._selected_fear:
            app  = self._app()
            name = self._selected_fear
            self._push_undo()
            app.fm.set_stage(name, s)
            self.refresh()
            self._save()
            self._log(f"  {name}: Severity > {FEAR_STAGES[s].name}")
            info = FEAR_STAGES[s]
            app.notify_event(
                f"Severity: {name} -> {info.name}",
                "fears", info.color,
                action_cb=lambda n=name: self.open_fear(n))

    # ── Event: Desens rung selection ──────────────────────────────────────────

    def _on_desens_select(self, rung: int):
        if not self._selected_fear:
            self._snack("Select a fear first.", T.BORDER); return
        app      = self._app()
        name     = self._selected_fear
        cur_rung = app.fm.get_desens(name)
        # Toggle: tap the active rung again to collapse it
        same_rung = (rung == cur_rung)
        self._push_undo()
        app.fm.set_desens(name, rung)
        self._des_expanded = not (same_rung and self._des_expanded)
        self._update_desens_visuals()
        self._update_effects_banner()
        self._autofill_dc()
        self._log(f"  {name}: Desensitization > {DESENS_NAMES[rung]}")
        self.refresh()
        self._save()
        app.notify_event(
            f"Desensitization: {name} -> {DESENS_NAMES[rung]}",
            "fears", DESENS_RUNG_COLORS[rung],
            action_cb=lambda n=name: self.open_fear(n))

    # ── Event: Fear tap ───────────────────────────────────────────────────────

    def _on_fear_tap(self, widget: ListItem, name: str):
        if self._sel_fear_widget and self._sel_fear_widget is not widget:
            self._sel_fear_widget.set_selected(False, persist=False)
        self._selected_fear   = name
        self._sel_fear_widget = widget
        widget.set_selected(True, persist=True)
        app   = self._app()
        stage = app.fm.get_stage(name)
        info  = FEAR_STAGES[stage]
        self._enc_fear_lbl.text       = f"Encountering: {name}  ({info.name})"
        self._enc_fear_lbl.text_color = T.k(info.color)
        self._enc_btn.disabled        = False
        self._stage = stage
        self._update_severity_visuals()
        self._update_desens_visuals()
        self._update_effects_banner()
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
        self._fear_input.text  = ""
        self._fear_input.focus = False
        self._log(f"Fear added: {name}")
        self.refresh()
        self._save()
        app.notify_event(f"Fear added: {name}", "fears", T.GOLD,
                         action_cb=lambda n=name: self.open_fear(n))

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

    # ── Event: Encounter — Step 1: roll WIS save ──────────────────────────────

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
        self._save_confirmed = False

        try:
            dc = int(self._dc_field.text.strip() or str(FEAR_ENC_DC))
        except ValueError:
            dc = FEAR_ENC_DC

        # Extreme Severity: +1 exhaustion before roll
        if stage == 4:
            self._push_undo()
            app.state.exhaustion = int(clamp(app.state.exhaustion + 1, 0, 6))
            self._log("Extreme Severity — +1 Exhaustion applied before encounter")
            app.refresh_all()
            app.notify_event("Extreme Severity: +1 Exhaustion applied", "fears", T.STAGE_4)
            _exh = app.state.exhaustion
            Clock.schedule_once(lambda _: app.notify_exhaustion(_exh), 0.5)

        wis_mod = app.state.wis_mod
        if getattr(app, 'wis_adv', False):
            rolls = roll_d(20, 2)
            d20 = max(rolls)
            roll_str = f"D20 Adv({rolls[0]},{rolls[1]})→{d20}"
        else:
            d20 = roll_d(20)[0]
            roll_str = f"D20({d20})"
        wis_save = d20 + wis_mod
        self._enc.wis_save_total = wis_save
        info     = FEAR_STAGES[stage]

        self._log(f"=== ENCOUNTER: {name} ({info.name}) ===")
        self._log(f"Desens: {DESENS_NAMES[rung]}  |  Rung {rung}  |  DC {dc}")
        self._log(f"WIS Save: {roll_str} + {wis_mod:+d} = {wis_save} vs DC {dc}")

        self._show_roll_panel()

        self._roll_info_lbl.text = (
            f"WIS Save: {roll_str} + WIS({wis_mod:+d}) = {wis_save} VS DC {dc}")

        if wis_save >= dc:
            self._roll_big.text       = f"PASSED: {wis_save}"
            self._roll_big.text_color = T.k(T.STAGE_1)
            self._fail_btn.disabled   = True
            self._pass_btn.disabled   = False
            self._hope_row.height  = 0
            self._hope_row.opacity = 0
        else:
            self._roll_big.text       = f"FAILED: {wis_save}"
            self._roll_big.text_color = T.k(T.BLOOD)
            self._fail_btn.disabled   = False
            self._pass_btn.disabled   = True
            if app.state.hope:
                self._hope_row.height  = dp(108)
                self._hope_row.opacity = 1
                Clock.schedule_once(lambda _: self._sync_panel_height(self._roll_panel))
            else:
                self._hope_row.height  = 0
                self._hope_row.opacity = 0

        self._push_btn.disabled  = True
        self._avoid_btn.disabled = True

    # ── Event: Use Hope (re-roll on fail) ────────────────────────────────────

    def _use_hope(self):
        app = self._app()
        self._push_undo()
        app.state.hope = False
        self._hope_row.height  = 0
        self._hope_row.opacity = 0
        app.refresh_all()
        # Hope guarantees a pass — auto-succeed the encounter
        self._on_pass()

    # ── Event: Confirm failed save — Step 2 ──────────────────────────────────

    def _on_confirm_fail(self, *_):
        """Player confirms the failed save — roll sanity dice and show preview."""
        app   = self._app()
        stage = self._enc.fear_stage or 1
        info  = FEAR_STAGES[stage]

        rolls = roll_d(4, info.dice)
        total = sum(rolls)
        rt    = "+".join(map(str, rolls))
        self._enc.roll_total = total

        self._log(f"Failed save — sanity roll: {info.dice}d4 ({rt}) = {total}")

        self._roll_big.text       = f"Sanity Roll: {total}"
        self._roll_big.text_color = T.k(T.WHITE)

        cur   = app.state.current_sanity
        max_s = app.state.max_sanity
        confront_val  = max(0, cur - total)
        avoid_val     = min(max_s, cur + total)
        thresh_label  = self._calc_threshold_preview(cur, total, max_s)

        # Desens/Severity change previews
        fear_name  = self._enc.fear_name or ""
        fear_stage = self._enc.fear_stage or 1
        cur_rung   = app.fm.get_desens(fear_name) if fear_name else 1
        new_rung_confront = min(4, cur_rung + 1)
        new_stage_avoid   = min(4, fear_stage + 1)
        new_rung_avoid    = max(1, cur_rung - 1)

        desens_color   = DESENS_RUNG_COLORS.get(cur_rung, DESENS_RUNG_COLORS[1])
        desens_new_c_c = DESENS_RUNG_COLORS.get(new_rung_confront, DESENS_RUNG_COLORS[1])
        desens_new_c_a = DESENS_RUNG_COLORS.get(new_rung_avoid, DESENS_RUNG_COLORS[1])
        sev_color      = FEAR_STAGES[fear_stage].color
        sev_new_color  = FEAR_STAGES[new_stage_avoid].color

        # Helpers — short names and arrow token
        _D = T.TEXT_DIM          # dim colour for arrow / change suffix
        _ARR = f" [color={_D}]>>[/color] "

        def _desens_short(rung):
            return DESENS_NAMES[rung].split()[0]   # "Low", "Moderate", "High", "Extreme"

        def _sev_short(stage):
            return FEAR_STAGES[stage].name         # e.g. "Low", "Moderate"

        # ── CONFRONT card labels ──────────────────────────────────────────────
        _thresh_color = {
            "Short-Term Madness": T.M_SHORT,
            "Long-Term Madness":  T.M_LONG,
            "Indefinite Madness": T.M_INDEF,
            "Sanity reaches 0!":  T.BLOOD,
        }.get(thresh_label, _D)
        _thresh_suffix = (
            f"  [color={_D}]>>[/color]  [color={_thresh_color}]{thresh_label}[/color]"
            if thresh_label not in ("No threshold crossed", "No threshold") else "")

        self._conf_sanity_lbl.text = (
            f"[color={T.PURPLE_LT}]{cur} - {total} = {confront_val}[/color]"
            f"{_thresh_suffix}"
        )

        if cur_rung == 4:
            self._conf_desens_lbl.text = (
                f"[color={desens_color}]Extreme[/color]"
                f"{_ARR}"
                f"[color={T.STAGE_1}]Fear removed[/color]"
            )
        else:
            self._conf_desens_lbl.text = (
                f"[color={desens_color}]{_desens_short(cur_rung)}[/color]"
                f"{_ARR}"
                f"[color={desens_new_c_c}]{_desens_short(new_rung_confront)}[/color]"
                f"  [color={_D}]+1[/color]"
            )

        # ── AVOID card labels ─────────────────────────────────────────────────
        self._avd_sanity_lbl.text = (
            f"[color={T.PURPLE_LT}]{cur} + {total} = {avoid_val}[/color]"
        )

        if fear_stage == 4:
            self._avd_sev_lbl.text = (
                f"[color={sev_color}]Extreme[/color]"
                f"{_ARR}"
                f"[color={T.STAGE_4}]Random fear added[/color]"
            )
        else:
            self._avd_sev_lbl.text = (
                f"[color={sev_color}]{_sev_short(fear_stage)}[/color]"
                f"{_ARR}"
                f"[color={sev_new_color}]{_sev_short(new_stage_avoid)}[/color]"
                f"  [color={_D}]+1[/color]"
            )

        if new_rung_avoid == cur_rung:
            self._avd_desens_lbl.text = f"[color={_D}]Already at minimum[/color]"
        else:
            self._avd_desens_lbl.text = (
                f"[color={desens_color}]{_desens_short(cur_rung)}[/color]"
                f"{_ARR}"
                f"[color={desens_new_c_a}]{_desens_short(new_rung_avoid)}[/color]"
                f"  [color={_D}]-1[/color]"
            )

        self._preview_box.opacity = 1
        self._confirm_row.height  = 0
        self._confirm_row.opacity = 0

        def _sync_heights(dt):
            self._sync_panel_height(self._preview_box)
            Clock.schedule_once(lambda dt2: self._sync_panel_height(self._roll_panel))
        Clock.schedule_once(_sync_heights, 0.05)

        self._push_btn.disabled  = False
        self._avoid_btn.disabled = False
        self._save_confirmed     = True

    # ── Event: Pass ──────────────────────────────────────────────────────────

    def _on_pass(self, *_):
        self._log("Passed — encounter ends cleanly.")
        self._end_enc()
        self._save()

    # ── Event: Confront ───────────────────────────────────────────────────────

    def _on_push(self, *_):
        app  = self._app()
        amt  = self._enc.roll_total or 0
        name = self._enc.fear_name
        self._push_undo()
        threshs      = app.state.apply_loss(amt)
        cur_rung     = app.fm.get_desens(name)
        fear_cured   = (cur_rung == 4)
        new_rung     = app.fm.incr_desens(name)
        self._log(
            f"Confront -- lost {amt} sanity  |  {name}: Desensitization > {DESENS_NAMES[new_rung]}")
        self._handle_thresholds(threshs)
        self._update_desens_visuals()
        self._autofill_dc()

        cur = app.state.current_sanity
        mx  = app.state.max_sanity
        pct = (cur / mx * 100) if mx else 0
        result = f"Lost {amt} sanity  |  Now: {cur} / {mx}  ({pct:.0f}%)"
        if threshs:
            kinds = ", ".join(k.replace("_", "-").title()
                              for _, k in threshs if k != "zero")
            if kinds:
                result += f"\nTHRESHOLD: {kinds} Madness added!"
        if fear_cured:
            result += f"\nFEAR OVERCOME: {name} has been conquered and removed!"
            self._log(f"FEAR CURED: {name} — Extreme Desensitization reached, fear removed.")
            app.notify_event(
                f"Fear conquered: {name}!",
                "fears", T.STAGE_1,
                action_cb=lambda n=name: self.open_fear(n)
            )
        else:
            # Sanity loss + desensitization change — batched into one card
            Clock.schedule_once(
                lambda _, n=name, a=amt, c=cur, m=mx: app.notify_event(
                    f"Confront: {n} - Lost {a} sanity ({c}/{m})",
                    "fears", T.BLOOD,
                    action_cb=lambda nn=n: self.open_fear(nn)
                ), 0.15)
            Clock.schedule_once(
                lambda _, r=new_rung, o=cur_rung, n=name: app.notify_event(
                    f"Desensitization: {n}, {DESENS_NAMES[o].split()[0]} >> {DESENS_NAMES[r].split()[0]}",
                    "fears", DESENS_RUNG_COLORS[r],
                    action_cb=lambda rr=r: self.open_desens(rr)
                ), 0.15)

        self._san_result_lbl.text = ""
        self._roll_big.text       = f"Lost {amt}  >  {cur}/{mx}"
        self._push_btn.disabled   = True
        self._avoid_btn.disabled  = True

        app.refresh_all()

        if fear_cured:
            app.fm.remove(name)
            self._selected_fear   = None
            self._sel_fear_widget = None
            Clock.schedule_once(lambda _: (self.refresh(), self._end_enc()), 0.3)
        else:
            Clock.schedule_once(lambda _: self._end_enc(), 0.3)
        self._save()

    # ── Event: Avoid ─────────────────────────────────────────────────────────

    def _on_avoid(self, *_):
        app   = self._app()
        amt   = self._enc.roll_total or 0
        name  = self._enc.fear_name
        stage = self._enc.fear_stage or 1
        self._push_undo()
        cleared   = app.state.apply_recovery(amt)
        new_stage = app.fm.increment_stage(name)
        old_rung  = app.fm.get_desens(name)
        new_rung  = app.fm.decr_desens(name)
        self._log(
            f"Avoided — recovered {amt} sanity  |  "
            f"{name}: Severity {stage}>{new_stage}  |  "
            f"Desensitization > {DESENS_NAMES[new_rung]}")

        # Extreme Severity Avoid → add random new fear
        if stage == 4:
            new_fear = app.fm.add_random()
            if new_fear:
                self._log(f"Extreme Avoid — panic: new fear added: {new_fear}")
                app.notify_event(f"Panic! New fear: {new_fear}", "fears", T.STAGE_4,
                                 action_cb=lambda f=new_fear: self.open_fear(f))

        self._update_desens_visuals()
        self._autofill_dc()

        cur = app.state.current_sanity
        mx  = app.state.max_sanity
        pct = (cur / mx * 100) if mx else 0
        result = f"Recovered {amt} sanity  |  Now: {cur} / {mx}  ({pct:.0f}%)"

        # Sanity gain + severity increase + desensitization decrease — batched into one card
        _delay = 0.5 if stage == 4 else 0.15
        Clock.schedule_once(
            lambda _, n=name, a=amt, c=cur, m=mx: app.notify_event(
                f"Avoid: {n} - Recovered {a} sanity ({c}/{m})",
                "fears", T.STAGE_1,
                action_cb=lambda nn=n: self.open_fear(nn)
            ), _delay)
        Clock.schedule_once(
            lambda _, s=new_stage, os=stage, n=name: app.notify_event(
                f"Severity: {n}, {FEAR_STAGES[os].name.split()[0]} >> {FEAR_STAGES[s].name.split()[0]}",
                "fears", FEAR_STAGES[s].color,
                action_cb=lambda ss=s: self.open_severity(ss)
            ), _delay)
        Clock.schedule_once(
            lambda _, r=new_rung, o=old_rung, n=name: app.notify_event(
                f"Desensitization: {n}, {DESENS_NAMES[o].split()[0]} >> {DESENS_NAMES[r].split()[0]}",
                "fears", DESENS_RUNG_COLORS[r],
                action_cb=lambda rr=r: self.open_desens(rr)
            ), _delay)

        self._san_result_lbl.text = ""
        self._roll_big.text       = f"Avoided  >  {cur}/{mx}"
        self._push_btn.disabled   = True
        self._avoid_btn.disabled  = True

        if cleared:
            self._handle_recovery_thresholds(cleared)

        app.refresh_all()
        self.refresh()
        Clock.schedule_once(lambda dt: self._end_enc(), 0.3)
        self._save()

    # ── Threshold handling ────────────────────────────────────────────────────

    def _handle_thresholds(self, threshs):
        app = self._app()
        sanity_tab = app._sanity_tab
        events = []
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
                self._log(f"THRESHOLD re-crossed: {label} - cured {cured_name}")
                events.append((color, None, cured_name, label))
            else:
                m = app.state.add_madness(kind)
                self._log(
                    f"THRESHOLD: {label} > {m.kind_label} insanity: "
                    f"[{m.roll_range}] {m.name} -- {m.effect[:50]}")
                events.append((color, m, None, label))
        if threshs:
            app.refresh_all()
            # Delay to 0.15s so threshold notifications batch with the encounter card
            for color, entry, cured_name, lbl in events:
                if cured_name:
                    Clock.schedule_once(
                        lambda _, cn=cured_name, c=color: app.notify_event(
                            f"Threshold cured: {cn}", "sanity", c
                        ), 0.15)
                else:
                    Clock.schedule_once(
                        lambda _, e=entry, c=color: app.notify_event(
                            f"{e.kind_label} Madness: {e.name}", "sanity", c,
                            action_cb=lambda ee=e: sanity_tab.open_madness(ee)
                        ), 0.15)

    def _handle_recovery_thresholds(self, cleared):
        """Sanity recovered upward past a threshold — remove the matching madness."""
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
                self._log(f"THRESHOLD CLEARED (avoid): {label} — {cured_name} cured")
                events.append((color, cured_name))
            else:
                self._log(f"THRESHOLD CLEARED (avoid): {label} — no matching insanity to cure")
        if events:
            app.refresh_all()
            for color, cured_name in events:
                Clock.schedule_once(
                    lambda _, cn=cured_name, c=color: app.notify_event(
                        f"Insanity cured: {cn}", "sanity", c
                    ), 0.3)

    def open_fear(self, name: str):
        """Navigate to main page, select the fear, and flash it."""
        self._go_page(0)
        item = self._fear_items.get(name)
        if item:
            self._on_fear_tap(item, name)
            item.flash()

    def open_severity(self, stage: int):
        """Navigate to the fear effects page and flash the severity row."""
        self._go_page(1)
        pair = self._sev_items.get(stage)
        if pair:
            row, _ = pair
            Clock.schedule_once(lambda _: row.flash(), 0.2)

    def open_desens(self, rung: int):
        """Navigate to the fear effects page and flash the desensitization row."""
        self._go_page(1)
        pair = self._desens_items.get(rung)
        if pair:
            row, _ = pair
            Clock.schedule_once(lambda _: row.flash(), 0.2)

    def cancel_encounter(self):
        if self._enc.active:
            self._log("Encounter cancelled.")
            self._end_enc()
