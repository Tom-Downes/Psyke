"""
Tab 1: Fears & Fear Encounter  (V2 â€” redesigned layout)

Two-page swipeable layout:
  Page 0 â€” Main:   Encounter card, Add Fear, Fear List, Rules
  Page 1 â€” Detail: Fear Severity, Fear Desensitization

Swipe left/right to move between pages.
"""
from __future__ import annotations

from kivy.animation import Animation
from kivy.app import App
from kivy.clock import Clock
from kivy.graphics import (
    Color, Line, Rectangle, RoundedRectangle,
    StencilPop, StencilPush, StencilUnUse, StencilUse,
)
from kivy.metrics import dp
from kivy.uix.behaviors import ButtonBehavior
from kivy.uix.floatlayout import FloatLayout
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
    SwipeFillListItem, ExpandableSection, DescriptionCard, SwipePageIndicator, themed_field,
    populate_rules_section, ExpandingEffectCard,
)
import theme as T


class _EncTab(ButtonBehavior, MDBoxLayout):
    """A stage tab on the encounter rail.

    Visual states
    -------------
    active   – stage currently being viewed  (dark-gold fill, bright text)
    done_new – the tab immediately before the active one  (solid gold, dark text)
    done_old – all earlier completed tabs  (muted dark-gold, dim text)
    """

    # Shared layout constants (used by FearsTab layout helpers too)
    _TAB_H   = dp(34)
    _TAB_W   = dp(64)
    _TAB_GAP = dp(6)    # vertical gap between consecutive tabs
    _TOP_PAD = dp(8)    # padding from dock top to the first tab
    _DIVIDER_W = dp(1)  # thin separator between main tab and side tab
    _SIDE_W  = dp(4)    # coloured side-tab width
    _SIDE_OVERHANG = dp(3)  # temporary extra width during the morph
    _STAGE_HEX = {
        "severity": T.GOLD,
        "save": T.GOLD,
        "sanity": T.PURPLE_LT,
        "choice": T.BLOOD_LT,
    }

    def __init__(self, key: str, label: str, on_tap, **kwargs):
        kwargs.setdefault("orientation", "horizontal")
        kwargs.setdefault("size_hint_y", None)
        kwargs.setdefault("height", dp(34))
        kwargs.setdefault("size_hint_x", None)
        kwargs.setdefault("width", dp(52))
        kwargs.setdefault("opacity", 0)
        super().__init__(**kwargs)
        self._tab_key    = key
        self._on_tap_cb  = on_tap
        self._shown      = False
        self._tab_state  = None   # None | "active" | "done_new" | "done_old"
        self._dim_pending  = False  # True while tab is live but sweep not yet fired
        self._commit_done  = False  # True once sweep completed → locked to gold
        self._commit_evt   = None
        self._commit_prog  = 0.0
        self._commit_rail_bottom = 0.0
        self._commit_cb    = None
        self._cap_hex      = None
        self._side_live    = False

        with self.canvas.before:
            self._fill_col    = Color(0, 0, 0, 0)
            self._fill_rect   = Rectangle()
            self._accent_col  = Color(0, 0, 0, 0)
            self._accent_rect = Rectangle()
        with self.canvas.after:
            self._side_divider_col = Color(0, 0, 0, 0)
            self._side_divider_rect = Rectangle()
            self._side_col    = Color(0, 0, 0, 0)
            self._side_rect   = Rectangle()
            self._side_line   = Line(width=dp(1), cap="none", joint="miter")
            self._stroke_col  = Color(*T.k(T.GOLD), 0)
            self._stroke_top_rect = Rectangle()
            self._stroke_bottom_rect = Rectangle()

        self.bind(pos=self._upd_canvas, size=self._upd_canvas)

        self._lbl = MDLabel(
            text=label, bold=True,
            theme_text_color="Custom",
            text_color=T.k(T.GOLD),
            font_style="Caption",
            halign="center", valign="middle",
        )
        self.add_widget(self._lbl)

    # ── canvas sync ───────────────────────────────────────────────────────────

    def _upd_canvas(self, *_):
        self._fill_rect.pos    = (self.x, self.y)
        self._fill_rect.size   = (self.width, self.height)
        self._accent_rect.pos  = (self.x, self.y)
        self._accent_rect.size = (dp(4), self.height)
        if self._commit_done and self._side_live:
            self._side_divider_rect.pos  = (self.right, self.y)
            self._side_divider_rect.size = (self._DIVIDER_W, self.height)
            self._side_rect.pos    = (self.right + self._DIVIDER_W, self.y)
            self._side_rect.size   = (self._SIDE_W, self.height)
            self._side_line.points = []
        elif not self._commit_evt:
            self._side_divider_rect.size = (0, 0)
            self._side_rect.size = (0, 0)
            self._side_line.points = []

    def _side_hex(self) -> str:
        if self._tab_key == "save":
            return T.GOLD
        return self._cap_hex or self._STAGE_HEX.get(self._tab_key, T.GOLD)

    def _apply_cap_state(self, alpha: float):
        self._side_col.rgba = T.k(self._side_hex(), alpha)

    def _hide_side_art(self):
        self._side_divider_rect.size = (0, 0)
        self._side_rect.size = (0, 0)
        self._side_line.points = []
        self._side_col.a = 0

    def _clear_stroke_art(self):
        self._stroke_top_rect.size = (0, 0)
        self._stroke_bottom_rect.size = (0, 0)

    def _set_side_morph(self, clean_rx: float, y: float, h: float, stage_hex: str):
        """Place the side cap at its final attachment point while it grows downward."""
        h = max(0.0, h)
        if h <= 0:
            self._hide_side_art()
            return

        divider_rx = clean_rx + self._DIVIDER_W

        self._side_col.rgba = T.k(stage_hex, 1.0)
        self._side_divider_col.rgba = T.k(T.BG_CARD)
        self._side_divider_rect.pos = (clean_rx, y)
        self._side_divider_rect.size = (self._DIVIDER_W, h)
        self._side_rect.pos = (divider_rx, y)
        self._side_rect.size = (self._SIDE_W, h)
        self._side_line.points = []

    # ── interaction ───────────────────────────────────────────────────────────

    def on_release(self):
        if self.opacity > 0 and self._shown:
            self._on_tap_cb(self._tab_key)

    # ── state ─────────────────────────────────────────────────────────────────

    def set_state(self, state: str):
        """Apply a visual state: 'active', 'done_new', or 'done_old'."""
        self._tab_state = state
        # Sweep completed → locked to solid gold + stage-coloured side tab
        if self._commit_done:
            self._fill_col.rgba   = T.k(T.GOLD)
            self._accent_col.rgba = T.k(T.GOLD_LT)
            self._lbl.text_color  = T.k(T.TEXT_DARK)
            self._side_divider_col.rgba = T.k(T.BG_CARD)
            self._side_col.rgba   = T.k(self._side_hex(), 1.0)
            return
        # Animation pending or running → don't interfere with side-line state
        if self._dim_pending or self._commit_evt:
            return
        if state == "active":
            self._fill_col.rgba   = (*T.k(T.GOLD_DK)[:3], 0.92)
            self._accent_col.rgba = T.k(T.GOLD_LT)
            self._lbl.text_color  = T.k(T.TEXT_BRIGHT)
        elif state == "done_new":
            self._fill_col.rgba   = T.k(T.GOLD)
            self._accent_col.rgba = T.k(T.GOLD_LT)
            self._lbl.text_color  = T.k(T.TEXT_DARK)
        elif state == "done_old":
            self._fill_col.rgba   = T.k(T.GOLD_DK)
            self._accent_col.rgba = T.k(T.GOLD_DK)
            self._lbl.text_color  = T.k(T.TEXT_DIM)

    # ── appear animation ──────────────────────────────────────────────────────

    def appear(self, rail_x: float | None = None, start_y: float | None = None):
        """Reveal by growing out from the rail. Fill is dim yellow until sweep fires."""
        self._shown       = True
        self._dim_pending = True
        self._commit_done = False
        target_x = self.x
        target_y = self.y
        target_w = self.width
        target_h = self.height

        Animation.cancel_all(self, "x", "y", "width", "height", "opacity")

        # Dim yellow immediately — set_state() is now blocked
        self._fill_col.rgba   = (*T.k(T.GOLD)[:3], 0.18)
        self._accent_col.rgba = (*T.k(T.GOLD)[:3], 0.28)
        self._lbl.text_color  = (*T.k(T.GOLD)[:3], 0.70)
        self._apply_cap_state(0.0)

        if rail_x is not None:
            self.x      = rail_x
            self.y      = target_y
            self.width  = dp(6)
            self.height = target_h
            self.opacity = 1
            Animation(x=target_x, width=target_w, duration=0.24, t="out_cubic").start(self)
            return

        self.opacity = 0
        if start_y is not None:
            self.y = start_y
        Animation(opacity=1, y=target_y, duration=0.24, t="out_cubic").start(self)

    def play_commit_anim(self, rail_bottom: float, total_duration: float = 0.84, on_complete=None):
        """Gold stroke sweeps around tab timed to total_duration, then tab snaps gold."""
        self._dim_pending = False
        if self._commit_evt:
            self._commit_evt.cancel()
            self._commit_evt = None
        self._commit_done         = False
        self._commit_prog         = 0.0
        self._commit_total_dur    = max(0.3, total_duration)
        self._commit_rail_bottom  = rail_bottom
        self._commit_cb           = on_complete
        self._fill_col.rgba       = (*T.k(T.GOLD)[:3], 0.18)
        self._accent_col.rgba     = (*T.k(T.GOLD)[:3], 0.28)
        self._lbl.text_color      = (*T.k(T.GOLD)[:3], 0.70)
        self._apply_cap_state(0.0)
        self._stroke_col.rgba     = (*T.k(T.GOLD)[:3], 1.0)
        self._clear_stroke_art()
        self._side_divider_col.rgba = T.k(T.BG_CARD)
        self._side_divider_rect.size = (0, 0)
        self._side_col.a          = 0
        self._side_rect.size      = (0, 0)
        self._side_line.points    = []
        self._side_live           = False
        self._commit_evt = Clock.schedule_interval(self._tick_commit_stroke, 1 / 60)

    def _tick_commit_stroke(self, dt):
        total      = self._commit_total_dur
        trace_end  = total * 0.65
        hold_end   = total * 0.75

        self._commit_prog += dt

        # ── Geometry ─────────────────────────────────────────────────────────
        lx       = self.x
        clean_rx = self.right           # actual right edge of the tab
        divider_rx = clean_rx + self._DIVIDER_W
        side_final_rx = divider_rx + self._SIDE_W
        by       = self.y
        ty       = self.top
        self._hide_side_art()
        self._clear_stroke_art()

        # Phase lengths:
        #  top    – gold stroke sweeps lx → clean_rx (corner belongs to the side-tab colour)
        #  right  – the side tab grows down while owning the corner/overhang
        #  bottom – the bottom border returns from clean_rx back to the rail
        top_len    = max(dp(1), clean_rx - lx)
        right_len  = max(dp(1), ty - by)
        bottom_len = max(dp(1), clean_rx - lx)
        total_path = top_len + right_len + bottom_len

        stage_hex = self._side_hex()

        # ── Finish ───────────────────────────────────────────────────────────
        if self._commit_prog >= total:
            # Gold stroke gone; lock in the finished side tab.
            self._clear_stroke_art()
            self._stroke_col.a       = 0
            # Tab snaps to solid gold
            self._fill_col.rgba      = T.k(T.GOLD)
            self._accent_col.rgba    = T.k(T.GOLD_LT)
            self._lbl.text_color     = T.k(T.TEXT_DARK)
            # Clean side tab — attached, with the standard 1px divider
            self._set_side_morph(clean_rx, by, self.height, stage_hex)
            self._side_live          = True
            self._commit_done        = True
            if self._commit_evt:
                self._commit_evt.cancel()
                self._commit_evt = None
            if self._commit_cb:
                cb = self._commit_cb
                self._commit_cb = None
                cb()
            return

        # ── Path progress ─────────────────────────────────────────────────────
        draw_prog = min(self._commit_prog / trace_end, 1.0) if trace_end > 0 else 1.0
        distance  = draw_prog * total_path

        # ── Gold stroke alpha (fades out in the final stretch) ────────────────
        if self._commit_prog >= hold_end and total > hold_end:
            stroke_alpha = max(0.0, 1.0 - (self._commit_prog - hold_end) / (total - hold_end))
        else:
            stroke_alpha = 1.0
        self._stroke_col.rgba = (*T.k(T.GOLD)[:3], stroke_alpha)

        # ── Phase 1: top wrap sweeps from the rail to the overshoot corner ───
        if distance <= top_len:
            self._stroke_top_rect.pos = (lx, ty - self._SIDE_W)
            self._stroke_top_rect.size = (distance, self._SIDE_W)
            return

        self._stroke_top_rect.pos = (lx, ty - self._SIDE_W)
        self._stroke_top_rect.size = (top_len, self._SIDE_W)

        rem = distance - top_len

        # ── Phase 2: side tab owns the top corner and grows downward ─────────
        right_draw = min(right_len, rem)
        if right_draw > 0:
            side_y = ty - right_draw
            side_h = right_draw
            self._set_side_morph(clean_rx, side_y, side_h, stage_hex)
            self._side_live        = right_draw >= right_len

        rem -= right_len
        if rem <= 0:
            return

        # The right side is now complete and remains as the finished side tab.
        # Final phase: animate the bottom back to the rail from the lower corner.
        self._set_side_morph(clean_rx, by, ty - by, stage_hex)
        self._side_live        = True

        # ── Phase 3: bottom border returns to the rail ───────────────────────
        bottom_draw = min(bottom_len, rem)
        if bottom_draw > 0:
            self._stroke_bottom_rect.pos = (clean_rx - bottom_draw, by)
            self._stroke_bottom_rect.size = (bottom_draw, self._SIDE_W)


def clip_children(widget):
    """Clip child drawing to the widget's bounds using a stencil mask."""
    with widget.canvas.before:
        StencilPush()
        widget._clip_rect = Rectangle(pos=widget.pos, size=widget.size)
        StencilUse()
    with widget.canvas.after:
        StencilUnUse()
        Color(0, 0, 0, 0)
        Rectangle(pos=widget.pos, size=widget.size)
        StencilPop()

    def _sync_clip(w, *_):
        if hasattr(w, "_clip_rect"):
            w._clip_rect.pos = w.pos
            w._clip_rect.size = w.size

    widget.bind(pos=_sync_clip, size=_sync_clip)
    _sync_clip(widget)


# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
# FEARS TAB
# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

class FearsTab(MDBoxLayout):

    def __init__(self, **kwargs):
        kwargs.setdefault("orientation", "vertical")
        super().__init__(**kwargs)

        self._enc   = EncounterState()
        self._stage = 1
        self._sev_items: dict[int, ExpandingEffectCard]    = {}
        self._desens_items: dict[int, ExpandingEffectCard] = {}
        self._selected_fear: str | None      = None
        self._sel_fear_widget: SwipeFillListItem | None = None
        self._fear_items: dict[str, SwipeFillListItem] = {}
        self._enc_stage_tabs: dict[str, MDFlatButton] = {}
        self._enc_active_stage: str | None = None
        self._sev_expanded   = False
        self._des_expanded   = False

        # â”€â”€ Page state â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
        self._page = 0   # 0 = Main, 1 = Severity & Desens

        # Page indicator bar
        self.add_widget(self._build_page_indicator())

        # â”€â”€ Page 0 (Main) â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
        self._sv0 = ScrollView(do_scroll_x=False, size_hint=(None, None))
        p0 = MDBoxLayout(
            orientation="vertical",
            padding=dp(10), spacing=dp(8),
            size_hint_y=None, adaptive_height=True)
        p0.add_widget(self._build_encounter_card())
        p0.add_widget(self._build_fear_add_row())
        p0.add_widget(self._build_fear_list())
        p0.add_widget(self._build_rules_panel())
        self._sv0.add_widget(p0)

        # â”€â”€ Page 1 (Detail) â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
        self._sv1 = ScrollView(do_scroll_x=False, size_hint=(None, None))
        p1 = MDBoxLayout(
            orientation="vertical",
            padding=dp(10), spacing=dp(8),
            size_hint_y=None, adaptive_height=True)

        # â”€â”€ Selected fear context banner â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
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

        # Fear name â€” Subtitle1
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

        self._content_area = FloatLayout()
        self._content_area.bind(
            size=lambda *_: Clock.schedule_once(lambda dt: self._update_sv_positions()),
            pos=lambda *_: Clock.schedule_once(lambda dt: self._update_sv_positions()),
        )
        self._content_area.add_widget(self._sv0)
        self._content_area.add_widget(self._sv1)
        self.add_widget(self._content_area)
        self._update_indicator()

    # â”€â”€ Page indicator â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

    def _build_page_indicator(self) -> MDBoxLayout:
        self._page_indicator = SwipePageIndicator(
            "Fear", "Fear Effects",
            left_hex=T.GOLD, right_hex=T.GOLD_LT, bg_hex=T.GOLD)
        return self._page_indicator

    def _update_indicator(self, progress: float | None = None):
        self._page_indicator.set_progress(float(self._page) if progress is None else progress)

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
        self._effects_sev_chip.text  = f"[color={sev_col}]{sev_name}[/color]"
        self._effects_des_chip.text  = f"[color={des_col}]{des_name}[/color]"

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
        self._page = page
        if page == 1:
            self._update_effects_banner()
            self._update_severity_visuals(expand=True)
            self._update_desens_visuals(expand=True)
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

    # â”€â”€ Swipe detection â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

    def on_touch_down(self, touch):
        if self.collide_point(*touch.pos):
            touch.ud['fears_swipe_start'] = (touch.x, touch.y)
            touch.ud['fears_swiping'] = False
        return super().on_touch_down(touch)

    def on_touch_move(self, touch):
        if touch.grab_current is self:
            start = touch.ud.get('fears_swipe_start')
            if start:
                dx = touch.x - start[0]
                w = self._content_area.width
                if self._page == 0:
                    offset = max(-w, min(0.0, dx))
                else:
                    offset = max(0.0, min(w, dx))
                self._update_sv_positions(offset)
            return True
        start = touch.ud.get('fears_swipe_start')
        if (start and not touch.ud.get('fears_swiping')
                and self.collide_point(*touch.pos)):
            dx = touch.x - start[0]
            dy = touch.y - start[1]
            if abs(dx) > dp(10) and abs(dx) > abs(dy) * 1.5:
                touch.ud['fears_swiping'] = True
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
            start = touch.ud.get('fears_swipe_start')
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

    # â”€â”€ Build: Encounter Card â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

    def _build_encounter_card(self) -> BorderCard:
        card = BorderCard(border_hex=T.GOLD)
        self._encounter_card = card
        card.add_widget(SectionLabel("FEAR ENCOUNTER", color_hex=T.GOLD, height_dp=30))

        self._enc_fear_lbl = CaptionLabel(
            "Select a fear from the list below first.",
            color_hex=T.TEXT_DIM, height_dp=20)
        # (not added to card â€” kept as data holder only)

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

        # Shell: Widget that reserves height in the card's BoxLayout.
        # Gold rail drawn on canvas; tabs and _enc_content are Widget children
        # positioned at absolute screen coords via _sync_shell_layout.
        self._enc_flow_shell = Widget(size_hint_y=None, height=0, opacity=0)
        clip_children(self._enc_flow_shell)
        with self._enc_flow_shell.canvas.before:
            Color(*T.k(T.GOLD))
            _rail_bar = Rectangle()
        def _upd_rail(w, *_, _rail_bar=_rail_bar):
            _rail_bar.pos  = (w.x, w.y)
            _rail_bar.size = (dp(4), w.height)
        self._enc_flow_shell.bind(pos=_upd_rail, size=_upd_rail)
        self._enc_flow_shell.bind(
            pos=lambda *_: self._sync_shell_layout(),
            size=lambda *_: self._sync_shell_layout(),
        )

        for _tab_key, _tab_lbl in (
            ("severity", "SEVERITY"),
            ("save", "SAVE"),
            ("sanity", "SANITY"),
            ("choice", "SELECT"),
        ):
            _tab = _EncTab(_tab_key, _tab_lbl, self._open_encounter_stage)
            self._enc_stage_tabs[_tab_key] = _tab
            self._enc_flow_shell.add_widget(_tab)

        # Content area: holds only the active stage panel at any time.
        self._enc_content = MDBoxLayout(
            orientation="vertical", spacing=dp(6),
            padding=[0, dp(8), 0, dp(8)],
            size_hint=(None, None), height=0)
        self._enc_content.bind(minimum_height=lambda *_: self._sync_shell_height())
        self._enc_flow_shell.add_widget(self._enc_content)

        # Info lines: calculation summaries shown beneath each roll row
        self._roll_info_lbl = MDLabel(
            text="", theme_text_color="Custom",
            text_color=T.k(T.TEXT_DIM), font_style="Caption",
            size_hint_y=None, height=dp(18))
        self._roll_info_lbl.bind(
            width=lambda inst, v: setattr(inst, "text_size", (v, None)),
            texture_size=lambda inst, size: setattr(inst, "height", max(dp(18), size[1])),
        )
        self._san_info_lbl = MDLabel(
            text="", theme_text_color="Custom",
            text_color=T.k(T.TEXT_DIM), font_style="Caption",
            size_hint_y=None, height=dp(18))
        self._san_info_lbl.bind(
            width=lambda inst, v: setattr(inst, "text_size", (v, None)),
            texture_size=lambda inst, size: setattr(inst, "height", max(dp(18), size[1])),
        )

        # Old-style encounter roll row: label + animated number
        self._enc_num_row = MDBoxLayout(
            orientation="horizontal",
            spacing=dp(6),
            size_hint_y=None,
            height=dp(56),
        )
        self._enc_roll_prefix = MDLabel(
            text="Wisdom Saving Throw:",
            bold=True,
            theme_text_color="Custom",
            text_color=T.k(T.WHITE),
            font_style="H5",
            adaptive_width=True,
            size_hint=(None, None),
            height=dp(56),
            halign="left",
            valign="middle",
        )
        self._enc_roll_num = MDLabel(
            text="--", bold=True, markup=True,
            theme_text_color="Custom", text_color=T.k(T.WHITE),
            font_style="H5", size_hint_x=1, size_hint_y=None, height=dp(56),
            halign="left", valign="middle")
        self._enc_num_row.add_widget(self._enc_roll_prefix)
        self._enc_num_row.add_widget(self._enc_roll_num)

        # Outcome label slides in after the spin
        self._outcome_lbl = MDLabel(
            text="", bold=True,
            theme_text_color="Custom", text_color=T.k(T.WHITE),
            font_style="H5", size_hint_y=None, height=0, opacity=0,
            halign="left", valign="middle")
        self._outcome_lbl.bind(size=lambda inst, *_: setattr(inst, "text_size", inst.size))

        def _mk_stage_panel(border_hex, min_height):
            panel = MDBoxLayout(
                orientation="vertical",
                spacing=dp(10),
                padding=[dp(14), dp(14), dp(14), dp(14)],
                size_hint_x=1, size_hint_y=None,
                adaptive_height=True,
            )
            panel._min_stage_height = dp(min_height)
            panel._stage_border_hex = border_hex
            panel._stage_fill_hex = border_hex
            panel._reveal_t = 1.0
            panel._reveal_evt = None
            with panel.canvas.before:
                panel._stage_bd_col = Color(*T.k(border_hex, 0.06))
                _bd = RoundedRectangle(radius=[0, dp(12), dp(12), 0])
                panel._stage_bg_col = Color(*T.k(border_hex, 0.018))
                _bg = RoundedRectangle(radius=[0, dp(11), dp(11), 0])
                panel._stage_line_col = Color(*T.k(border_hex))
                _line = Line(width=dp(1.6))

            def _upd_stage_panel(w, *_, _bd=_bd, _bg=_bg, _line=_line):
                reveal_t = max(0.0, min(1.0, getattr(w, "_reveal_t", 1.0)))
                vis_w = max(0, w.width * reveal_t)
                _bd.pos = w.pos
                _bd.size = (vis_w, w.height)
                _bg.pos = (w.x + 1, w.y + 1)
                _bg.size = (max(0, vis_w - 2), max(0, w.height - 2))
                x, y, ww, hh = w.x, w.y, w.width, w.height
                right_x = x + max(0, vis_w) - 1
                if vis_w <= dp(20):
                    _line.points = []
                else:
                    _line.points = [
                        x + dp(4), y + hh - 1,
                        right_x - dp(12), y + hh - 1,
                        right_x, y + hh - dp(12),
                        right_x, y + dp(12),
                        right_x - dp(12), y,
                        x + dp(4), y,
                    ]

            panel._stage_upd = lambda: _upd_stage_panel(panel)
            panel.bind(pos=_upd_stage_panel, size=_upd_stage_panel)
            return panel

        self._severity_stage_box = _mk_stage_panel(T.GOLD, 118)
        self._severity_name_lbl = MDLabel(
            text="",
            markup=True,
            bold=True,
            theme_text_color="Custom",
            text_color=T.k(T.TEXT_BRIGHT),
            font_style="Subtitle1",
            size_hint_y=None,
            adaptive_height=True,
            halign="left",
            valign="middle",
        )
        self._severity_name_lbl.bind(
            width=lambda inst, v: setattr(inst, "text_size", (v, None)),
            texture_size=lambda inst, size: setattr(inst, "height", max(dp(26), size[1])),
        )
        self._severity_stage_box.add_widget(self._severity_name_lbl)
        self._severity_effect_lbl = MDLabel(
            text="",
            markup=True,
            theme_text_color="Custom",
            text_color=T.k(T.TEXT_DIM),
            font_style="Body1",
            size_hint_y=None,
            adaptive_height=True,
            halign="left",
            valign="top",
        )
        self._severity_effect_lbl.bind(
            width=lambda inst, v: setattr(inst, "text_size", (v, None)),
            texture_size=lambda inst, size: setattr(inst, "height", max(dp(44), size[1])),
        )
        self._severity_stage_box.add_widget(self._severity_effect_lbl)

        self._save_stage_box = _mk_stage_panel(T.GOLD, 128)
        self._save_stage_box.add_widget(self._enc_num_row)
        self._save_stage_box.add_widget(self._roll_info_lbl)
        self._save_stage_box.add_widget(self._outcome_lbl)

        # Old-style sanity roll row: label + animated number
        self._san_num_row = MDBoxLayout(
            orientation="horizontal",
            spacing=dp(6),
            size_hint_y=None,
            height=dp(56),
        )
        self._san_prefix_lbl = MDLabel(
            text="Sanity Roll:",
            bold=True,
            theme_text_color="Custom",
            text_color=T.k(T.WHITE),
            font_style="H5",
            adaptive_width=True,
            size_hint=(None, None),
            height=dp(56),
            halign="left",
            valign="middle",
        )
        self._san_num_lbl = MDLabel(
            text="--", bold=True, markup=True,
            theme_text_color="Custom", text_color=T.k(T.WHITE),
            font_style="H5", size_hint_x=1, size_hint_y=None, height=dp(56),
            halign="left", valign="middle")
        self._san_num_row.add_widget(self._san_prefix_lbl)
        self._san_num_row.add_widget(self._san_num_lbl)
        self._san_section = _mk_stage_panel(T.PURPLE_LT, 118)
        self._san_section.add_widget(self._san_num_row)
        self._san_section.add_widget(self._san_info_lbl)

        # Preview box â€” shown after fail confirmed (two separate cards)
        # Negative h-padding bleeds through the encounter card's dp(12) padding
        # so the confront/avoid cards sit flush against the gold border (1dp inset).
        self._preview_box = MDBoxLayout(
            orientation="vertical",
            spacing=dp(10),
            padding=[0, dp(2), 0, 0],
            size_hint_x=1,
            size_hint_y=None,
            adaptive_height=True,
        )
        self._preview_box._min_stage_height = dp(188)
        self._preview_box._stage_border_hex = T.GOLD
        self._preview_box._stage_fill_hex = T.GOLD
        self._preview_box._reveal_t = 1.0
        self._preview_box._reveal_evt = None
        with self._preview_box.canvas.before:
            self._preview_box._stage_bd_col = Color(*T.k(T.GOLD, 0.06))
            _preview_bd = RoundedRectangle(radius=[0, dp(12), dp(12), 0])
            self._preview_box._stage_bg_col = Color(*T.k(T.GOLD, 0.018))
            _preview_bg = RoundedRectangle(radius=[0, dp(11), dp(11), 0])
            self._preview_box._stage_line_col = Color(*T.k(T.GOLD))
            _preview_line = Line(width=dp(1.6))

        def _upd_preview_stage_panel(w, *_, _bd=_preview_bd, _bg=_preview_bg, _line=_preview_line):
            reveal_t = max(0.0, min(1.0, getattr(w, "_reveal_t", 1.0)))
            vis_w = max(0, w.width * reveal_t)
            _bd.pos = w.pos
            _bd.size = (vis_w, w.height)
            _bg.pos = (w.x + 1, w.y + 1)
            _bg.size = (max(0, vis_w - 2), max(0, w.height - 2))
            x, y, ww, hh = w.x, w.y, w.width, w.height
            right_x = x + max(0, vis_w) - 1
            if vis_w <= dp(20):
                _line.points = []
            else:
                _line.points = [
                    x + dp(4), y + hh - 1,
                    right_x - dp(12), y + hh - 1,
                    right_x, y + hh - dp(12),
                    right_x, y + dp(12),
                    right_x - dp(12), y,
                    x + dp(4), y,
                ]

        self._preview_box._stage_upd = lambda: _upd_preview_stage_panel(self._preview_box)
        self._preview_box.bind(pos=_upd_preview_stage_panel, size=_upd_preview_stage_panel)

        # â”€â”€ Card + metric-row factory helpers â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
        def _mk_outer_card(border_hex):
            """Option card that reveals with the same rail-emerge motion as stage cards."""
            box = MDBoxLayout(
                orientation="vertical", spacing=dp(6),
                padding=[dp(10), dp(10), dp(10), dp(10)],
                adaptive_height=True)
            box._stage_border_hex = border_hex
            box._stage_fill_hex = border_hex
            box._reveal_t = 1.0
            box._reveal_evt = None
            with box.canvas.before:
                # Tinted fill â€” subtle shade of the card colour
                box._stage_bd_col = Color(*T.k(border_hex, 0.06))
                _bd = RoundedRectangle(radius=[0, dp(12), dp(12), 0])
                box._stage_bg_col = Color(*T.k(border_hex, 0.018))
                _bg = RoundedRectangle(radius=[0, dp(11), dp(11), 0])
                # 3-sided border: top â†’ right â†’ bottom  (left side open)
                box._stage_line_col = Color(*T.k(border_hex))
                _line = Line(width=dp(1.6))
            def _upd(w, *_, _bd=_bd, _bg=_bg, _line=_line):
                reveal_t = max(0.0, min(1.0, getattr(w, "_reveal_t", 1.0)))
                vis_w = max(0, w.width * reveal_t)
                _bd.pos = w.pos
                _bd.size = (vis_w, w.height)
                _bg.pos = (w.x + 1, w.y + 1)
                _bg.size = (max(0, vis_w - 2), max(0, w.height - 2))
                x, y, ww, hh = w.x, w.y, w.width, w.height
                right_x = x + max(0, vis_w) - 1
                if vis_w <= dp(20):
                    _line.points = []
                else:
                    _line.points = [
                        x + dp(4), y + hh - 1,
                        right_x - dp(12), y + hh - 1,
                        right_x, y + hh - dp(12),
                        right_x, y + dp(12),
                        right_x - dp(12), y,
                        x + dp(4), y,
                    ]
            box.bind(pos=_upd, size=_upd)
            box._stage_upd = lambda: _upd(box)
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
                theme_text_color="Custom", text_color=T.k(T.WHITE),
                font_style="Caption",
                size_hint_y=None, height=dp(16)))

            val_lbl = MDLabel(
                text="", markup=True,
                theme_text_color="Custom", text_color=T.k(T.TEXT_BRIGHT),
                font_style="Caption",
                size_hint_y=None, height=dp(18))
            val_lbl.bind(
                width=lambda inst, v: setattr(inst, "text_size", (v, None)),
                texture_size=lambda inst, size: setattr(inst, "height", max(dp(18), size[1])),
            )

            content.add_widget(val_lbl)
            row.add_widget(content)
            return row, val_lbl

        # â”€â”€â”€ CONFRONT card â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
        self._confront_card = _mk_outer_card(T.BLOOD_LT)
        self._confront_card.opacity = 0
        self._confront_card._reveal_t = 0.0

        self._confront_card.add_widget(MDLabel(
            text="CONFRONT", bold=True,
            theme_text_color="Custom", text_color=T.k(T.BLOOD_LT),
            font_style="Subtitle1",
            size_hint_y=None, height=dp(28),
            halign="left", valign="middle"))

        _csan_row, self._conf_sanity_lbl = _mk_metric_row("SANITY LOSS", T.PURPLE_LT)
        self._confront_card.add_widget(_csan_row)

        _cdes_row, self._conf_desens_lbl = _mk_metric_row("DESENSITIZATION", T.DESENS_LT)
        self._confront_card.add_widget(_cdes_row)

        self._push_btn = MDRaisedButton(
            text="CONFRONT", md_bg_color=T.k(T.BLOOD),
            size_hint_x=1, size_hint_y=None, height=dp(44),
            disabled=True, on_release=self._on_push)
        self._confront_card.add_widget(self._push_btn)

        # â”€â”€â”€ AVOID card â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
        self._avoid_card = _mk_outer_card(T.STAGE_1)
        self._avoid_card.opacity = 0
        self._avoid_card._reveal_t = 0.0

        self._avoid_card.add_widget(MDLabel(
            text="AVOID", bold=True,
            theme_text_color="Custom", text_color=T.k(T.GREEN),
            font_style="Subtitle1",
            size_hint_y=None, height=dp(28),
            halign="left", valign="middle"))

        _asan_row, self._avd_sanity_lbl = _mk_metric_row("SANITY GAIN", T.PURPLE_LT)
        self._avoid_card.add_widget(_asan_row)

        _asev_row, self._avd_sev_lbl = _mk_metric_row("SEVERITY", T.GOLD_LT)
        self._avoid_card.add_widget(_asev_row)

        _ades_row, self._avd_desens_lbl = _mk_metric_row("DESENSITIZATION", T.DESENS_LT)
        self._avoid_card.add_widget(_ades_row)

        self._avoid_btn = MDRaisedButton(
            text="AVOID", md_bg_color=T.k(T.GREEN),
            size_hint_x=1, size_hint_y=None, height=dp(44),
            disabled=True, on_release=self._on_avoid)
        self._avoid_card.add_widget(self._avoid_btn)

        self._preview_box.add_widget(self._confront_card)
        self._preview_box.add_widget(self._avoid_card)

        # Sanity result shown after resolving
        self._san_result_lbl = MDLabel(
            text="", theme_text_color="Custom",
            text_color=T.k(T.WHITE), font_style="Caption",
            size_hint_y=None, height=0)

        # Hope row â€” centred, hidden until a fail result with active hope
        self._hope_row = MDBoxLayout(
            size_hint_y=None, height=0, opacity=0,
            padding=[0, dp(4), 0, dp(4)])
        self._hope_btn = HopeButton(on_use=self._use_hope)
        self._hope_row.add_widget(self._hope_btn)
        self._hope_row.add_widget(Widget())
        self._save_stage_box.add_widget(self._hope_row)


        card.add_widget(self._enc_flow_shell)
        return card

    # â”€â”€ Build: Fear Add Row â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

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

    # â”€â”€ Build: Fear List Card â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

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

    # â”€â”€ Build: Severity Section (accordion) â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

    def _build_severity_section(self) -> BorderCard:
        card = BorderCard(border_hex=T.GOLD_DK)
        card.add_widget(SectionLabel("FEAR SEVERITY", color_hex=T.GOLD))

        self._sev_items = {}

        for s in range(1, 5):
            info = FEAR_STAGES[s]
            sev_label = f"Level {s} | {info.dice}d4 Sanity loss"

            ec = ExpandingEffectCard(
                on_tap=lambda w, stage=s: self._on_severity_select(stage))
            ec.title_text    = info.name
            ec.subtitle_text = sev_label
            ec.detail_body   = info.desc
            ec.accent_rgba   = list(T.k(info.color))
            card.add_widget(ec)

            self._sev_items[s] = ec

        return card

    # â”€â”€ Build: Fear Desensitization Section (accordion) â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

    def _build_desens_section(self) -> BorderCard:
        card = BorderCard(border_hex=T.GOLD_DK)
        card.add_widget(SectionLabel("FEAR DESENSITIZATION", color_hex=T.GOLD))

        self._desens_items = {}

        for r in range(1, 5):
            color = DESENS_RUNG_COLORS[r]

            ec = ExpandingEffectCard(
                on_tap=lambda w, rung=r: self._on_desens_select(rung))
            ec.title_text    = DESENS_NAMES[r]
            ec.subtitle_text = f"Level {r}  |  DC {DESENS_DC[r]}"
            ec.detail_body   = DESENS_DESCS[r]
            ec.accent_rgba   = list(T.k(color))
            card.add_widget(ec)

            self._desens_items[r] = ec

        return card

    # â”€â”€ Build: Rules Panel â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

    def _build_rules_panel(self) -> BorderCard:
        wrapper = BorderCard(border_hex=T.GOLD)
        sec = ExpandableSection(
            "FEAR RULES",
            accent_hex=T.GOLD,
        )
        populate_rules_section(sec, FEAR_RULES_TEXT, T.GOLD)
        wrapper.add_widget(sec)
        return wrapper

    # â”€â”€ Internal helpers â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

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

    def _sync_shell_layout(self, *_):
        """Position tabs and place the active panel directly under its tab."""
        s = self._enc_flow_shell
        history = self._stage_history_keys()
        n = len(history)
        content_h = max(0, self._enc_content.minimum_height)
        active = self._enc_active_stage if self._enc_active_stage in history else None
        active_idx = history.index(active) if active else -1
        content_gap = dp(8) if active_idx >= 0 else 0
        tabs_total = (
            _EncTab._TOP_PAD + n * _EncTab._TAB_H + (n - 1) * _EncTab._TAB_GAP
        ) if n else 0
        shell_h = max(s.height, tabs_total + (content_h + content_gap if active_idx >= 0 else 0))
        self._enc_content.x = s.x
        self._enc_content.width = s.width
        self._enc_content.height = content_h
        if active_idx >= 0:
            tabs_above = _EncTab._TOP_PAD + active_idx * (_EncTab._TAB_H + _EncTab._TAB_GAP) + _EncTab._TAB_H
            self._enc_content.y = s.y + shell_h - tabs_above - content_gap - content_h
        else:
            self._enc_content.y = s.y
        self._layout_stage_tabs(animated=False)

    def _sync_shell_height(self, *_):
        """Compute shell height from tabs with the active panel inserted below its tab."""
        h_content = self._enc_content.minimum_height
        active = self._enc_active_stage
        if active:
            h_content = max(h_content, getattr(self._enc_stage_child(active),
                                               "_min_stage_height", 0))
        n = len(self._stage_history_keys())
        tabs_h = (
            _EncTab._TOP_PAD + n * _EncTab._TAB_H + (n - 1) * _EncTab._TAB_GAP
        ) if n else 0
        content_gap = dp(8) if active else 0
        h = tabs_h + content_gap + h_content
        self._enc_content.height = h_content
        self._enc_flow_shell.height = h
        self._layout_stage_tabs(animated=False)

    def _focus_encounter_card(self, animate: bool = True):
        card = getattr(self, "_encounter_card", None)
        if card is None or self._page != 0:
            return

        def _do_focus(dt):
            try:
                self._sv0.scroll_to(card, padding=dp(10), animate=animate)
            except Exception:
                self._sv0.scroll_y = 1

        Clock.schedule_once(_do_focus, 0)

    def _enc_stage_child(self, key: str):
        return {
            "severity": self._severity_stage_box,
            "save":   self._save_stage_box,
            "sanity": self._san_section,
            "choice": self._preview_box,
        }[key]

    def _stage_history_keys(self):
        return [k for k in ("severity", "save", "sanity", "choice") if self._enc_stage_tabs[k]._shown]

    def _tab_stack_y(self, idx: int) -> float:
        """Absolute screen Y for tab at stack position idx, accounting for inserted content."""
        s = self._enc_flow_shell
        history = self._stage_history_keys()
        n = max(1, len(history))
        active = self._enc_active_stage if self._enc_active_stage in history else None
        active_idx = history.index(active) if active else -1
        content_h = max(0, self._enc_content.height)
        gap = dp(8) if active_idx >= 0 else 0
        rail_min_h = _EncTab._TOP_PAD + n * _EncTab._TAB_H + (n - 1) * _EncTab._TAB_GAP
        h = max(s.height, rail_min_h + (content_h + gap if active_idx >= 0 else 0))
        extra = content_h + gap if active_idx >= 0 and idx > active_idx else 0
        local_y = h - _EncTab._TOP_PAD - (idx + 1) * _EncTab._TAB_H - idx * _EncTab._TAB_GAP - extra
        return s.y + local_y

    def _tab_spawn_y(self, tab: _EncTab) -> float:
        """Spawn above the shell top so the tab slides down into its slot."""
        s = self._enc_flow_shell
        return s.y + s.height + tab.height

    def _layout_stage_tabs(self, animated: bool = False):
        """Place every visible tab at absolute screen coords, top-first."""
        s = self._enc_flow_shell
        for idx, key in enumerate(self._stage_history_keys()):
            tab = self._enc_stage_tabs[key]
            tx  = s.x
            ty  = self._tab_stack_y(idx)
            if animated:
                Animation.cancel_all(tab, "x", "y")
                Animation(x=tx, y=ty, duration=0.22, t="in_out_cubic").start(tab)
            else:
                tab.x = tx
                tab.y = ty

    def _set_stage_available(self, key: str, available: bool = True):
        tab = self._enc_stage_tabs[key]
        if available and not tab._shown:
            tab._shown = True
            tab.x = self._enc_flow_shell.x
            tab.y = self._tab_stack_y(len(self._stage_history_keys()) - 1)
            tab.width = _EncTab._TAB_W
            tab.height = _EncTab._TAB_H
            tab.appear(rail_x=self._enc_flow_shell.x, start_y=self._tab_spawn_y(tab))
            self._refresh_tab_highlights(layout_tabs=False)
            Clock.schedule_once(lambda *_: self._layout_stage_tabs(animated=True), 0)
            return
        if not available:
            Animation.cancel_all(tab)
            if tab._commit_evt:
                tab._commit_evt.cancel()
                tab._commit_evt = None
            tab.opacity       = 0
            tab._shown        = False
            tab._tab_state    = None
            tab._dim_pending  = False
            tab._commit_done  = False
            tab._side_live    = False
            tab._clear_stroke_art()
            tab._stroke_col.a = 0
            tab._side_divider_rect.size = (0, 0)
            tab._side_divider_col.a = 0
            tab._side_rect.size = (0, 0)
            tab._side_line.points = []
            tab._side_col.a = 0
            tab.x = self._enc_flow_shell.x
            tab.y = self._tab_spawn_y(tab)
            tab._fill_col.rgba   = (0, 0, 0, 0)
            tab._accent_col.rgba = (0, 0, 0, 0)
        self._refresh_tab_highlights()

    def _refresh_tab_highlights(self, layout_tabs: bool = True, animated: bool = False):
        history = self._stage_history_keys()
        active  = self._enc_active_stage
        latest  = history[-1] if history else None
        try:
            act_idx = history.index(active) if active else -1
        except ValueError:
            act_idx = -1
        for idx, key in enumerate(history):
            tab = self._enc_stage_tabs[key]
            if idx == act_idx and key != latest:
                tab.set_state("done_old")
                tab.opacity = 0.72
            elif idx == act_idx:
                tab.set_state("active")
                tab.opacity = 1.0
            elif idx == act_idx - 1:
                tab.set_state("done_new")
                tab.opacity = 1.0
            else:
                tab.set_state("done_old")
                tab.opacity = 1.0
        if layout_tabs:
            self._layout_stage_tabs(animated=animated)

    def _play_tab_commit(self, key: str, total_duration: float = 0.84, on_complete=None):
        """Fire the sweep on one tab, lasting total_duration seconds."""
        tab = self._enc_stage_tabs.get(key)
        if tab is None or not tab._shown:
            if on_complete:
                on_complete()
            return
        tab.play_commit_anim(
            rail_bottom=self._enc_flow_shell.y,
            total_duration=total_duration,
            on_complete=on_complete,
        )

    def _animate_stage_reveal(self, panel, duration: float = 0.24):
        if getattr(panel, "_reveal_evt", None):
            panel._reveal_evt.cancel()
            panel._reveal_evt = None
        panel._reveal_t = 0.0
        panel.opacity = 0.0
        if hasattr(panel, "_stage_upd"):
            panel._stage_upd()

        start_t = Clock.get_boottime()

        def _tick(dt):
            prog = min(1.0, (Clock.get_boottime() - start_t) / max(0.001, duration))
            eased = 1.0 - pow(1.0 - prog, 3)
            panel._reveal_t = eased
            panel.opacity = eased
            if hasattr(panel, "_stage_upd"):
                panel._stage_upd()
            if prog >= 1.0:
                panel._reveal_evt = None
                return False
            return True

        panel._reveal_evt = Clock.schedule_interval(_tick, 1 / 60)

    def _open_encounter_stage(self, key: str, animate: bool = True):
        """Swap the active stage panel into _enc_content."""
        panels = {
            "severity": self._severity_stage_box,
            "save":   self._save_stage_box,
            "sanity": self._san_section,
            "choice": self._preview_box,
        }
        target = panels[key]
        for k, child in panels.items():
            if k != key and child.parent is self._enc_content:
                self._enc_content.remove_widget(child)
        if target.parent is not self._enc_content:
            if animate:
                self._enc_content.add_widget(target)
                self._animate_stage_reveal(target)
            else:
                target._reveal_t = 1.0
                target.opacity = 1
                if hasattr(target, "_stage_upd"):
                    target._stage_upd()
                self._enc_content.add_widget(target)
        self._enc_active_stage = key
        self._refresh_tab_highlights()
        Clock.schedule_once(lambda dt: self._sync_shell_height(), 0)
        Clock.schedule_once(lambda dt: self._focus_encounter_card(animate=animate), 0)

    def _settle_active_encounter_layout(self, *_):
        if not self._enc_active_stage:
            return
        self._sync_shell_height()
        self._layout_stage_tabs(animated=False)

    def _reset_enc_ui(self):
        """Reset all encounter widget states for a fresh encounter."""
        self._set_stage_panel_color(self._severity_stage_box, T.GOLD)
        self._set_stage_panel_color(self._save_stage_box, T.GOLD)
        self._set_stage_panel_color(self._san_section, T.PURPLE_LT)
        self._roll_info_lbl.opacity   = 0
        self._roll_info_lbl.text      = ""
        self._san_info_lbl.opacity    = 0
        self._san_info_lbl.text       = ""
        self._severity_name_lbl.text  = ""
        self._severity_effect_lbl.text = ""
        self._enc_num_row.height      = dp(56)
        self._enc_num_row.opacity     = 1
        self._enc_roll_num.text       = "--"
        self._enc_roll_num.text_color = T.k(T.WHITE)
        self._outcome_lbl.text        = ""
        self._outcome_lbl.height      = 0
        self._outcome_lbl.opacity     = 0
        self._san_num_row.height      = dp(56)
        self._san_num_row.opacity     = 1
        self._san_num_lbl.text        = "--"
        self._san_num_lbl.text_color  = T.k(T.WHITE)
        self._hope_row.height         = 0
        self._hope_row.opacity        = 0
        self._confront_card.opacity   = 0
        self._avoid_card.opacity      = 0
        self._confront_card._reveal_t = 0.0
        self._avoid_card._reveal_t    = 0.0
        if hasattr(self._confront_card, "_stage_upd"):
            self._confront_card._stage_upd()
        if hasattr(self._avoid_card, "_stage_upd"):
            self._avoid_card._stage_upd()
        self._conf_sanity_lbl.text    = ""
        self._conf_desens_lbl.text    = ""
        self._avd_sanity_lbl.text     = ""
        self._avd_sev_lbl.text        = ""
        self._avd_desens_lbl.text     = ""
        self._san_result_lbl.text     = ""
        self._push_btn.disabled       = True
        self._avoid_btn.disabled      = True
        self._enc_active_stage        = None
        for key in self._enc_stage_tabs:
            self._enc_stage_tabs[key]._cap_hex = None
        for key in self._enc_stage_tabs:
            self._set_stage_available(key, False)

    def _show_roll_panel(self, on_ready=None):
        """Reset and reveal the encounter shell, then let the caller start stages."""
        shell = self._enc_flow_shell
        shell.height  = 0
        shell.opacity = 0
        self._enc_content.height = 0
        self._reset_enc_ui()
        def _do_anim(dt):
            if on_ready:
                on_ready()
            self._sync_shell_height()
            Animation(opacity=1, duration=0.22, t="out_quart").start(shell)
            self._focus_encounter_card()
        Clock.schedule_once(_do_anim, 0)
        Clock.schedule_once(lambda dt: setattr(self._sv0, "scroll_y", 1), 0.12)

    def _end_enc(self):
        self._enc.reset()
        for panel in (
            self._severity_stage_box,
            self._save_stage_box,
            self._san_section,
            self._preview_box,
        ):
            if panel.parent is self._enc_content:
                self._enc_content.remove_widget(panel)
        self._enc_content.height     = 0
        self._enc_flow_shell.height  = 0
        self._enc_flow_shell.opacity = 0
        self._reset_enc_ui()

    def _set_stage_panel_color(self, panel, color_hex: str):
        panel._stage_border_hex = color_hex
        panel._stage_fill_hex = color_hex
        if hasattr(panel, "_stage_header_lbl"):
            panel._stage_header_lbl.text_color = T.k(color_hex)
        if hasattr(panel, "_stage_bd_col"):
            panel._stage_bd_col.rgba = T.k(color_hex, 0.06)
        if hasattr(panel, "_stage_bg_col"):
            panel._stage_bg_col.rgba = T.k(color_hex, 0.018)
        if hasattr(panel, "_stage_line_col"):
            panel._stage_line_col.rgba = T.k(color_hex)
        if hasattr(panel, "_stage_upd"):
            panel._stage_upd()

    def _set_encounter_severity_preview(self, fear_name: str, stage: int):
        info = FEAR_STAGES[stage]
        self._enc_stage_tabs["severity"]._cap_hex = info.color
        self._set_stage_panel_color(self._severity_stage_box, info.color)
        self._severity_name_lbl.text = (
            f"[color={T.GOLD_LT}]{fear_name}[/color]  |  "
            f"[color={info.color}]{info.name}[/color]"
        )
        extra = ""
        if stage == 4:
            extra = f"\n\n[color={T.BLOOD_LT}]Encounter start: +1 Exhaustion incoming.[/color]"
        self._severity_effect_lbl.text = f"[color={info.color}]{info.desc}[/color]{extra}"
        self._refresh_tab_highlights(layout_tabs=False)

    def _start_save_stage(self, wis_save: int, dc: int):
        self._set_stage_available("save", True)
        self._open_encounter_stage("save")
        Clock.schedule_once(lambda _: self._animate_roll_result(wis_save, dc), 0.16)

    def _start_severity_stage(self, fear_name: str, stage: int, wis_save: int, dc: int):
        self._set_encounter_severity_preview(fear_name, stage)
        self._set_stage_available("severity", True)
        self._open_encounter_stage("severity", animate=False)
        _spin_intervals = [0.022] * 12 + [0.065] * 5 + [0.17] * 4
        _spin_t = sum(_spin_intervals)
        _sweep_dur = _spin_t + 0.30 + 0.30 + 0.22
        self._play_tab_commit(
            "severity",
            total_duration=_sweep_dur,
            on_complete=lambda: Clock.schedule_once(
                lambda _: self._start_save_stage(wis_save, dc), 0.12
            ),
        )


    def _update_severity_visuals(self, expand=None, animate=False):
        if not self._sev_items:
            return
        if expand is not None:
            self._sev_expanded = expand
        if not self._selected_fear:
            for card in self._sev_items.values():
                if card.open_state:
                    card.set_open(False, animate=animate)
            return
        for s, card in self._sev_items.items():
            should_open = (s == self._stage) and self._sev_expanded
            if card.open_state != should_open:
                card.set_open(should_open, animate=animate)

    def _update_desens_visuals(self, expand=None, animate=False):
        if not self._desens_items:
            return
        if expand is not None:
            self._des_expanded = expand
        app  = self._app()
        name = self._selected_fear
        if not name:
            for card in self._desens_items.values():
                if card.open_state:
                    card.set_open(False, animate=animate)
            return
        cur_rung = app.fm.get_desens(name)
        for r, card in self._desens_items.items():
            should_open = (r == cur_rung) and self._des_expanded
            if card.open_state != should_open:
                card.set_open(should_open, animate=animate)

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

    def _severity_transition_markup(self, old_stage: int, new_stage: int) -> str:
        old_info = FEAR_STAGES[old_stage]
        new_info = FEAR_STAGES[new_stage]
        old_name = old_info.name.split()[0]
        new_name = new_info.name.split()[0]
        return (
            f"[color={old_info.color}]{old_name}[/color] "
            f"[color={T.TEXT_DIM}][font=Symbols]\u2192[/font][/color] "
            f"[color={new_info.color}]{new_name}[/color]"
        )

    def _desens_transition_markup(self, old_rung: int, new_rung: int) -> str:
        old_name = DESENS_NAMES[old_rung].split()[0]
        new_name = DESENS_NAMES[new_rung].split()[0]
        old_col = DESENS_RUNG_COLORS[old_rung]
        new_col = DESENS_RUNG_COLORS[new_rung]
        return (
            f"[color={old_col}]{old_name}[/color] "
            f"[color={T.TEXT_DIM}][font=Symbols]\u2192[/font][/color] "
            f"[color={new_col}]{new_name}[/color]"
        )

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

    def _loss_threshold_preview(self, old_val: int, loss_amt: int, max_s: int) -> tuple[str, str]:
        if max_s <= 0:
            return ("No threshold", T.TEXT_DIM)
        new_val = max(0, old_val - max(0, loss_amt))
        if new_val == 0:
            return ("Sanity reaches 0!", T.BLOOD)
        old_pct = old_val / max_s
        new_pct = new_val / max_s
        existing_kinds = {m.kind for m in self._app().state.madnesses}
        outcomes = []
        for _label, thresh, kind in THRESHOLDS:
            if kind == "zero":
                continue
            if old_pct > thresh >= new_pct:
                if kind in existing_kinds and kind != "indefinite":
                    outcomes.append((f"Cured {self._kind_label(kind)} Insanity", self._kind_color(kind)))
                else:
                    outcomes.append((f"{self._kind_label(kind)} Insanity", self._kind_color(kind)))
        return outcomes[-1] if outcomes else ("No threshold crossed", T.TEXT_DIM)

    def _recovery_threshold_preview(self, old_val: int, gain_amt: int, max_s: int) -> tuple[str, str]:
        if max_s <= 0:
            return ("No threshold", T.TEXT_DIM)
        new_val = min(max_s, old_val + max(0, gain_amt))
        old_pct = old_val / max_s
        new_pct = new_val / max_s
        existing_kinds = {m.kind for m in self._app().state.madnesses}
        outcomes = []
        for _label, thresh, kind in THRESHOLDS:
            if kind == "zero":
                continue
            if old_pct <= thresh < new_pct:
                if kind in existing_kinds and kind != "indefinite":
                    outcomes.append((f"Cured {self._kind_label(kind)} Insanity", self._kind_color(kind)))
        return outcomes[-1] if outcomes else ("No threshold crossed", T.TEXT_DIM)

    # â”€â”€ Public refresh â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

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
                item = SwipeFillListItem(
                    primary=name,
                    secondary=secondary,
                    accent_hex=T.GOLD,
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
            w.set_selected(True, persist=True, animate=False)
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

    # â”€â”€ Event: Severity selection â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

    def _on_severity_select(self, s: int):
        # Toggle: tap the active row again to collapse it
        same_stage = (s == self._stage)
        self._stage = s
        self._sev_expanded = not (same_stage and self._sev_expanded)
        self._update_severity_visuals(animate=True)
        self._update_effects_banner()
        if self._selected_fear:
            app  = self._app()
            name = self._selected_fear
            old_stage = app.fm.get_stage(name)
            self._push_undo()
            app.fm.set_stage(name, s)
            # Defer refresh past animation (0.28s) so it doesn't cancel the card open
            Clock.schedule_once(lambda dt: self.refresh(), 0.35)
            self._save()
            self._log(f"  {name}: Severity > {FEAR_STAGES[s].name}")
            info = FEAR_STAGES[s]
            if old_stage != s:
                app.notify_event(
                    f"{name} Severity: {self._severity_transition_markup(old_stage, s)}",
                    "fears", info.color,
                    action_cb=lambda st=s: self.open_severity(st))

    # â”€â”€ Event: Desens rung selection â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

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
        self._update_desens_visuals(animate=True)
        self._update_effects_banner()
        self._autofill_dc()
        self._log(f"  {name}: Desensitization > {DESENS_NAMES[rung]}")
        # Defer refresh past animation (0.28s) so it doesn't cancel the card open
        Clock.schedule_once(lambda dt: self.refresh(), 0.35)
        self._save()
        if cur_rung != rung:
            app.notify_event(
                f"{name} Desensitization: {self._desens_transition_markup(cur_rung, rung)}",
                "fears", DESENS_RUNG_COLORS[rung],
                action_cb=lambda rr=rung: self.open_desens(rr))

    # â”€â”€ Event: Fear tap â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

    def _on_fear_tap(self, widget: SwipeFillListItem, name: str):
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

    # â”€â”€ Event: Add fear â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

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

    # â”€â”€ Event: Encounter â€” Step 1: roll WIS save â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

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

        # Extreme Severity: delayed exhaustion buffer
        if False and stage == 4:
            self._push_undo()
            app.state.exhaustion = int(clamp(app.state.exhaustion + 1, 0, 6))
            self._log("Extreme Severity â€” +1 Exhaustion applied before encounter")
            app.refresh_all()
            _exh = app.state.exhaustion
            Clock.schedule_once(lambda _: app.notify_exhaustion(_exh), 0.5)

        if stage == 4:
            def _apply_extreme_exhaustion(_dt):
                if not self._enc.active or self._enc.fear_name != name or self._enc.fear_stage != 4:
                    return
                self._push_undo()
                app.state.exhaustion = int(clamp(app.state.exhaustion + 1, 0, 6))
                self._log("Extreme Severity: +1 Exhaustion applied shortly after encounter start")
                app.refresh_all()
                _exh = app.state.exhaustion
                Clock.schedule_once(lambda _: app.notify_exhaustion(_exh), 0.1)
            Clock.schedule_once(_apply_extreme_exhaustion, 0.85)

        wis_mod = app.state.wis_mod
        if getattr(app, 'wis_adv', False):
            rolls = roll_d(20, 2)
            d20 = max(rolls)
            roll_str = f"D20 Adv({rolls[0]},{rolls[1]})â†’{d20}"
        else:
            d20 = roll_d(20)[0]
            roll_str = f"D20({d20})"
        wis_save = d20 + wis_mod
        self._enc.wis_save_total = wis_save
        info     = FEAR_STAGES[stage]

        self._log(f"=== ENCOUNTER: {name} ({info.name}) ===")
        self._log(f"Desens: {DESENS_NAMES[rung]}  |  Rung {rung}  |  DC {dc}")
        self._log(f"WIS Save: {roll_str} + {wis_mod:+d} = {wis_save} vs DC {dc}")

        self._enc_wis_roll_info = (
            f"WIS Save: {roll_str} + WIS({wis_mod:+d}) = {wis_save} VS DC {dc}"
        )
        self._roll_info_lbl.text = ""
        self._roll_info_lbl.opacity = 0

        self._show_roll_panel(
            on_ready=lambda: self._start_severity_stage(name, stage, wis_save, dc)
        )

        # â”€â”€ Severity effects popup â€” fires immediately when encounter opens â”€â”€
    def _spin_number(self, lbl, target: int, max_val: int, on_land):
        """Animate a spinning-number effect on lbl, landing on target.

        Schedules all frame updates via Clock.schedule_once.
        Calls on_land after total_spin_time + 0.30s.
        Returns total_spin_time.
        """
        intervals = [0.022] * 12 + [0.065] * 5 + [0.17] * 4
        n_frames  = len(intervals)
        td        = ((target - 1) % max_val) + 1
        s0        = (td - 1 - n_frames) % max_val
        sv        = s0 + 1
        t         = 0.0
        for i, iv in enumerate(intervals):
            t += iv
            num = ((sv - 1 + i) % max_val) + 1
            Clock.schedule_once(
                (lambda n: lambda dt: setattr(lbl, "text", str(n)))(num),
                t)
        Clock.schedule_once(on_land, t + 0.30)
        return t

    def _animate_roll_result(self, wis_save: int, dc: int):
        """WIS save spin + sweep run together; sweep ends when outcome is shown."""
        passed     = wis_save >= dc
        final_rgba = T.k(T.GREEN) if passed else T.k(T.BLOOD)

        self._push_btn.disabled       = True
        self._avoid_btn.disabled      = True
        self._enc_roll_num.text       = "--"
        self._enc_roll_num.text_color = T.k(T.WHITE)
        self._roll_info_lbl.text      = ""
        self._roll_info_lbl.opacity   = 0
        self._outcome_lbl.text        = ""
        self._outcome_lbl.height      = 0
        self._outcome_lbl.opacity     = 0

        def _continue_flow():
            if not passed and self._app().state.hope:
                self._hope_row.height  = dp(108)
                self._hope_row.opacity = 1
                Clock.schedule_once(lambda dt: self._sync_shell_height(), 0.25)
            if passed:
                Clock.schedule_once(self._on_pass, 0.55)
            else:
                Clock.schedule_once(self._on_confirm_fail, 0.42)

        def _slide_in_outcome(dt):
            self._outcome_lbl.text       = "PASSED" if passed else "FAILED"
            self._outcome_lbl.text_color = final_rgba
            Animation(
                height=dp(44), opacity=1,
                duration=0.22, t="out_cubic"
            ).start(self._outcome_lbl)
            Clock.schedule_once(lambda dt: self._sync_shell_height(), 0.10)

        def _land(dt):
            self._enc_roll_num.text = str(wis_save)
            base_sz = self._enc_roll_num.font_size
            (Animation(font_size=base_sz * 1.22, duration=0.06, t="out_quad") +
             Animation(font_size=base_sz, duration=0.20, t="out_back")
            ).start(self._enc_roll_num)
            Animation(text_color=final_rgba, duration=0.25,
                      t="out_quad").start(self._enc_roll_num)
            self._roll_info_lbl.text = getattr(self, "_enc_wis_roll_info", "")
            Animation(opacity=1, duration=0.18, t="out_quad").start(self._roll_info_lbl)
            Clock.schedule_once(lambda dt: self._sync_shell_height(), 0.02)
            Clock.schedule_once(_slide_in_outcome, 0.30)

        # Sweep duration = spin_time + land_delay + outcome_delay + outcome_anim ≈ 2.09s
        _spin_intervals = [0.022] * 12 + [0.065] * 5 + [0.17] * 4
        _spin_t = sum(_spin_intervals)
        _sweep_dur = _spin_t + 0.30 + 0.30 + 0.22  # land_delay + outcome_delay + outcome_anim

        # Start sweep and spin at the same moment
        self._play_tab_commit("save", total_duration=_sweep_dur, on_complete=_continue_flow)
        self._spin_number(self._enc_roll_num, wis_save, 20, _land)

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
        """Roll sanity dice immediately after a failed save and show preview."""
        app   = self._app()
        stage = self._enc.fear_stage or 1
        info  = FEAR_STAGES[stage]

        rolls = roll_d(4, info.dice)
        total = sum(rolls)
        rt    = "+".join(map(str, rolls))
        self._enc.roll_total = total
        san_roll_info = f"Sanity: {info.dice}d4 ({rt}) = {total}"
        self._san_info_lbl.text = ""
        self._san_info_lbl.opacity = 0

        self._log(f"Failed save -- sanity roll: {info.dice}d4 ({rt}) = {total}")

        _max_val = max(4, info.dice * 4)

        self._san_num_lbl.text       = "--"
        self._san_num_lbl.text_color = T.k(T.WHITE)

        cur   = app.state.current_sanity
        max_s = app.state.max_sanity
        confront_val  = max(0, cur - total)
        avoid_val     = min(max_s, cur + total)
        thresh_label, thresh_color = self._loss_threshold_preview(cur, total, max_s)

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
        _D   = T.TEXT_DIM
        _ARR = f" [color={_D}][font=Symbols]\u2192[/font][/color] "

        def _desens_short(rung):
            return DESENS_NAMES[rung].split()[0]

        def _sev_short(s):
            return FEAR_STAGES[s].name

        # ── CONFRONT card labels ──────────────────────────────────────────────
        _thresh_suffix = (
            f"  [color={_D}][font=Symbols]\u2192[/font][/color]  [color={thresh_color}]{thresh_label}[/color]"
            if thresh_label not in ("No threshold crossed", "No threshold") else "")

        confront_pct = int(confront_val / max_s * 100) if max_s else 0
        self._conf_sanity_lbl.text = (
            f"[color={T.PURPLE_LT}]{cur} - {total} = {confront_val} ({confront_pct}%)[/color]"
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
        avoid_thresh_label, avoid_thresh_color = self._recovery_threshold_preview(cur, total, max_s)
        _avoid_thresh_suffix = (
            f"  [color={_D}][font=Symbols]\u2192[/font][/color]  [color={avoid_thresh_color}]{avoid_thresh_label}[/color]"
            if avoid_thresh_label not in ("No threshold crossed", "No threshold") else ""
        )
        avoid_pct = int(avoid_val / max_s * 100) if max_s else 0
        self._avd_sanity_lbl.text = (
            f"[color={T.PURPLE_LT}]{cur} + {total} = {avoid_val} ({avoid_pct}%)[/color]"
            f"{_avoid_thresh_suffix}"
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

        self._push_btn.disabled  = True
        self._avoid_btn.disabled = True

        def _reveal_preview(dt):
            self._confront_card.opacity = 0
            self._avoid_card.opacity = 0
            self._confront_card._reveal_t = 0.0
            self._avoid_card._reveal_t = 0.0
            if hasattr(self._confront_card, "_stage_upd"):
                self._confront_card._stage_upd()
            if hasattr(self._avoid_card, "_stage_upd"):
                self._avoid_card._stage_upd()
            self._set_stage_available("choice", True)
            Clock.schedule_once(
                lambda _: self._open_encounter_stage("choice"), 0.06)

            def _fade_confront(dt2):
                self._animate_stage_reveal(self._confront_card, duration=0.24)

            def _fade_avoid(dt2):
                def _on_done(*_):
                    Clock.schedule_once(lambda dt: self._sync_shell_height(), 0)
                    self._push_btn.disabled  = False
                    self._avoid_btn.disabled = False
                self._animate_stage_reveal(self._avoid_card, duration=0.24)
                Clock.schedule_once(lambda dt: _on_done(), 0.24)

            Clock.schedule_once(_fade_confront, 0.18)
            Clock.schedule_once(_fade_avoid, 0.30)

        def _san_land(dt):
            self._san_num_lbl.text = str(total)
            base_sz = self._san_num_lbl.font_size
            (Animation(font_size=base_sz * 1.22, duration=0.06, t="out_quad") +
             Animation(font_size=base_sz, duration=0.20, t="out_back")
            ).start(self._san_num_lbl)

            def _colorise(dt2):
                Animation(text_color=T.k(T.PURPLE_LT), duration=0.25,
                          t="out_quad").start(self._san_num_lbl)

            self._san_info_lbl.text = san_roll_info
            Animation(opacity=1, duration=0.18, t="out_quad").start(self._san_info_lbl)
            Clock.schedule_once(lambda dt: self._sync_shell_height(), 0.02)
            Clock.schedule_once(_colorise, 0.22)

        def _start_sanity_roll(dt):
            self._set_stage_available("sanity", True)
            self._open_encounter_stage("sanity")
            # Sweep and spin start together; sweep ends when number turns purple
            # Sweep duration = spin_time + land_delay + colorise_delay + color_anim ≈ 2.04s
            _spin_intervals = [0.022] * 12 + [0.065] * 5 + [0.17] * 4
            _spin_t = sum(_spin_intervals)
            _sweep_dur = _spin_t + 0.30 + 0.22 + 0.25  # land_delay + colorise_delay + color_anim
            self._play_tab_commit(
                "sanity",
                total_duration=_sweep_dur,
                on_complete=lambda: Clock.schedule_once(_reveal_preview, 0.10),
            )
            self._spin_number(self._san_num_lbl, total, _max_val, _san_land)

        Clock.schedule_once(_start_sanity_roll, 0.20)


    def _on_pass(self, *_):
        self._log("Passed -- encounter ends cleanly.")
        self._end_enc()
        self._save()

    # â”€â”€ Event: Confront â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

    def _on_push(self, *_):
        app  = self._app()
        amt  = self._enc.roll_total or 0
        name = self._enc.fear_name
        self._san_result_lbl.text = ""
        self._push_btn.disabled   = True
        self._avoid_btn.disabled  = True
        self._enc_stage_tabs["choice"]._cap_hex = T.BLOOD_LT
        self._refresh_tab_highlights(layout_tabs=False)

        def _apply_confront_consequences():
            self._push_undo()
            _pre_madness_kinds = [m.kind for m in app.state.madnesses]
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
            pct = int(cur / mx * 100) if mx else 0
            _thresh_notif = ""
            _pre_kind_counts = {k: _pre_madness_kinds.count(k) for k in ("short", "long", "indefinite")}
            for _, _tk in threshs:
                if _tk == "zero":
                    continue
                _ins_col = self._kind_color(_tk)
                if _pre_kind_counts.get(_tk, 0) > 0 and _tk != "indefinite":
                    _thresh_notif = f" [color={_ins_col}]â†’ Cured {self._kind_label(_tk)} Insanity[/color]"
                elif _pre_kind_counts.get(_tk, 0) > 0 and _tk == "indefinite":
                    continue
                else:
                    _thresh_notif = f" [color={_ins_col}]â†’ {self._kind_label(_tk)} Insanity[/color]"
            if fear_cured:
                self._log(f"FEAR CURED: {name} Ã¢â‚¬â€ Extreme Desensitization reached, fear removed.")
                app.notify_event(
                    f"Fear conquered: {name}!",
                    "fears", T.STAGE_1,
                    action_cb=lambda n=name: self.open_fear(n)
                )
            else:
                Clock.schedule_once(
                    lambda _, n=name, a=amt, c=cur, p=pct, ts=_thresh_notif: app.notify_event(
                        f"Sanity: [color={T.PURPLE_LT}]{c+a} - {a} = {c} ({p}%)[/color]{ts}",
                        "fears", T.BLOOD,
                        action_cb=lambda nn=n: self.open_fear(nn)
                    ), 0.15)
                Clock.schedule_once(
                    lambda _, r=new_rung, o=cur_rung, n=name: app.notify_event(
                        f"{n} Desensitization: {self._desens_transition_markup(o, r)}",
                        "fears", DESENS_RUNG_COLORS[r],
                        action_cb=lambda rr=r: self.open_desens(rr)
                    ), 0.15)

            app.refresh_all()

            if fear_cured:
                app.fm.remove(name)
                self._selected_fear   = None
                self._sel_fear_widget = None
                self.refresh()
            self._end_enc()
            self._save()

        self._play_tab_commit("choice", on_complete=lambda: Clock.schedule_once(
            lambda _: _apply_confront_consequences(), 0.05))
        return
        self._push_undo()
        _pre_madness_kinds = [m.kind for m in app.state.madnesses]
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
        pct = int(cur / mx * 100) if mx else 0
        _thresh_notif = ""
        _pre_kind_counts = {k: _pre_madness_kinds.count(k) for k in ("short", "long", "indefinite")}
        for _, _tk in threshs:
            if _tk == "zero":
                continue
            _ins_col = self._kind_color(_tk)
            if _pre_kind_counts.get(_tk, 0) > 0 and _tk != "indefinite":
                _thresh_notif = f" [color={_ins_col}]→ Cured {self._kind_label(_tk)} Insanity[/color]"
            elif _pre_kind_counts.get(_tk, 0) > 0 and _tk == "indefinite":
                continue
            else:
                _thresh_notif = f" [color={_ins_col}]→ {self._kind_label(_tk)} Insanity[/color]"
        if fear_cured:
            self._log(f"FEAR CURED: {name} â€” Extreme Desensitization reached, fear removed.")
            app.notify_event(
                f"Fear conquered: {name}!",
                "fears", T.STAGE_1,
                action_cb=lambda n=name: self.open_fear(n)
            )
        else:
            # Sanity loss + desensitization change â€” batched into one card
            Clock.schedule_once(
                lambda _, n=name, a=amt, c=cur, p=pct, ts=_thresh_notif: app.notify_event(
                    f"Sanity: [color={T.PURPLE_LT}]{c+a} - {a} = {c} ({p}%)[/color]{ts}",
                    "fears", T.BLOOD,
                    action_cb=lambda nn=n: self.open_fear(nn)
                ), 0.15)
            Clock.schedule_once(
                lambda _, r=new_rung, o=cur_rung, n=name: app.notify_event(
                    f"{n} Desensitization: {self._desens_transition_markup(o, r)}",
                    "fears", DESENS_RUNG_COLORS[r],
                    action_cb=lambda rr=r: self.open_desens(rr)
                ), 0.15)

        self._san_result_lbl.text = ""
        self._push_btn.disabled   = True
        self._avoid_btn.disabled  = True
        self._enc_stage_tabs["choice"]._cap_hex = T.BLOOD_LT
        self._refresh_tab_highlights(layout_tabs=False)

        app.refresh_all()

        if fear_cured:
            app.fm.remove(name)
            self._selected_fear   = None
            self._sel_fear_widget = None
            self._play_tab_commit("choice", on_complete=lambda: Clock.schedule_once(
                lambda _: (self.refresh(), self._end_enc()), 0.05))
        else:
            self._play_tab_commit("choice", on_complete=lambda: Clock.schedule_once(
                lambda _: self._end_enc(), 0.05))
        self._save()

    # â”€â”€ Event: Avoid â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

    def _on_avoid(self, *_):
        app   = self._app()
        amt   = self._enc.roll_total or 0
        name  = self._enc.fear_name
        stage = self._enc.fear_stage or 1
        self._san_result_lbl.text = ""
        self._push_btn.disabled   = True
        self._avoid_btn.disabled  = True
        self._enc_stage_tabs["choice"]._cap_hex = T.GREEN
        self._refresh_tab_highlights(layout_tabs=False)

        def _apply_avoid_consequences():
            self._push_undo()
            _pre_madness_kinds = [m.kind for m in app.state.madnesses]
            cleared   = app.state.apply_recovery(amt)
            new_stage = app.fm.increment_stage(name)
            old_rung  = app.fm.get_desens(name)
            new_rung  = app.fm.decr_desens(name)
            self._log(
                f"Avoided Ã¢â‚¬â€ recovered {amt} sanity  |  "
                f"{name}: Severity {stage}>{new_stage}  |  "
                f"Desensitization > {DESENS_NAMES[new_rung]}")

            if stage == 4:
                new_fear = app.fm.add_random()
                if new_fear:
                    self._log(f"Extreme Avoid Ã¢â‚¬â€ panic: new fear added: {new_fear}")
                    app.notify_event(f"Panic! New fear: {new_fear}", "fears", T.STAGE_4,
                                     action_cb=lambda f=new_fear: self.open_fear(f))

            self._update_desens_visuals()
            self._autofill_dc()

            cur = app.state.current_sanity
            mx  = app.state.max_sanity
            pct = int(cur / mx * 100) if mx else 0
            _avoid_thresh_notif = ""
            _pre_kind_counts = {k: _pre_madness_kinds.count(k) for k in ("short", "long", "indefinite")}
            for _, _c, _kind in cleared:
                if _kind == "zero":
                    continue
                _ins_col = self._kind_color(_kind)
                if _pre_kind_counts.get(_kind, 0) > 0 and _kind != "indefinite":
                    _avoid_thresh_notif = f" [color={_ins_col}]â†’ Cured {self._kind_label(_kind)} Insanity[/color]"
                elif _pre_kind_counts.get(_kind, 0) > 0 and _kind == "indefinite":
                    continue

            _delay = 0.5 if stage == 4 else 0.15
            Clock.schedule_once(
                lambda _, n=name, a=amt, c=cur, m=mx, p=pct, ts=_avoid_thresh_notif: app.notify_event(
                    f"Sanity: [color={T.PURPLE_LT}]{c-a} + {a} = {c} ({p}%)[/color]{ts}",
                    "fears", T.STAGE_1,
                    action_cb=lambda nn=n: self.open_fear(nn)
                ), _delay)
            Clock.schedule_once(
                lambda _, s=new_stage, os=stage, n=name: app.notify_event(
                    f"{n} Severity: {self._severity_transition_markup(os, s)}",
                    "fears", FEAR_STAGES[s].color,
                    action_cb=lambda ss=s: self.open_severity(ss)
                ), _delay)
            Clock.schedule_once(
                lambda _, r=new_rung, o=old_rung, n=name: app.notify_event(
                    f"{n} Desensitization: {self._desens_transition_markup(o, r)}",
                    "fears", DESENS_RUNG_COLORS[r],
                    action_cb=lambda rr=r: self.open_desens(rr)
                ), _delay)

            if cleared:
                self._handle_recovery_thresholds(cleared)

            app.refresh_all()
            self.refresh()
            self._end_enc()
            self._save()

        self._play_tab_commit("choice", on_complete=lambda: Clock.schedule_once(
            lambda _: _apply_avoid_consequences(), 0.05))
        return
        self._push_undo()
        _pre_madness_kinds = [m.kind for m in app.state.madnesses]
        cleared   = app.state.apply_recovery(amt)
        new_stage = app.fm.increment_stage(name)
        old_rung  = app.fm.get_desens(name)
        new_rung  = app.fm.decr_desens(name)
        self._log(
            f"Avoided â€” recovered {amt} sanity  |  "
            f"{name}: Severity {stage}>{new_stage}  |  "
            f"Desensitization > {DESENS_NAMES[new_rung]}")

        # Extreme Severity Avoid â†’ add random new fear
        if stage == 4:
            new_fear = app.fm.add_random()
            if new_fear:
                self._log(f"Extreme Avoid â€” panic: new fear added: {new_fear}")
                app.notify_event(f"Panic! New fear: {new_fear}", "fears", T.STAGE_4,
                                 action_cb=lambda f=new_fear: self.open_fear(f))

        self._update_desens_visuals()
        self._autofill_dc()

        cur = app.state.current_sanity
        mx  = app.state.max_sanity
        pct = int(cur / mx * 100) if mx else 0
        _avoid_thresh_notif = ""
        _pre_kind_counts = {k: _pre_madness_kinds.count(k) for k in ("short", "long", "indefinite")}
        for _, _c, _kind in cleared:
            if _kind == "zero":
                continue
            _ins_col = self._kind_color(_kind)
            if _pre_kind_counts.get(_kind, 0) > 0 and _kind != "indefinite":
                _avoid_thresh_notif = f" [color={_ins_col}]→ Cured {self._kind_label(_kind)} Insanity[/color]"
            elif _pre_kind_counts.get(_kind, 0) > 0 and _kind == "indefinite":
                continue

        # Sanity gain + severity increase + desensitization decrease â€” batched into one card
        _delay = 0.5 if stage == 4 else 0.15
        Clock.schedule_once(
            lambda _, n=name, a=amt, c=cur, m=mx, p=pct, ts=_avoid_thresh_notif: app.notify_event(
                f"Sanity: [color={T.PURPLE_LT}]{c-a} + {a} = {c} ({p}%)[/color]{ts}",
                "fears", T.STAGE_1,
                action_cb=lambda nn=n: self.open_fear(nn)
            ), _delay)
        Clock.schedule_once(
            lambda _, s=new_stage, os=stage, n=name: app.notify_event(
                f"{n} Severity: {self._severity_transition_markup(os, s)}",
                "fears", FEAR_STAGES[s].color,
                action_cb=lambda ss=s: self.open_severity(ss)
            ), _delay)
        Clock.schedule_once(
            lambda _, r=new_rung, o=old_rung, n=name: app.notify_event(
                f"{n} Desensitization: {self._desens_transition_markup(o, r)}",
                "fears", DESENS_RUNG_COLORS[r],
                action_cb=lambda rr=r: self.open_desens(rr)
            ), _delay)

        self._san_result_lbl.text = ""
        self._push_btn.disabled   = True
        self._avoid_btn.disabled  = True
        self._enc_stage_tabs["choice"]._cap_hex = T.GREEN
        self._refresh_tab_highlights(layout_tabs=False)

        if cleared:
            self._handle_recovery_thresholds(cleared)

        app.refresh_all()
        self.refresh()
        self._play_tab_commit("choice", on_complete=lambda: Clock.schedule_once(
            lambda _: self._end_enc(), 0.05))
        self._save()

    # â”€â”€ Threshold handling â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

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
            if existing and kind != "indefinite":
                cured = existing[0]
                app.state.madnesses.remove(cured)
                cured_name = cured.name if cured.name else cured.kind_label
                self._log(f"THRESHOLD re-crossed: {label} - cured {cured_name}")
                events.append((color, None, cured_name, label))
            elif existing and kind == "indefinite":
                self._log(f"THRESHOLD re-crossed: {label}")
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
                            f"{e.kind_label} Insanity: [color={c}]{e.name}[/color]", "sanity", c,
                            action_cb=lambda ee=e: sanity_tab.open_madness(ee)
                        ), 0.15)

    def _handle_recovery_thresholds(self, cleared):
        """Sanity recovered upward past a threshold â€” remove the matching madness."""
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
            if existing and kind != "indefinite":
                cured = existing[0]
                app.state.madnesses.remove(cured)
                cured_name = cured.name if cured.name else cured.kind_label
                self._log(f"THRESHOLD CLEARED (avoid): {label} â€” {cured_name} cured")
                events.append((color, cured_name))
            elif existing and kind == "indefinite":
                self._log(f"THRESHOLD CLEARED (avoid): {label}")
            else:
                self._log(f"THRESHOLD CLEARED (avoid): {label} â€” no matching insanity to cure")
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
        """Navigate to the fear effects page and flash the severity card."""
        self._go_page(1)
        card = self._sev_items.get(stage)
        if card:
            Clock.schedule_once(lambda _: card.flash(), 0.2)

    def open_desens(self, rung: int):
        """Navigate to the fear effects page and flash the desensitization card."""
        self._go_page(1)
        card = self._desens_items.get(rung)
        if card:
            Clock.schedule_once(lambda _: card.flash(), 0.2)

    def cancel_encounter(self):
        if self._enc.active:
            self._log("Encounter cancelled.")
            self._end_enc()


