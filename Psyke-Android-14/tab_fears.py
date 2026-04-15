"""
Tab 1: Fears & Fear Encounter  (V2 — redesigned layout)

Two-page swipeable layout:
  Page 0 — Main:   Encounter card, Add Fear, Fear List, Rules
  Page 1 — Detail: Fear Severity, Fear Desensitization

Swipe left/right to move between pages.
"""
from __future__ import annotations

from datetime import datetime
from kivy.animation import Animation
from kivy.app import App
from kivy.clock import Clock
from kivy.graphics import (
    Color, Line, Rectangle, RoundedRectangle,
    StencilPop, StencilPush, StencilUnUse, StencilUse,
)
try:
    from kivy.core.text import CoreLabel as _CoreLabel
except ImportError:
    from kivy.core.text import Label as _CoreLabel
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
    populate_rules_section, ExpandingEffectCard, FillSwipeTitle,
)
import theme as T


class _EncTab(ButtonBehavior, MDBoxLayout):
    """A stage tab on the encounter rail.

    Visual states
    -------------
    active   — stage currently being viewed  (dark-gold fill, bright text)
    done_new — the tab immediately before the active one  (solid gold, dark text)
    done_old — all earlier completed tabs  (muted dark-gold, dim text)
    """

    # Shared layout constants (used by FearsTab layout helpers too)
    _TAB_H   = dp(34)
    _TAB_W   = dp(82)
    _TAB_GAP = dp(6)    # vertical gap between consecutive tabs
    _TOP_PAD = dp(8)    # padding from dock top to the first tab
    _RAIL_W  = dp(6)    # the EncounterListItem accent bar acts as the rail
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
        kwargs.setdefault("width", self._TAB_W)
        kwargs.setdefault("opacity", 0)
        kwargs.setdefault("padding", [self._RAIL_W + dp(6), 0, dp(8), 0])
        super().__init__(**kwargs)
        self._tab_key    = key
        self._on_tap_cb  = on_tap
        self._shown      = False
        self._tab_state  = None   # None | "active" | "done_new" | "done_old"
        self._dim_pending  = False  # True while tab is live but sweep not yet fired
        self._commit_done  = False  # True once sweep completed â†' locked to gold
        self._commit_evt   = None
        self._commit_prog  = 0.0
        self._commit_rail_bottom = 0.0
        self._commit_cb    = None
        self._commit_trace_dur = None
        self._commit_top_phase_dur = None
        self._cap_hex        = None
        self._side_live      = False
        self._appear_pending = False  # True while waiting for post-retract appear()

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
            self._stroke_col  = Color(*T.k(self._main_hex, 0))
            self._stroke_top_rect = Rectangle()
            self._stroke_bottom_rect = Rectangle()

        self.bind(pos=self._upd_canvas, size=self._upd_canvas)

        # Canvas-based label: fixed-size text anchored to the tab's right edge.
        # As the tab grows rightward, the rightmost characters appear first
        # ("ITY" of "SEVERITY") with the beginning revealed as more space opens.
        self._lbl_text = label
        self._lbl_tex = None      # CoreLabel texture (white, tinted by Color instr)
        self._lbl_tex_w = 0
        self._lbl_tex_h = 0
        with self.canvas:
            self._text_col_instr = Color(*T.k(self._main_hex))
            self._text_rect = Rectangle()
        self._rebuild_label_tex()

    # â"€â"€ canvas sync â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€

    def _upd_canvas(self, *_):
        body_x = self.x + self._RAIL_W
        body_w = max(0, self.width - self._RAIL_W)
        self._fill_rect.pos    = (body_x, self.y)
        self._fill_rect.size   = (body_w, self.height)
        self._accent_rect.pos  = (body_x, self.y)
        self._accent_rect.size = (0, self.height)
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
        self._upd_text_canvas()

    def _rebuild_label_tex(self):
        """Build a white CoreLabel texture for the tab label text."""
        cl = _CoreLabel(
            text=self._lbl_text, bold=True,
            font_size=dp(11),
            color=(1, 1, 1, 1),
        )
        cl.refresh()
        tex = cl.texture
        self._lbl_tex   = tex
        self._lbl_tex_w = tex.width  if tex else 0
        self._lbl_tex_h = tex.height if tex else 0
        self._upd_text_canvas()

    def _upd_text_canvas(self):
        """Draw the rightmost visible portion of the label texture.

        The text's right edge is anchored to (self.right - right_pad).
        As the tab grows rightward, characters are revealed from the right
        end of the word first — "ITY" of "SEVERITY" appears before "SEV".
        """
        _RIGHT_PAD = dp(8)
        _LEFT_PAD  = self._RAIL_W + dp(6)   # = dp(12) total left inset
        tex = self._lbl_tex
        if not tex or not self._lbl_tex_w:
            self._text_rect.size = (0, 0)
            return
        # How many pixels of text area are currently exposed (right of the rail)
        clip_w = max(0.0, self.width - _LEFT_PAD - _RIGHT_PAD)
        draw_w = min(clip_w, float(self._lbl_tex_w))
        if draw_w <= 0:
            self._text_rect.size = (0, 0)
            return
        right_anchor = self.right - _RIGHT_PAD
        text_y = self.y + (self.height - self._lbl_tex_h) / 2
        draw_x = right_anchor - draw_w
        # UV: show the rightmost draw_w pixels of the texture
        u0 = (self._lbl_tex_w - draw_w) / max(1, self._lbl_tex_w)
        self._text_rect.texture    = tex
        self._text_rect.tex_coords = (u0, 1, 1, 1, 1, 0, u0, 0)
        self._text_rect.pos  = (draw_x, text_y)
        self._text_rect.size = (draw_w, self._lbl_tex_h)

    # ── Overridable main colour (subclasses swap GOLD → their accent) ──────────

    @property
    def _main_hex(self):    return T.GOLD
    @property
    def _main_dk_hex(self): return T.GOLD_DK
    @property
    def _main_lt_hex(self): return T.GOLD_LT

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

    # â"€â"€ interaction â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€

    def on_release(self):
        if self.opacity > 0 and self._shown:
            self._on_tap_cb(self._tab_key)

    # â"€â"€ state â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€

    def set_state(self, state: str):
        """Apply a visual state: 'active', 'current', 'done_new', or 'done_old'."""
        self._tab_state = state
        m  = self._main_hex
        md = self._main_dk_hex
        ml = self._main_lt_hex
        # Sweep completed â†' locked to solid main colour + stage-coloured side tab
        if self._commit_done:
            if state == "active":
                self._fill_col.rgba   = (*T.k(md)[:3], 0.92)
                self._accent_col.rgba = T.k(ml)
                self._text_col_instr.rgba = T.k(T.TEXT_BRIGHT)
            elif state == "current":
                self._fill_col.rgba   = (*T.k(m)[:3], 0.18)
                self._accent_col.rgba = (*T.k(m)[:3], 0.28)
                self._text_col_instr.rgba = (*T.k(ml)[:3], 0.70)
            elif state == "done_new":
                self._fill_col.rgba   = T.k(m)
                self._accent_col.rgba = T.k(ml)
                self._text_col_instr.rgba = T.k(T.TEXT_DARK)
            else:
                self._fill_col.rgba   = T.k(md)
                self._accent_col.rgba = T.k(md)
                self._text_col_instr.rgba = T.k(T.TEXT_DIM)
            self._side_divider_col.rgba = T.k(T.BG_CARD)
            self._side_col.rgba   = T.k(self._side_hex(), 1.0)
            self._upd_canvas()
            return
        # Animation pending or running â†' don't interfere with side-line state
        if self._dim_pending or self._commit_evt:
            return
        if state == "active":
            self._fill_col.rgba   = (*T.k(md)[:3], 0.92)
            self._accent_col.rgba = T.k(ml)
            self._text_col_instr.rgba = T.k(T.TEXT_BRIGHT)
        elif state == "current":
            self._fill_col.rgba   = (*T.k(m)[:3], 0.18)
            self._accent_col.rgba = (*T.k(m)[:3], 0.28)
            self._text_col_instr.rgba = (*T.k(ml)[:3], 0.70)
        elif state == "done_new":
            self._fill_col.rgba   = T.k(m)
            self._accent_col.rgba = T.k(ml)
            self._text_col_instr.rgba = T.k(T.TEXT_DARK)
        elif state == "done_old":
            self._fill_col.rgba   = T.k(md)
            self._accent_col.rgba = T.k(md)
            self._text_col_instr.rgba = T.k(T.TEXT_DIM)

    # â"€â"€ appear animation â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€

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

        # Dim main colour immediately — set_state() is now blocked
        self._fill_col.rgba   = (*T.k(self._main_hex)[:3], 0.18)
        self._accent_col.rgba = (*T.k(self._main_hex)[:3], 0.28)
        self._text_col_instr.rgba = (*T.k(self._main_hex)[:3], 0.70)
        self._apply_cap_state(0.0)

        if rail_x is not None:
            self.x      = rail_x
            self.y      = target_y
            self.width  = dp(6)
            self.height = target_h
            self.opacity = 1
            Animation(x=target_x, width=target_w, duration=0.32, t="out_cubic").start(self)
            return

        self.opacity = 0
        if start_y is not None:
            self.y = start_y
        Animation(opacity=1, y=target_y, duration=0.24, t="out_cubic").start(self)

    def play_commit_anim(
        self,
        rail_bottom: float,
        total_duration: float = 0.84,
        on_complete=None,
        trace_duration: float | None = None,
        top_phase_duration: float | None = None,
    ):
        """Stroke sweeps around tab timed to total_duration, then tab snaps to main colour."""
        self._dim_pending = False
        if self._commit_evt:
            self._commit_evt.cancel()
            self._commit_evt = None
        total_dur = max(0.3, total_duration)
        trace_dur = None if trace_duration is None else max(0.001, trace_duration)
        if trace_dur is not None:
            total_dur = max(total_dur, trace_dur)
        self._commit_done         = False
        self._commit_prog         = 0.0
        self._commit_total_dur    = total_dur
        self._commit_trace_dur    = trace_dur
        if top_phase_duration is None:
            self._commit_top_phase_dur = None
        else:
            top_limit = trace_dur if trace_dur is not None else total_dur * 0.65
            self._commit_top_phase_dur = max(0.0, min(top_phase_duration, top_limit))
        self._commit_rail_bottom  = rail_bottom
        self._commit_cb           = on_complete
        self._fill_col.rgba       = (*T.k(self._main_hex)[:3], 0.18)
        self._accent_col.rgba     = (*T.k(self._main_hex)[:3], 0.28)
        self._text_col_instr.rgba = (*T.k(self._main_hex)[:3], 0.70)
        self._apply_cap_state(0.0)
        self._stroke_col.rgba     = (*T.k(self._main_hex)[:3], 1.0)
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
        trace_end  = min(total, self._commit_trace_dur if self._commit_trace_dur is not None else total * 0.65)
        hold_end   = max(trace_end, total * 0.75)

        self._commit_prog += dt

        # â"€â"€ Geometry â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€
        lx       = self.x + self._RAIL_W
        clean_rx = self.right
        by       = self.y
        ty       = self.top
        self._hide_side_art()
        self._clear_stroke_art()

        # Phase lengths:
        #  top    — gold stroke sweeps lx â†' clean_rx (corner belongs to the side-tab colour)
        #  right  — the side tab grows down while owning the corner/overhang
        #  bottom — the bottom border returns from clean_rx back to the rail
        top_len    = max(dp(1), clean_rx - lx)
        right_len  = max(dp(1), ty - by)
        bottom_len = max(dp(1), clean_rx - lx)
        total_path = top_len + right_len + bottom_len

        stage_hex = self._side_hex()

        # â"€â"€ Finish â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€
        if self._commit_prog >= total:
            # Stroke gone; lock in the finished side tab.
            self._clear_stroke_art()
            self._stroke_col.a       = 0
            # Tab snaps to solid main colour
            self._fill_col.rgba      = T.k(self._main_hex)
            self._accent_col.rgba    = T.k(self._main_lt_hex)
            self._text_col_instr.rgba = T.k(T.TEXT_DARK)
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

        # â"€â"€ Path progress â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€
        top_phase_dur = self._commit_top_phase_dur
        if (
            top_phase_dur is not None
            and 0 < top_phase_dur < trace_end
            and total_path > top_len
        ):
            if self._commit_prog <= top_phase_dur:
                distance = top_len * min(self._commit_prog / top_phase_dur, 1.0)
            else:
                rem_trace = max(0.001, trace_end - top_phase_dur)
                rem_prog = min((self._commit_prog - top_phase_dur) / rem_trace, 1.0)
                distance = top_len + rem_prog * (total_path - top_len)
        else:
            draw_prog = min(self._commit_prog / trace_end, 1.0) if trace_end > 0 else 1.0
            distance  = draw_prog * total_path

        # â"€â"€ Gold stroke alpha (fades out in the final stretch) â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€
        if self._commit_prog >= hold_end and total > hold_end:
            stroke_alpha = max(0.0, 1.0 - (self._commit_prog - hold_end) / (total - hold_end))
        else:
            stroke_alpha = 1.0
        self._stroke_col.rgba = (*T.k(self._main_hex)[:3], stroke_alpha)

        # â"€â"€ Phase 1: top wrap sweeps from the rail to the overshoot corner â"€â"€â"€
        if distance <= top_len:
            self._stroke_top_rect.pos = (lx, ty - self._SIDE_W)
            self._stroke_top_rect.size = (distance, self._SIDE_W)
            return

        self._stroke_top_rect.pos = (lx, ty - self._SIDE_W)
        self._stroke_top_rect.size = (top_len, self._SIDE_W)

        rem = distance - top_len

        # â"€â"€ Phase 2: side tab owns the top corner and grows downward â"€â"€â"€â"€â"€â"€â"€â"€â"€
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

        # â"€â"€ Phase 3: bottom border returns to the rail â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€
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


# â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€
# ENCOUNTER LIST ITEM
# Expandable list item that hosts the fear encounter flow.
# Visually identical to ExpandingEffectCard when collapsed; the accent bar
# evolves into the encounter rail when the item is live/expanded.
#
# Modes:
#   "idle"      — collapsed or openable; detail shows DC + ENCOUNTER controls.
#   "live"      — expanded; detail shows the encounter flow shell.
#   "completed" — collapsible summary; detail shows resolved encounter record.
# â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€

from kivy.properties import BooleanProperty as _BProp, NumericProperty as _NProp

class EncounterListItem(MDBoxLayout):
    expand_t   = _NProp(0.0)
    open_state = _BProp(False)
    _CONTENT_RIGHT_INSET = dp(18)
    _MIN_COLLAPSED_H = dp(56)

    def __init__(self, accent_hex: str = T.GOLD, **kwargs):
        kwargs.setdefault("orientation", "vertical")
        kwargs.setdefault("size_hint_y", None)
        kwargs.setdefault("spacing", dp(2))
        # Left padding = 0 so shells/tabs start at the list-item edge and the
        # accent bar becomes the rail.  Right padding keeps breathing room.
        kwargs.setdefault("padding", [0, dp(6), dp(14), dp(6)])
        super().__init__(**kwargs)

        self._accent_hex = accent_hex
        self._mode       = "idle"
        self._flash_evt  = None
        self._live_shell = None   # _enc_flow_shell ref while mode=="live"
        self._on_open_cb = None

        with self.canvas.before:
            Color(*T.k(T.BORDER))
            self._outer        = RoundedRectangle(radius=[dp(10)])
            self._bg_color     = Color(*T.k(T.BG_CARD))
            self._inner        = RoundedRectangle(radius=[dp(9)])
            self._accent_color = Color(*T.k(accent_hex))
            self._bar          = RoundedRectangle(radius=[dp(9), 0, 0, dp(9)])

        # â"€â"€ header (always visible) â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€
        self._header = MDBoxLayout(
            orientation="horizontal",
            size_hint_y=None, adaptive_height=True,
            padding=[dp(14), 0, 0, 0])
        self._text_col = MDBoxLayout(
            orientation="vertical", spacing=0,
            size_hint_y=None, adaptive_height=True)
        self._title_stage = FillSwipeTitle(fill_rgba=list(T.k(accent_hex)))
        self._title_stage.text = "FEAR ENCOUNTER"
        self._subtitle_lbl = MDLabel(
            text="Select a fear to begin",
            markup=True,
            theme_text_color="Custom", text_color=T.k(T.TEXT_DIM),
            font_style="Caption", size_hint_y=None, adaptive_height=True)
        self._text_col.add_widget(self._title_stage)
        self._text_col.add_widget(self._subtitle_lbl)
        self._header.add_widget(self._text_col)
        self.add_widget(self._header)

        # â"€â"€ detail box (content swapped per mode) â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€
        self._detail_box = MDBoxLayout(
            orientation="vertical", spacing=dp(6),
            size_hint_y=None, opacity=0, height=0)
        self.add_widget(self._detail_box)

        self.bind(
            pos=self._redraw, size=self._redraw,
            expand_t=self._redraw, open_state=self._redraw)
        self.height = self._collapsed_height()

    def _collapsed_height(self) -> float:
        header_h = max(dp(32), getattr(self._header, "height", 0))
        return max(
            self._MIN_COLLAPSED_H,
            self.padding[1] + self.padding[3] + header_h + self.spacing + dp(4),
        )

    # â"€â"€ drawing â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€

    def _redraw(self, *_):
        t      = self.expand_t
        radius = dp(10 + 2 * t)

        # Accent bar grows 4 -> 6 dp as the item opens.
        # At full expansion (t=1) the 6dp bar IS the encounter rail --
        # tabs emerge from it; neither live nor frozen shell draws its own bar.
        accent_w = dp(4 + 2 * t)

        self._bg_color.rgba     = T.k(T.BG_HOVER) if self.open_state else T.k(T.BG_CARD)
        self._accent_color.rgba = T.k(self._accent_hex)

        self._outer.pos    = self.pos
        self._outer.size   = self.size
        self._outer.radius = [radius]
        self._inner.pos    = (self.x + 1, self.y + 1)
        self._inner.size   = (max(0, self.width - 2), max(0, self.height - 2))
        self._inner.radius = [max(0, radius - 1)]
        self._bar.pos      = (self.x + 1, self.y + 1)
        self._bar.size     = (accent_w, max(0, self.height - 2))
        self._bar.radius   = [radius, 0, 0, radius]

        # Detail box height / opacity (non-live modes only)
        body_alpha = max(0.0, min(1.0, (t - 0.50) / 0.24))
        self._detail_box.opacity = body_alpha
        if self._mode != "live":
            self._detail_box.height = max(0.0, self.height - self._collapsed_height())

        # Subtitle brightens with expand
        mix    = max(0.0, min(1.0, (t - 0.18) / 0.24))
        dim    = T.k(T.TEXT_DIM)[:3]
        bright = T.k(T.TEXT_BRIGHT)[:3]
        col    = tuple(dim[i] + (bright[i] - dim[i]) * mix for i in range(3))
        self._subtitle_lbl.text_color = (*col, 1.0)
        self._subtitle_lbl.bold       = mix > 0.15
        self._title_stage.fill_t      = max(0.0, min(1.0, (t - 0.12) / 0.46))

    # â"€â"€ open / close â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€

    def set_open(self, open_state: bool, animate: bool = True, on_complete=None):
        Animation.cancel_all(self, "height", "expand_t")
        self.open_state = open_state
        if not animate:
            self.expand_t = 1.0 if open_state else 0.0
            self.height   = self._collapsed_height()
            self._redraw()
            if open_state:
                Clock.schedule_once(self._sync_open_height)
                for child in self._detail_box.children:
                    cb = getattr(child, "_on_parent_open", None)
                    if callable(cb):
                        Clock.schedule_once(lambda dt, _cb=cb: _cb(), 0)
            else:
                for child in self._detail_box.children:
                    cb = getattr(child, "_on_parent_close", None)
                    if callable(cb):
                        Clock.schedule_once(lambda dt, _cb=cb: _cb(), 0)
            if callable(on_complete):
                Clock.schedule_once(lambda dt: on_complete(), 0)
            return
        if open_state:
            Clock.schedule_once(lambda dt: self._do_open_anim(on_complete=on_complete))
        else:
            for child in self._detail_box.children:
                cb = getattr(child, "_on_parent_close", None)
                if callable(cb):
                    Clock.schedule_once(lambda dt, _cb=cb: _cb(), 0)
            anim = Animation(height=self._collapsed_height(), expand_t=0.0,
                             duration=0.28, t="out_cubic")
            if callable(on_complete):
                anim.bind(on_complete=lambda *_: on_complete())
            anim.start(self)

    def _do_open_anim(self, *_, on_complete=None):
        target_h = self._target_open_height()
        if target_h <= self._collapsed_height():
            Clock.schedule_once(lambda dt: self._do_open_anim(on_complete=on_complete))
            return
        anim = Animation(height=target_h, expand_t=1.0,
                         duration=0.28, t="out_cubic")
        if callable(on_complete):
            anim.bind(on_complete=lambda *_: on_complete())
        anim.start(self)
        for child in self._detail_box.children:
            cb = getattr(child, "_on_parent_open", None)
            if callable(cb):
                Clock.schedule_once(lambda dt, _cb=cb: _cb(), 0)

    def _target_open_height(self):
        detail_h = sum(
            max(getattr(w, "height", 0), getattr(w, "minimum_height", 0))
            for w in self._detail_box.children
        )
        detail_h = max(dp(48), detail_h)
        return (
            self.padding[1] + self.padding[3]
            + self._header.height
            + self.spacing
            + detail_h + dp(8)
        )

    def _sync_open_height(self, *_):
        if not self.open_state:
            return
        h = self._target_open_height()
        if h <= self._collapsed_height():
            Clock.schedule_once(self._sync_open_height)
            return
        self.height = h

    def _bind_completed_content(self, widget):
        """Keep completed-entry height synced as deferred shell/layout updates land."""
        if widget is None:
            return

        def _queue_sync(*_):
            if self._mode == "completed" and self.open_state:
                Clock.schedule_once(self._sync_open_height, 0)

        for prop in ("height", "minimum_height", "size", "pos"):
            try:
                widget.bind(**{prop: _queue_sync})
            except Exception:
                pass

        for child in getattr(widget, "children", []):
            for prop in ("height", "minimum_height", "size"):
                try:
                    child.bind(**{prop: _queue_sync})
                except Exception:
                    pass

    def update_live_height(self):
        """Called when the flow shell height changes during a live encounter."""
        if self._mode != "live" or not self._live_shell:
            return
        shell_h = self._live_shell.height
        self._detail_box.height = max(0, shell_h)
        target = (
            self.padding[1] + self.padding[3]
            + self._header.height
            + self.spacing
            + max(dp(4), shell_h) + dp(4)
        )
        target = max(target, self._collapsed_height())
        if abs(target - self.height) > dp(1):
            Animation.cancel_all(self, "height")
            self.height = target

    def _set_detail_content(self, widget):
        """Adopt a detail widget even if it still belongs to a previous item."""
        if widget is None:
            self._detail_box.clear_widgets()
            return
        if widget.parent is not None and widget.parent is not self._detail_box:
            widget.parent.remove_widget(widget)
        self._detail_box.clear_widgets()
        self._detail_box.add_widget(widget)

    # â"€â"€ mode transitions â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€

    def set_idle(self, subtitle: str = "Select a fear to begin"):
        self._mode = "idle"
        self._live_shell = None
        self._title_stage.text   = "FEAR ENCOUNTER"
        self._title_stage.fill_t = 0.0
        self._subtitle_lbl.text  = subtitle

    def start_live(self, fear_name: str, stage: int, flow_shell, subtitle: str = ""):
        """Switch to live mode; flow shell placed in detail section."""
        self._mode       = "live"
        self._live_shell = flow_shell
        self._title_stage.text  = fear_name
        self._subtitle_lbl.text = subtitle
        self._set_detail_content(flow_shell)
        # Open visually immediately; height grows as the shell fills in
        self.open_state            = True
        self._detail_box.opacity   = 1.0
        Animation(expand_t=1.0, duration=0.28, t="out_cubic").start(self)

    def set_completed(self, title: str, subtitle: str, content_widget, on_complete=None):
        """Transition to completed state; content_widget shown when expanded."""
        self._mode       = "completed"
        self._live_shell = None
        self._title_stage.text  = title
        self._subtitle_lbl.text = subtitle
        self._set_detail_content(content_widget)
        self._bind_completed_content(content_widget)
        self.set_open(False, animate=True, on_complete=on_complete)

    def _touch_hits_stage_tab(self, widget, touch) -> bool:
        if hasattr(widget, "_tab_key") and widget.collide_point(*touch.pos):
            return True
        for child in getattr(widget, "children", []):
            if self._touch_hits_stage_tab(child, touch):
                return True
        return False

    # â"€â"€ tap â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€

    def on_touch_down(self, touch):
        if not self.collide_point(*touch.pos):
            return super().on_touch_down(touch)
        if self._mode == "completed":
            if self._header.collide_point(*touch.pos):
                if not self.open_state and self._on_open_cb:
                    if self._on_open_cb(self) is False:
                        return True
                self.set_open(not self.open_state)
                return True
            if self.open_state:
                if self._touch_hits_stage_tab(self._detail_box, touch):
                    return super().on_touch_down(touch)
                self.set_open(False)
                return True
        if self._mode == "idle" and self._header.collide_point(*touch.pos):
            if not self.open_state and self._on_open_cb:
                if self._on_open_cb(self) is False:
                    return True
            self.set_open(not self.open_state)
            return True
        return super().on_touch_down(touch)

    # â"€â"€ flash (same stroke-sweep as ExpandingEffectCard) â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€

    def flash(self):
        if self._flash_evt:
            self._flash_evt.cancel()
            self._flash_evt = None
        self._clear_stroke_overlay()
        self._flash_prog = 0.0
        with self.canvas.after:
            self._stroke_col  = Color(*T.k(self._accent_hex), 1.0)
            self._stroke_line = Line(width=dp(2), cap="none", joint="miter")
        self._flash_evt = Clock.schedule_interval(self._tick_stroke, 1 / 60)

    def wrap_sweep(self):
        if self._flash_evt:
            self._flash_evt.cancel()
            self._flash_evt = None
        self._clear_stroke_overlay()
        self._flash_prog = 0.0
        with self.canvas.after:
            self._stroke_col  = Color(*T.k(self._accent_hex), 1.0)
            self._stroke_line = Line(width=dp(2), cap="none", joint="miter")
        self._flash_evt = Clock.schedule_interval(self._tick_wrap_sweep, 1 / 60)

    def _clear_stroke_overlay(self):
        if hasattr(self, "_stroke_col"):
            try:
                self.canvas.after.remove(self._stroke_col)
                self.canvas.after.remove(self._stroke_line)
            except Exception:
                pass

    def _stroke_path_points(self, distance: float):
        x = self.x + dp(1)
        y = self.y + dp(1)
        w = max(dp(1), self.width - dp(2))
        h = max(dp(1), self.height - dp(2))
        perimeter = 2 * (w + h)
        dist = max(0.0, min(distance, perimeter))
        segs = [
            ((x, y), (x, y + h), h),
            ((x, y + h), (x + w, y + h), w),
            ((x + w, y + h), (x + w, y), h),
            ((x + w, y), (x, y), w),
        ]
        pts = [x, y]
        rem = dist
        for (x0, y0), (x1, y1), seg_len in segs:
            if rem <= 0:
                break
            if rem >= seg_len:
                pts += [x1, y1]
                rem -= seg_len
                continue
            t = rem / max(seg_len, 0.001)
            pts += [x0 + t * (x1 - x0), y0 + t * (y1 - y0)]
            break
        return pts, perimeter

    def _tick_stroke(self, dt):
        SPEED = 2.0;  HOLD = 0.25;  FADE = 0.35
        self._flash_prog += dt
        total = 1.0 / SPEED + HOLD + FADE
        if self._flash_prog >= total:
            self._clear_stroke_overlay()
            self._flash_evt.cancel()
            self._flash_evt = None
            return
        draw_prog  = min(self._flash_prog * SPEED, 1.0)
        fade_start = 1.0 / SPEED + HOLD
        alpha = (max(0.0, 1.0 - (self._flash_prog - fade_start) / FADE)
                 if self._flash_prog >= fade_start else 1.0)
        self._stroke_col.rgba = (*T.k(self._accent_hex)[:3], alpha)
        _, perimeter = self._stroke_path_points(0)
        pts, _ = self._stroke_path_points(draw_prog * perimeter)
        self._stroke_line.points = pts

    def _tick_wrap_sweep(self, dt):
        DURATION = 0.82
        self._flash_prog += dt
        if self._flash_prog >= DURATION:
            pts, _ = self._stroke_path_points(10**9)
            self._stroke_line.points = pts
            self._clear_stroke_overlay()
            self._flash_evt.cancel()
            self._flash_evt = None
            return
        draw_prog = min(1.0, self._flash_prog / DURATION)
        self._stroke_col.rgba = (*T.k(self._accent_hex)[:3], 1.0)
        _, perimeter = self._stroke_path_points(0)
        pts, _ = self._stroke_path_points(draw_prog * perimeter)
        self._stroke_line.points = pts


# â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€
# FEARS TAB
# â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€

class FearsTab(MDBoxLayout):
    _TAB_SETTLE_DELAY = 0.24
    _CHOICE_REVEAL_DELAY = 0.12
    _STAGE_BOX_EXPAND_DELAY = 0.14
    _STAGE_CARD_REVEAL_DURATION = 0.34

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
        self._enc_stage_tabs: dict[str, _EncTab] = {}
        self._enc_active_stage: str | None = None
        self._sev_expanded   = False
        self._des_expanded   = False

        # Encounter list-item state
        self._enc_item: EncounterListItem | None    = None
        self._enc_items_box: MDBoxLayout | None     = None
        self._dc_row: MDBoxLayout | None            = None   # persistent DC controls
        self._current_enc_num: int                  = 0
        self._enc_dc_used: int                      = FEAR_ENC_DC
        self._fear_enc_items: dict                  = {}     # fear name → [completed EncounterListItem, ...]
        self._fear_enc_records: dict                = {}     # fear name → [record dict, ...]  (persisted)
        self._enc_list_fear: str | None             = None   # fear whose items are currently displayed
        self._selected_enc_item                     = None   # currently open completed item

        # Ã¢"â‚¬Ã¢"â‚¬ Page state Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬
        self._page = 0   # 0 = Main, 1 = Severity & Desens

        # Page indicator bar
        self.add_widget(self._build_page_indicator())

        # Ã¢"â‚¬Ã¢"â‚¬ Page 0 (Main) Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬
        self._sv0 = ScrollView(do_scroll_x=False, size_hint=(None, None))
        p0 = MDBoxLayout(
            orientation="vertical",
            padding=dp(10), spacing=dp(8),
            size_hint_y=None, adaptive_height=True)
        p0.add_widget(self._build_encounter_section())
        p0.add_widget(self._build_fear_add_row())
        p0.add_widget(self._build_fear_list())
        p0.add_widget(self._build_rules_panel())
        self._sv0.add_widget(p0)

        # Ã¢"â‚¬Ã¢"â‚¬ Page 1 (Detail) Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬
        self._sv1 = ScrollView(do_scroll_x=False, size_hint=(None, None))
        p1 = MDBoxLayout(
            orientation="vertical",
            padding=dp(10), spacing=dp(8),
            size_hint_y=None, adaptive_height=True)

        # Ã¢"â‚¬Ã¢"â‚¬ Selected fear context banner Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬
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

        self._content_area = FloatLayout()
        self._content_area.bind(
            size=lambda *_: Clock.schedule_once(lambda dt: self._update_sv_positions()),
            pos=lambda *_: Clock.schedule_once(lambda dt: self._update_sv_positions()),
        )
        self._content_area.add_widget(self._sv0)
        self._content_area.add_widget(self._sv1)
        self.add_widget(self._content_area)
        self._update_indicator()

    # Ã¢"â‚¬Ã¢"â‚¬ Page indicator Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬

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

    # Ã¢"â‚¬Ã¢"â‚¬ Swipe detection Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬

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

    # Ã¢"â‚¬Ã¢"â‚¬ Build: Encounter Card Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬

    def _build_encounter_section(self) -> MDBoxLayout:
        """
        Encounter items box: the idle _enc_item at the top, completed encounter
        items accumulating below it — same list-item family as the fear list.
        """
        self._enc_items_box = MDBoxLayout(
            orientation="vertical", adaptive_height=True, spacing=dp(4))

        # DC controls and encounter history live inside the same yellow card.
        enc_card = BorderCard(border_hex=T.GOLD)
        enc_card.add_widget(SectionLabel("FEAR ENCOUNTER", color_hex=T.GOLD))

        # Compact "Selected Fear" banner shown at the top of the encounter card
        self._enc_fear_banner = MDBoxLayout(
            orientation="vertical", spacing=dp(2),
            padding=[dp(10), dp(6), dp(10), dp(6)],
            size_hint_y=None, height=0, opacity=0)
        with self._enc_fear_banner.canvas.before:
            Color(*T.k(T.GOLD, 0.70))
            _efb_bd   = RoundedRectangle(radius=[dp(8)])
            Color(*T.k(T.BG_HOVER))
            _efb_bg   = RoundedRectangle(radius=[dp(7)])
            Color(*T.k(T.GOLD, 0.06))
            _efb_tint = RoundedRectangle(radius=[dp(7)])
        def _upd_efb(w, *_):
            _efb_bd.pos    = w.pos;   _efb_bd.size   = w.size
            _efb_bg.pos    = (w.x+2,  w.y+2)
            _efb_bg.size   = (max(0, w.width-4), max(0, w.height-4))
            _efb_tint.pos  = (w.x+2,  w.y+2)
            _efb_tint.size = (max(0, w.width-4), max(0, w.height-4))
        self._enc_fear_banner.bind(pos=_upd_efb, size=_upd_efb)
        self._enc_fear_banner.add_widget(MDLabel(
            text="Selected Fear:",
            theme_text_color="Custom", text_color=T.k(T.TEXT_DIM),
            font_style="Caption",
            size_hint_y=None, height=dp(14)))
        self._enc_fear_name_lbl = MDLabel(
            text="", markup=True, bold=True,
            theme_text_color="Custom", text_color=T.k(T.TEXT_BRIGHT),
            font_style="Body2",
            size_hint_y=None, height=dp(22))
        self._enc_fear_banner.add_widget(self._enc_fear_name_lbl)
        enc_card.add_widget(self._enc_fear_banner)

        dc_row = MDBoxLayout(spacing=dp(8), size_hint_y=None, height=dp(52))
        dc_row.add_widget(MDLabel(
            text="DC:", size_hint_x=None, width=dp(26),
            theme_text_color="Custom", text_color=T.k(T.TEXT_DIM)))
        self._dc_field = themed_field(
            hint_text="", text=str(FEAR_ENC_DC),
            accent_hex=T.GOLD,
            size_hint_x=1, input_filter="int")
        dc_row.add_widget(self._dc_field)
        self._enc_btn = MDRaisedButton(
            text="ENCOUNTER",
            md_bg_color=T.k(T.BLOOD),
            size_hint_x=None, width=dp(132), size_hint_y=None, height=dp(48),
            disabled=True,
            on_release=self._on_encounter)
        dc_row.add_widget(self._enc_btn)
        enc_card.add_widget(dc_row)
        self._dc_row = dc_row

        # Shell: Widget that reserves height in the card's BoxLayout.
        # Gold rail drawn on canvas; tabs and _enc_content are Widget children
        # positioned at absolute screen coords via _sync_shell_layout.
        # The EncounterListItem's accent bar (6dp gold stripe) IS the rail.
        # The shell draws no separate bar of its own.
        self._enc_flow_shell = Widget(size_hint_y=None, height=0, opacity=0)
        clip_children(self._enc_flow_shell)
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
        self._enc_height_sync_paused = False
        self._enc_content.bind(minimum_height=lambda *_: self._on_enc_content_min_height())
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
            font_style="H5", size_hint_y=None, height=dp(44), opacity=0,
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
                # Stencil clip: restricts both background and child widgets to
                # the currently-revealed width, so text doesn't appear ahead of
                # the card's growing edge.
                StencilPush()
                _clip = Rectangle()
                StencilUse()
                panel._stage_bd_col = Color(*T.k(border_hex, 0.06))
                _bd = RoundedRectangle(radius=[0, dp(12), dp(12), 0])
                panel._stage_bg_col = Color(*T.k(border_hex, 0.018))
                _bg = RoundedRectangle(radius=[0, dp(11), dp(11), 0])
                panel._stage_line_col = Color(*T.k(border_hex))
                _line = Line(width=dp(1.6), cap="none", joint="bevel")
            with panel.canvas.after:
                StencilUnUse()
                StencilPop()

            def _upd_stage_panel(w, *_, _bd=_bd, _bg=_bg, _line=_line, _clip=_clip):
                reveal_t = max(0.0, min(1.0, getattr(w, "_reveal_t", 1.0)))
                vis_w = max(0, w.width * reveal_t)
                _clip.pos  = (w.x, w.y)
                _clip.size = (vis_w, w.height)
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

        # Choice stage container — holds the two standalone option cards
        # without any extra wrapper chrome.
        self._preview_box = MDBoxLayout(
            orientation="vertical",
            spacing=dp(10),
            padding=[0, 0, 0, 0],
            size_hint_x=1,
            size_hint_y=None,
            adaptive_height=True,
        )
        self._preview_box._min_stage_height = dp(188)

        # Ã¢"â‚¬Ã¢"â‚¬ Card + metric-row factory helpers Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬
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
                StencilPush()
                _clip = Rectangle()
                StencilUse()
                # Tinted fill — subtle shade of the card colour
                box._stage_bd_col = Color(*T.k(border_hex, 0.06))
                _bd = RoundedRectangle(radius=[0, dp(12), dp(12), 0])
                box._stage_bg_col = Color(*T.k(border_hex, 0.018))
                _bg = RoundedRectangle(radius=[0, dp(11), dp(11), 0])
                # 3-sided border: top Ã¢â€ â€™ right Ã¢â€ â€™ bottom  (left side open)
                box._stage_line_col = Color(*T.k(border_hex))
                _line = Line(width=dp(1.6))
            with box.canvas.after:
                StencilUnUse()
                StencilPop()
            def _upd(w, *_, _bd=_bd, _bg=_bg, _line=_line, _clip=_clip):
                reveal_t = max(0.0, min(1.0, getattr(w, "_reveal_t", 1.0)))
                vis_w = max(0, w.width * reveal_t)
                _clip.pos  = (w.x, w.y)
                _clip.size = (vis_w, w.height)
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

        # Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬ CONFRONT card Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬
        self._confront_card = _mk_outer_card(T.BLOOD_LT)

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

        # Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬ AVOID card Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬
        self._avoid_card = _mk_outer_card(T.STAGE_1)

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

        # Hope row — centred, hidden until a fail result with active hope
        self._hope_row = MDBoxLayout(
            size_hint_y=None, height=0, opacity=0,
            padding=[0, dp(4), 0, dp(4)])
        self._hope_btn = HopeButton(on_use=self._use_hope)
        self._hope_row.add_widget(self._hope_btn)
        self._hope_row.add_widget(Widget())
        self._save_stage_box.add_widget(self._hope_row)

        # Notify the current _enc_item whenever the shell height changes
        def _on_shell_height(shell, h):
            if self._enc_item and self._enc_item._mode == "live":
                self._enc_item.update_live_height()
        self._enc_flow_shell.bind(height=_on_shell_height)

        self._enc_item = None  # created on demand when encounter starts

        enc_card.add_widget(Divider(color_hex=T.GOLD_DK))

        self._enc_header_row = MDBoxLayout(
            size_hint_y=None, height=0, spacing=dp(8), opacity=0)
        self._enc_section_lbl = SectionLabel("", color_hex=T.GOLD, size_hint_y=1)
        self._enc_header_row.add_widget(self._enc_section_lbl)
        self._enc_header_row.add_widget(Widget())
        self._enc_delete_btn = MDIconButton(
            icon="trash-can-outline",
            theme_icon_color="Custom", icon_color=T.k(T.RED),
            size_hint_x=None, width=dp(40),
            disabled=True,
            on_release=self._on_delete_selected_encounter)
        self._enc_header_row.add_widget(self._enc_delete_btn)
        enc_card.add_widget(self._enc_header_row)
        enc_card.add_widget(self._enc_items_box)

        section = MDBoxLayout(
            orientation="vertical", adaptive_height=True, spacing=dp(8))
        section.add_widget(enc_card)
        return section

    # Ã¢"â‚¬Ã¢"â‚¬ Build: Fear Add Row Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬

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

    # Ã¢"â‚¬Ã¢"â‚¬ Build: Fear List Card Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬

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
        rm_btn_wrap = FloatLayout(size_hint_x=None, width=dp(40), size_hint_y=None, height=dp(32))
        rm_btn.pos_hint = {"center_x": 0.5, "center_y": 0.43}
        rm_btn_wrap.add_widget(rm_btn)
        hdr.add_widget(rm_btn_wrap)
        card.add_widget(hdr)

        self._fear_list_box = MDBoxLayout(
            orientation="vertical", adaptive_height=True, spacing=dp(2))
        card.add_widget(self._fear_list_box)
        return card

    # Ã¢"â‚¬Ã¢"â‚¬ Build: Severity Section (accordion) Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬

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

    # Ã¢"â‚¬Ã¢"â‚¬ Build: Fear Desensitization Section (accordion) Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬

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

    # Ã¢"â‚¬Ã¢"â‚¬ Build: Rules Panel Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬

    def _build_rules_panel(self) -> BorderCard:
        wrapper = BorderCard(border_hex=T.GOLD)
        sec = ExpandableSection(
            "FEAR RULES",
            accent_hex=T.GOLD,
        )
        populate_rules_section(sec, FEAR_RULES_TEXT, T.GOLD)
        wrapper.add_widget(sec)
        return wrapper

    # Ã¢"â‚¬Ã¢"â‚¬ Internal helpers Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬

    def _app(self): return App.get_running_app()

    def _push_undo(self):
        app = self._app()
        app.undo_stack.push(app.state, app.fm)

    def _save(self):
        app = self._app()
        app.save_manager.save(app.state, app.fm, app.char_name, app.enc_history,
                              fear_enc_records=self._fear_enc_records)

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
        content_w = max(0, s.width - EncounterListItem._CONTENT_RIGHT_INSET)
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
        self._enc_content.x = s.x + dp(1)
        self._enc_content.width = content_w
        self._enc_content.height = content_h
        if active_idx >= 0:
            tabs_above = _EncTab._TOP_PAD + active_idx * (_EncTab._TAB_H + _EncTab._TAB_GAP) + _EncTab._TAB_H
            self._enc_content.y = s.y + shell_h - tabs_above - content_gap - content_h
        else:
            self._enc_content.y = s.y
        self._layout_stage_tabs(animated=False)

    def _on_enc_content_min_height(self):
        if self._enc_height_sync_paused:
            return
        self._sync_shell_height()

    def _sync_shell_height(self, *_, animate_tabs: bool = False):
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
        self._layout_stage_tabs(animated=animate_tabs)

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
                if tab._appear_pending:
                    tab._appear_pending = False
                    tab.x = tx
                    tab.y = ty
                    tab.appear(rail_x=s.x)
                else:
                    Animation.cancel_all(tab, "x", "y")
                    Animation(x=tx, y=ty, duration=0.22, t="in_out_cubic").start(tab)
            else:
                tab.x = tx
                tab.y = ty

    def _set_stage_available(self, key: str, available: bool = True,
                             refresh_highlights: bool = True):
        tab = self._enc_stage_tabs[key]
        if available and not tab._shown:
            tab._shown          = True
            tab._appear_pending = True
            tab.x      = self._enc_flow_shell.x
            tab.y      = self._tab_stack_y(len(self._stage_history_keys()) - 1)
            tab.width  = _EncTab._TAB_W
            tab.height = _EncTab._TAB_H
            tab.opacity = 0
            if refresh_highlights:
                self._refresh_tab_highlights(layout_tabs=False)
            return
        if not available:
            Animation.cancel_all(tab)
            if tab._commit_evt:
                tab._commit_evt.cancel()
                tab._commit_evt = None
            tab.opacity          = 0
            tab._shown           = False
            tab._appear_pending  = False
            tab._tab_state       = None
            tab._dim_pending     = False
            tab._commit_done     = False
            tab._side_live       = False
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
        current = None
        if latest and not self._enc_stage_tabs[latest]._commit_done:
            current = latest
        for key in history:
            tab = self._enc_stage_tabs[key]
            if key == current:
                tab.set_state("current")
                tab.opacity = 1.0
            elif key == active:
                tab.set_state("active")
                tab.opacity = 1.0
            else:
                tab.set_state("done_new")
                tab.opacity = 1.0
        if layout_tabs:
            self._layout_stage_tabs(animated=animated)

    def _play_tab_commit(
        self,
        key: str,
        total_duration: float = 0.84,
        on_complete=None,
        trace_duration: float | None = None,
        top_phase_duration: float | None = None,
    ):
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
            trace_duration=trace_duration,
            top_phase_duration=top_phase_duration,
        )

    def _animate_stage_reveal(self, panel, duration: float | None = None):
        duration = self._STAGE_CARD_REVEAL_DURATION if duration is None else duration
        if getattr(panel, "_reveal_evt", None):
            panel._reveal_evt.cancel()
            panel._reveal_evt = None
        panel._reveal_t = 0.0
        panel.opacity = 1.0
        if hasattr(panel, "_stage_upd"):
            panel._stage_upd()

        start_t = Clock.get_boottime()

        def _tick(dt):
            prog = min(1.0, (Clock.get_boottime() - start_t) / max(0.001, duration))
            eased = 1.0 - pow(1.0 - prog, 3)
            panel._reveal_t = eased
            panel.opacity = 1.0
            if hasattr(panel, "_stage_upd"):
                panel._stage_upd()
            if prog >= 1.0:
                panel.opacity = 1.0
                panel._reveal_evt = None
                return False
            return True

        panel._reveal_evt = Clock.schedule_interval(_tick, 1 / 60)

    def _animate_stage_retract(self, panel, duration: float = 0.26, on_complete=None):
        """Retract a stage panel back into the rail — exact reverse of _animate_stage_reveal.

        _reveal_t goes from its current value → 0 with in_cubic easing (slow start,
        fast finish) so the card accelerates back into the rail, mirroring the
        out_cubic ease-out it used when emerging.
        """
        if getattr(panel, "_reveal_evt", None):
            panel._reveal_evt.cancel()
            panel._reveal_evt = None

        start_t        = Clock.get_boottime()
        start_reveal_t = max(0.0, min(1.0, getattr(panel, "_reveal_t", 1.0)))

        def _tick(dt):
            prog  = min(1.0, (Clock.get_boottime() - start_t) / max(0.001, duration))
            # in_cubic: starts slow, accelerates — mirrors the out_cubic emerge
            eased = pow(prog, 3)
            panel._reveal_t = start_reveal_t * (1.0 - eased)
            panel.opacity   = 1.0
            if hasattr(panel, "_stage_upd"):
                panel._stage_upd()
            if prog >= 1.0:
                panel._reveal_t = 0.0
                panel.opacity   = 1.0
                if hasattr(panel, "_stage_upd"):
                    panel._stage_upd()
                panel._reveal_evt = None
                if on_complete:
                    on_complete()
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

        if not animate:
            for k, child in panels.items():
                if k != key and child.parent is self._enc_content:
                    self._enc_content.remove_widget(child)
            if target.parent is not self._enc_content:
                target._reveal_t = 1.0
                target.opacity = 1
                if hasattr(target, "_stage_upd"):
                    target._stage_upd()
                self._enc_content.add_widget(target)
            self._enc_active_stage = key
            self._refresh_tab_highlights()
            Clock.schedule_once(lambda dt: self._sync_shell_height(), 0)
            return

        # Animated path: fade out old panel, crossfade to new, animate tabs into position
        old_panel = next(
            (child for k, child in panels.items()
             if k != key and child.parent is self._enc_content),
            None
        )

        def _do_swap(*_):
            self._enc_height_sync_paused = False
            if old_panel is not None and old_panel.parent is self._enc_content:
                self._enc_content.remove_widget(old_panel)
                old_panel.opacity = 1.0  # reset for reuse
            if target.parent is not self._enc_content:
                target._reveal_t = 0.0
                target.opacity = 1.0
                if hasattr(target, "_stage_upd"):
                    target._stage_upd()
                self._enc_content.add_widget(target)
            self._enc_active_stage = key
            self._refresh_tab_highlights(layout_tabs=False)
            Clock.schedule_once(
                lambda dt: self._sync_shell_height(animate_tabs=True), 0)
            Clock.schedule_once(
                lambda dt: self._animate_stage_reveal(target),
                self._STAGE_BOX_EXPAND_DELAY,
            )

        if old_panel is not None:
            self._enc_height_sync_paused = True
            self._animate_stage_retract(old_panel, on_complete=_do_swap)
        else:
            _do_swap()

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
        self._outcome_lbl.height      = dp(44)
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
        Clock.schedule_once(_do_anim, 0)

    def _enc_timestamp(self) -> str:
        now  = datetime.now()
        hour = now.hour % 12 or 12
        ampm = "am" if now.hour < 12 else "pm"
        return f"{hour}:{now.minute:02d}{ampm}"

    def _build_frozen_encounter_shell(self, record: dict):
        """Build a self-contained read-only replay of the encounter flow.
        Uses the same gold-rail + _EncTab layout as the live shell.
        All tabs are clickable and open their respective frozen panel.
        """
        from kivy.uix.widget import Widget as _W

        passed = record.get('passed', True)
        choice = record.get('choice', 'pass')
        stages = ['severity', 'save']
        if not passed:
            stages += ['sanity', 'choice']
        LABELS = {'severity': 'SEVERITY', 'save': 'SAVE',
                  'sanity': 'SANITY', 'choice': 'SELECT'}

        # ── shell ────────────────────────────────────────────────────────
        # The EncounterListItem's 6dp accent bar IS the rail — no separate bar here.
        shell = _W(size_hint_y=None, height=0)
        clip_children(shell)

        content = MDBoxLayout(
            orientation='vertical', spacing=dp(6),
            padding=[0, dp(8), 0, dp(8)],
            size_hint=(None, None), height=0)
        shell.add_widget(content)

        # ── panel factory ─────────────────────────────────────────────────
        def _mk_card(border_hex, min_h=100):
            box = MDBoxLayout(
                orientation='vertical', spacing=dp(8),
                padding=[dp(14), dp(12), dp(14), dp(12)],
                size_hint=(1, None), adaptive_height=True)
            box._min_stage_height = dp(min_h)
            box._reveal_t = 1.0
            box._reveal_evt = None
            with box.canvas.before:
                StencilPush()
                _clip = Rectangle()
                StencilUse()
                Color(*T.k(border_hex, 0.06))
                _bd = RoundedRectangle(radius=[0, dp(12), dp(12), 0])
                Color(*T.k(border_hex, 0.018))
                _bg = RoundedRectangle(radius=[0, dp(11), dp(11), 0])
                Color(*T.k(border_hex))
                _ln = Line(width=dp(1.6), cap="none", joint="bevel")
            with box.canvas.after:
                StencilUnUse()
                StencilPop()
            def _upd(w, *_, _bd=_bd, _bg=_bg, _ln=_ln, _clip=_clip):
                reveal_t = max(0.0, min(1.0, getattr(w, "_reveal_t", 1.0)))
                vis_w = max(0, w.width * reveal_t)
                _clip.pos  = (w.x, w.y)
                _clip.size = (vis_w, w.height)
                _bd.pos = w.pos;  _bd.size = (vis_w, w.height)
                _bg.pos = (w.x+1, w.y+1)
                _bg.size = (max(0, vis_w-2), max(0, w.height-2))
                x, y, ww, hh = w.x, w.y, w.width, w.height
                rx = x + max(0, vis_w) - 1
                if vis_w > dp(20):
                    _ln.points = [x+dp(4), y+hh-1, rx-dp(12), y+hh-1,
                                   rx, y+hh-dp(12), rx, y+dp(12),
                                   rx-dp(12), y, x+dp(4), y]
                else:
                    _ln.points = []
            box.bind(pos=_upd, size=_upd)
            box._stage_upd = lambda: _upd(box)
            return box

        def _lbl(text, color=T.TEXT, style='Body1', bold=False, h=None, markup=False):
            kw = dict(text=text, bold=bold, markup=markup,
                      theme_text_color='Custom', text_color=T.k(color),
                      font_style=style, size_hint_y=None, halign='left', valign='middle')
            if h:
                kw['height'] = dp(h)
            else:
                kw['adaptive_height'] = True
            w = MDLabel(**kw)
            w.bind(width=lambda inst, v: setattr(inst, 'text_size', (v, None)))
            return w

        def _mk_metric(cat, val_text, accent):
            row = MDBoxLayout(orientation='horizontal', adaptive_height=True, spacing=0)
            with row.canvas.before:
                Color(*T.k(T.BG_INSET)); _bg = RoundedRectangle(radius=[dp(5)])
                Color(*T.k(accent));     _ac = Rectangle()
            def _upd_r(w, *_, _bg=_bg, _ac=_ac):
                _bg.pos = w.pos; _bg.size = w.size
                _ac.pos = w.pos; _ac.size = (dp(4), w.height)
            row.bind(pos=_upd_r, size=_upd_r)
            inner = MDBoxLayout(orientation='vertical',
                                padding=[dp(12), dp(6), dp(8), dp(6)],
                                spacing=dp(2), adaptive_height=True)
            inner.add_widget(MDLabel(
                text=cat, bold=True,
                theme_text_color='Custom', text_color=T.k(T.WHITE),
                font_style='Caption', size_hint_y=None, height=dp(16)))
            vl = MDLabel(text=val_text, markup=True,
                         theme_text_color='Custom', text_color=T.k(T.TEXT_BRIGHT),
                         font_style='Caption', size_hint_y=None, adaptive_height=True)
            vl.bind(width=lambda inst, v: setattr(inst, 'text_size', (v, None)))
            inner.add_widget(vl)
            row.add_widget(inner)
            return row

        # ── severity panel ───────────────────────────────────────────────
        info = FEAR_STAGES[record['stage']]
        sev_panel = _mk_card(info.color, 100)
        sev_panel.add_widget(_lbl(
            f"[b][color={info.color}]{info.name}[/color][/b]",
            style='Subtitle1', h=28, markup=True))
        sev_panel.add_widget(_lbl(info.desc, color=T.WHITE))

        # ── save panel ───────────────────────────────────────────────────
        save_col = T.STAGE_1 if passed else T.BLOOD_LT
        save_panel = _mk_card(save_col, 100)
        save_panel.add_widget(_lbl(
            f"Wisdom Saving Throw: [color={save_col}]{record.get('wis', 0)}[/color]",
            color=T.TEXT_BRIGHT, style='H5', bold=True, h=56, markup=True))
        save_panel.add_widget(_lbl(
            record.get('wis_str', f"WIS Save: {record.get('wis', 0)} VS DC {record.get('dc', 0)}"),
            color=T.TEXT_DIM, style='Caption'))
        save_panel.add_widget(_lbl(
            f"[b][color={save_col}]{'PASSED' if passed else 'FAILED'}[/color][/b]",
            style='H5', h=44, markup=True))

        # ── sanity panel ─────────────────────────────────────────────────
        san_panel = None
        if not passed:
            san_panel = _mk_card(T.PURPLE_LT, 80)
            san_panel.add_widget(_lbl(
                f"[b]Sanity Roll:[/b] [color={T.PURPLE_LT}]{record.get('san_roll', 0)}[/color]",
                style='H5', h=56, markup=True))
            san_info = record.get('san_info', '')
            if san_info:
                san_panel.add_widget(_lbl(san_info, color=T.TEXT_DIM, style='Caption'))

        # ── choice panel ─────────────────────────────────────────────────
        choice_panel = None
        if not passed and choice in ('confront', 'avoid'):
            preview = record.get('choice_preview') or {}
            if choice == 'confront':
                choice_panel = _mk_card(T.BLOOD_LT, 130)
                choice_panel.add_widget(
                    _lbl('CONFRONT', color=T.BLOOD_LT, style='Subtitle1', bold=True, h=28))
                choice_panel.add_widget(
                    _mk_metric('SANITY LOSS',
                               preview.get('sanity_text', f"\u2212{record.get('san_change', 0)}"),
                               T.PURPLE_LT))
                choice_panel.add_widget(
                    _mk_metric('DESENSITIZATION',
                               preview.get('desens_text', 'Fear removed' if record.get('fear_removed') else ''),
                               T.DESENS_LT))
            else:
                choice_panel = _mk_card(T.STAGE_1, 150)
                choice_panel.add_widget(
                    _lbl('AVOID', color=T.GREEN, style='Subtitle1', bold=True, h=28))
                choice_panel.add_widget(
                    _mk_metric('SANITY GAIN',
                               preview.get('sanity_text', f"+{record.get('san_change', 0)}"),
                               T.PURPLE_LT))
                choice_panel.add_widget(
                    _mk_metric('SEVERITY',
                               preview.get('severity_text', ''),
                               T.GOLD_LT))
                choice_panel.add_widget(
                    _mk_metric('DESENSITIZATION',
                               preview.get('desens_text', 'Already at minimum'),
                               T.DESENS_LT))

        panels = {'severity': sev_panel, 'save': save_panel}
        if san_panel:    panels['sanity'] = san_panel
        if choice_panel: panels['choice'] = choice_panel

        # ── tabs ──────────────────────────────────────────────────────────
        tabs = {}
        active_key = [None]
        stage_tab_caps = {
            'severity': info.color,
            'save': T.GOLD,
            'sanity': T.PURPLE_LT,
            'choice': T.BLOOD_LT if choice == 'confront' else T.GREEN,
        }

        def _refresh_hl(active):
            """Set visual state and commit/side-bar flags before _do_layout positions tabs."""
            for i, k in enumerate(stages):
                t = tabs[k]
                t._dim_pending = False
                t._commit_evt  = None
                t._commit_done = True
                t._side_live   = True
                if active is not None and k == active:
                    t.set_state("active")
                else:
                    t.set_state("done_new")
                t.opacity = 1.0
                t._upd_canvas()

        def _animate_panel_reveal(panel, duration=0.24):
            if panel is None:
                return
            if getattr(panel, "_reveal_evt", None):
                panel._reveal_evt.cancel()
                panel._reveal_evt = None
            panel._reveal_t = 0.0
            panel.opacity = 1.0
            if hasattr(panel, "_stage_upd"):
                panel._stage_upd()

            start_t = Clock.get_boottime()

            def _tick(dt):
                prog = min(1.0, (Clock.get_boottime() - start_t) / max(0.001, duration))
                eased = 1.0 - pow(1.0 - prog, 3)
                panel._reveal_t = eased
                panel.opacity = 1.0
                if hasattr(panel, "_stage_upd"):
                    panel._stage_upd()
                if prog >= 1.0:
                    panel.opacity = 1.0
                    panel._reveal_evt = None
                    return False
                return True

            panel._reveal_evt = Clock.schedule_interval(_tick, 1 / 60)

        def _animate_panel_retract(panel, duration=0.10, on_complete=None):
            if panel is None:
                if on_complete:
                    on_complete()
                return
            if getattr(panel, "_reveal_evt", None):
                panel._reveal_evt.cancel()
                panel._reveal_evt = None

            start_t = Clock.get_boottime()
            start_reveal_t = max(0.0, min(1.0, getattr(panel, "_reveal_t", 1.0)))

            def _tick(dt):
                prog = min(1.0, (Clock.get_boottime() - start_t) / max(0.001, duration))
                eased = pow(prog, 3)
                panel._reveal_t = start_reveal_t * (1.0 - eased)
                panel.opacity = 1.0
                if hasattr(panel, "_stage_upd"):
                    panel._stage_upd()
                if prog >= 1.0:
                    panel._reveal_t = 0.0
                    panel.opacity = 1.0
                    if hasattr(panel, "_stage_upd"):
                        panel._stage_upd()
                    panel._reveal_evt = None
                    if on_complete:
                        on_complete()
                    return False
                return True

            panel._reveal_evt = Clock.schedule_interval(_tick, 1 / 60)

        def _do_layout(active, animate_tabs=False):
            n = len(stages)
            content_w = max(0, shell.width - EncounterListItem._CONTENT_RIGHT_INSET)
            tabs_h = _EncTab._TOP_PAD + n*_EncTab._TAB_H + (n-1)*_EncTab._TAB_GAP

            if active is None:
                # No tab selected: all tabs stacked at top, content hidden
                shell.height    = tabs_h
                content.width   = content_w
                content.height  = 0
                content.opacity = 0
                for i, k in enumerate(stages):
                    t = tabs[k]
                    local_y = (tabs_h - _EncTab._TOP_PAD
                               - (i+1)*_EncTab._TAB_H - i*_EncTab._TAB_GAP)
                    if animate_tabs:
                        Animation.cancel_all(t, "x", "y")
                        Animation(x=shell.x, y=shell.y + local_y,
                                  duration=0.22, t="in_out_cubic").start(t)
                    else:
                        t.pos  = (shell.x, shell.y + local_y)
                    t.size = (_EncTab._TAB_W, _EncTab._TAB_H)
                return

            panel = panels.get(active)
            content_h = max(dp(80),
                            getattr(panel, 'minimum_height', 0) if panel else 0,
                            getattr(panel, '_min_stage_height', 0) if panel else 0)
            gap = dp(8)
            shell_h = tabs_h + gap + content_h
            shell.height = shell_h
            aidx = stages.index(active)
            tabs_above = (_EncTab._TOP_PAD
                          + aidx * (_EncTab._TAB_H + _EncTab._TAB_GAP)
                          + _EncTab._TAB_H)
            content.x      = shell.x + dp(1)
            content.y      = shell.y + shell_h - tabs_above - gap - content_h
            content.width  = content_w
            content.height = content_h
            for i, k in enumerate(stages):
                t = tabs[k]
                extra = (content_h + gap) if i > aidx else 0
                local_y = (shell_h - _EncTab._TOP_PAD
                           - (i+1)*_EncTab._TAB_H - i*_EncTab._TAB_GAP - extra)
                target_x = shell.x
                target_y = shell.y + local_y
                if animate_tabs:
                    Animation.cancel_all(t, "x", "y")
                    Animation(x=target_x, y=target_y,
                              duration=0.22, t="in_out_cubic").start(t)
                else:
                    # Setting pos triggers _upd_canvas which draws side bars at correct coords
                    t.pos  = (target_x, target_y)
                t.size = (_EncTab._TAB_W, _EncTab._TAB_H)

        def _close_tab(animate=True):
            old_panel = content.children[0] if content.children else None
            active_key[0] = None

            def _do_clear():
                content.clear_widgets()
                content.opacity = 0
                _refresh_hl(None)
                Clock.schedule_once(lambda dt: _do_layout(None, animate_tabs=animate))

            if animate and old_panel is not None:
                _animate_panel_retract(old_panel, on_complete=_do_clear)
            else:
                if old_panel is not None:
                    old_panel._reveal_t = 0.0
                    old_panel.opacity = 1.0
                    if hasattr(old_panel, "_stage_upd"):
                        old_panel._stage_upd()
                _do_clear()

        def _open_tab(key, animate=True):
            if active_key[0] == key and content.children:
                _close_tab(animate=animate)
                return
            old_panel = content.children[0] if content.children else None
            active_key[0] = key

            def _do_swap():
                content.clear_widgets()
                panel = panels.get(key)
                if panel:
                    if animate:
                        panel._reveal_t = 0.0
                        panel.opacity = 1.0
                        if hasattr(panel, "_stage_upd"):
                            panel._stage_upd()
                    else:
                        panel._reveal_t = 1.0
                        panel.opacity = 1.0
                        if hasattr(panel, "_stage_upd"):
                            panel._stage_upd()
                    content.add_widget(panel)
                _refresh_hl(key)
                def _layout_then_reveal(dt):
                    _do_layout(key, animate_tabs=animate)
                    content.opacity = 1.0
                    if panel is None:
                        return
                    if animate:
                        _animate_panel_reveal(panel)
                    else:
                        panel._reveal_t = 1.0
                        panel.opacity = 1.0
                        if hasattr(panel, "_stage_upd"):
                            panel._stage_upd()
                Clock.schedule_once(_layout_then_reveal)

            if animate and old_panel is not None:
                _animate_panel_retract(old_panel, on_complete=_do_swap)
            else:
                _do_swap()

        def _animate_tabs_from_rail():
            def _start(_dt):
                _do_layout(active_key[0])
                for k in stages:
                    t = tabs[k]
                    Animation.cancel_all(t, "x", "width")
                    target_x = t.x
                    target_w = t.width
                    t.x = shell.x
                    t.width = _EncTab._RAIL_W
                    t._upd_canvas()
                    Animation(x=target_x, width=target_w, duration=0.24, t="out_cubic").start(t)
            Clock.schedule_once(_start, 0)

        shell.bind(
            pos=lambda *_: _do_layout(active_key[0]),
            size=lambda *_: _do_layout(active_key[0]))

        for key in stages:
            tab = _EncTab(key, LABELS[key], _open_tab)
            tab._shown  = True
            tab._cap_hex = stage_tab_caps.get(key)
            tab.opacity = 1
            tabs[key] = tab
            shell.add_widget(tab)

        # All tabs start with full fill; no tab is pre-selected
        _refresh_hl(None)

        shell._on_parent_open = _animate_tabs_from_rail
        shell._on_parent_close = lambda: _close_tab(animate=False)
        return shell

    def _resolve_encounter(self, title: str, subtitle: str, content_widget, after_complete=None):
        """Transition the active _enc_item to completed state."""
        item = self._enc_item
        if item is not None:
            fear_name = getattr(item, '_fear_name', None)
            if fear_name is not None:
                self._fear_enc_items.setdefault(fear_name, []).append(item)
                rec = getattr(item, '_enc_record', None)
                if rec is not None:
                    self._fear_enc_records.setdefault(fear_name, []).append(rec)
            item.set_completed(title, subtitle, content_widget, on_complete=after_complete)
        elif callable(after_complete):
            after_complete()
        self._enc_item = None

    def _collapse_other_encounters(self, keep_item=None):
        if not self._enc_items_box:
            return True
        live_other_open = False
        for item in list(self._enc_items_box.children):
            if not isinstance(item, EncounterListItem) or item is keep_item:
                continue
            if item._mode == "live":
                live_other_open = True
                continue
            if item.open_state:
                item.set_open(False, animate=True)
        if live_other_open and keep_item is not None and keep_item._mode != "live":
            return False
        return True

    def _switch_encounter_list(self, new_name: str | None):
        """Swap _enc_items_box to show only completed encounters for new_name."""
        if self._enc_list_fear == new_name:
            if new_name:
                self._enc_fear_name_lbl.text   = f"[color={T.GOLD_LT}]{new_name}[/color]"
                self._enc_fear_banner.height   = dp(50)
                self._enc_fear_banner.opacity  = 1
                self._enc_section_lbl.text     = "Encounter List"
                self._enc_header_row.height    = dp(32)
                self._enc_header_row.opacity   = 1
            return
        live_item = self._enc_item
        # Remove all completed items (keep the live item in place)
        for child in list(self._enc_items_box.children):
            if isinstance(child, EncounterListItem) and child is not live_item:
                self._enc_items_box.remove_widget(child)
        # Re-add completed items for the new fear in insertion order
        if new_name is not None:
            for item in self._fear_enc_items.get(new_name, []):
                self._enc_items_box.add_widget(
                    item, index=len(self._enc_items_box.children))
        self._enc_list_fear      = new_name
        self._selected_enc_item  = None
        self._enc_delete_btn.disabled = True
        # Update the selected fear banner and header row
        if new_name:
            self._enc_fear_name_lbl.text   = f"[color={T.GOLD_LT}]{new_name}[/color]"
            self._enc_fear_banner.height   = dp(50)
            self._enc_fear_banner.opacity  = 1
            self._enc_section_lbl.text     = "Encounter List"
            self._enc_header_row.height    = dp(32)
            self._enc_header_row.opacity   = 1
        else:
            self._enc_fear_name_lbl.text   = ""
            self._enc_fear_banner.height   = 0
            self._enc_fear_banner.opacity  = 0
            self._enc_section_lbl.text     = ""
            self._enc_header_row.height    = 0
            self._enc_header_row.opacity   = 0

    def _restore_enc_records(self, records_by_fear: dict):
        """Rebuild encounter list items from persisted records (called on load)."""
        self._fear_enc_items.clear()
        self._fear_enc_records.clear()
        # Clear any stale widgets from a previous session
        if self._enc_items_box:
            for child in list(self._enc_items_box.children):
                if isinstance(child, EncounterListItem) and child._mode == "completed":
                    self._enc_items_box.remove_widget(child)
        for fear_name, records in records_by_fear.items():
            for rec in records:
                shell = self._build_frozen_encounter_shell(rec)
                item = EncounterListItem()
                item._on_open_cb = self._collapse_other_encounters
                item._fear_name  = fear_name
                item._enc_record = rec
                item.bind(open_state=self._on_enc_item_open_state)
                item.set_completed(
                    rec.get('fear_name', fear_name),
                    rec.get('subtitle', ''),
                    shell,
                )
                self._fear_enc_items.setdefault(fear_name, []).append(item)
                self._fear_enc_records.setdefault(fear_name, []).append(rec)

    def _on_enc_item_open_state(self, item, is_open):
        """Enable/disable the header delete button based on which item is expanded."""
        if is_open and item._mode == "completed":
            self._selected_enc_item = item
            self._enc_delete_btn.disabled = False
        else:
            # Re-scan for any other open completed item
            self._selected_enc_item = None
            self._enc_delete_btn.disabled = True
            for child in self._enc_items_box.children:
                if (isinstance(child, EncounterListItem)
                        and child is not item
                        and child.open_state
                        and child._mode == "completed"):
                    self._selected_enc_item = child
                    self._enc_delete_btn.disabled = False
                    break

    def _on_delete_selected_encounter(self, *_):
        """Delete the currently selected (open) encounter item."""
        item = self._selected_enc_item
        if item is None:
            return
        self._selected_enc_item = None
        self._enc_delete_btn.disabled = True
        self._delete_encounter_item(item)

    def _delete_encounter_item(self, item: EncounterListItem):
        """Remove a completed encounter item from the list and per-fear store."""
        fear_name = getattr(item, '_fear_name', None)
        if fear_name is not None:
            items = self._fear_enc_items.get(fear_name, [])
            if item in items:
                items.remove(item)
            rec = getattr(item, '_enc_record', None)
            if rec is not None:
                recs = self._fear_enc_records.get(fear_name, [])
                if rec in recs:
                    recs.remove(rec)
        if self._enc_items_box and item.parent is self._enc_items_box:
            self._enc_items_box.remove_widget(item)
        self._save()

    def _end_enc(self):
        """Reset encounter state and flow shell (called after _resolve_encounter)."""
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
        self._severity_effect_lbl.text = f"[color={T.WHITE}]{info.desc}[/color]{extra}"
        self._refresh_tab_highlights(layout_tabs=False)

    def _start_save_stage(self, wis_save: int, dc: int):
        self._set_stage_available("save", True, refresh_highlights=False)
        self._open_encounter_stage("save", animate=True)
        Clock.schedule_once(
            lambda _: self._animate_roll_result(wis_save, dc),
            self._TAB_SETTLE_DELAY,
        )

    def _start_severity_stage(self, fear_name: str, stage: int, wis_save: int, dc: int):
        self._set_encounter_severity_preview(fear_name, stage)
        self._set_stage_available("severity", True, refresh_highlights=False)
        self._open_encounter_stage("severity", animate=True)
        def _start_commit(_dt):
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
        Clock.schedule_once(_start_commit, self._TAB_SETTLE_DELAY)


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

    # Ã¢"â‚¬Ã¢"â‚¬ Public refresh Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬

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
            self._enc_btn.disabled = False
            self._stage = stage
            self._update_severity_visuals()
            self._update_desens_visuals()
            self._autofill_dc()
        else:
            self._enc_btn.disabled = True
        self._switch_encounter_list(self._selected_fear)

    # Ã¢"â‚¬Ã¢"â‚¬ Event: Severity selection Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬

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

    # Ã¢"â‚¬Ã¢"â‚¬ Event: Desens rung selection Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬

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

    # Ã¢"â‚¬Ã¢"â‚¬ Event: Fear tap Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬

    def _on_fear_tap(self, widget: SwipeFillListItem, name: str):
        if self._sel_fear_widget and self._sel_fear_widget is not widget:
            self._sel_fear_widget.set_selected(False, persist=False)
        self._selected_fear   = name
        self._sel_fear_widget = widget
        widget.set_selected(True, persist=True)
        app   = self._app()
        stage = app.fm.get_stage(name)
        info  = FEAR_STAGES[stage]
        self._enc_btn.disabled        = False
        self._stage = stage
        self._update_severity_visuals()
        self._update_desens_visuals()
        self._update_effects_banner()
        self._autofill_dc()
        self._switch_encounter_list(name)

    # Ã¢"â‚¬Ã¢"â‚¬ Event: Add fear Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬

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
        self._fear_enc_items.pop(name, None)
        self._selected_fear   = None
        self._sel_fear_widget = None
        self.refresh()
        self._save()

    # Ã¢"â‚¬Ã¢"â‚¬ Event: Encounter — Step 1: roll WIS save Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬

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
        self._enc_dc_used = dc

        # Track encounter number and create a live list item
        self._current_enc_num = app.fm.incr_enc_count(name)
        self._collapse_other_encounters()
        new_item = EncounterListItem()
        new_item._on_open_cb = self._collapse_other_encounters
        new_item._fear_name  = name
        new_item.bind(open_state=self._on_enc_item_open_state)
        self._enc_items_box.add_widget(
            new_item, index=len(self._enc_items_box.children))
        new_item.start_live(
            name,
            stage,
            self._enc_flow_shell,
            subtitle=f"Encounter {self._current_enc_num}  |  {self._enc_timestamp()}",
        )
        self._enc_item = new_item

        # Extreme Severity: delayed exhaustion buffer
        if False and stage == 4:
            self._push_undo()
            app.state.exhaustion = int(clamp(app.state.exhaustion + 1, 0, 6))
            self._log("Extreme Severity — +1 Exhaustion applied before encounter")
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
            roll_str = f"D20 Adv({rolls[0]},{rolls[1]})Ã¢â€ â€™{d20}"
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

        # Ã¢"â‚¬Ã¢"â‚¬ Severity effects popup — fires immediately when encounter opens Ã¢"â‚¬Ã¢"â‚¬
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
        self._outcome_lbl.height      = dp(44)
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
                opacity=1,
                duration=0.22, t="out_cubic"
            ).start(self._outcome_lbl)

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

        # Sweep duration = spin_time + land_delay + outcome_delay + outcome_anim â‰ˆ 2.09s
        _spin_intervals = [0.022] * 12 + [0.065] * 5 + [0.17] * 4
        _spin_t = sum(_spin_intervals)
        _sweep_dur = _spin_t + 0.30 + 0.30 + 0.22  # land_delay + outcome_delay + outcome_anim

        # Start sweep and spin at the same moment
        self._play_tab_commit("save", total_duration=_sweep_dur, on_complete=_continue_flow)
        self._spin_number(self._enc_roll_num, wis_save, 20, _land)

    # â"€â"€ Event: Use Hope (re-roll on fail) â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€

    def _use_hope(self):
        app = self._app()
        self._push_undo()
        app.state.hope = False
        self._hope_row.height  = 0
        self._hope_row.opacity = 0
        app.refresh_all()
        # Hope guarantees a pass — auto-succeed the encounter
        self._on_pass()

    # â"€â"€ Event: Confirm failed save — Step 2 â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€

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

        # â"€â"€ CONFRONT card labels â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€
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

        # â"€â"€ AVOID card labels â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€
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
            self._set_stage_available("choice", True, refresh_highlights=False)
            self._open_encounter_stage("choice", animate=True)
            Clock.schedule_once(lambda dt: self._sync_shell_height(), 0)
            reveal_delay = self._TAB_SETTLE_DELAY + self._CHOICE_REVEAL_DELAY

            def _show_confront(_dt):
                self._animate_stage_reveal(self._confront_card)

            def _show_avoid(_dt):
                self._animate_stage_reveal(self._avoid_card)
                Clock.schedule_once(lambda __: self._sync_shell_height(), 0.02)

            Clock.schedule_once(_show_confront, reveal_delay)
            Clock.schedule_once(_show_avoid, reveal_delay + 0.12)
            Clock.schedule_once(lambda _: setattr(self._push_btn, "disabled", False), reveal_delay + 0.24)
            Clock.schedule_once(lambda _: setattr(self._avoid_btn, "disabled", False), reveal_delay + 0.24)

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
            self._set_stage_available("sanity", True, refresh_highlights=False)
            self._open_encounter_stage("sanity", animate=True)
            # Sweep and spin start together; sweep ends when number turns purple
            # Sweep duration = spin_time + land_delay + colorise_delay + color_anim â‰ˆ 2.04s
            _spin_intervals = [0.022] * 12 + [0.065] * 5 + [0.17] * 4
            _spin_t = sum(_spin_intervals)
            _sweep_dur = _spin_t + 0.30 + 0.22 + 0.25  # land_delay + colorise_delay + color_anim
            def _start_sanity_commit(_dt2):
                self._play_tab_commit(
                    "sanity",
                    total_duration=_sweep_dur,
                    on_complete=lambda: Clock.schedule_once(_reveal_preview, 0.10),
                )
                self._spin_number(self._san_num_lbl, total, _max_val, _san_land)

            Clock.schedule_once(_start_sanity_commit, self._TAB_SETTLE_DELAY)

        Clock.schedule_once(_start_sanity_roll, 0.20)


    def _on_pass(self, *_):
        name  = self._enc.fear_name or ""
        stage = self._enc.fear_stage or 1
        wis   = self._enc.wis_save_total or 0
        dc    = self._enc_dc_used
        info  = FEAR_STAGES[stage]
        enc   = self._current_enc_num
        ts    = self._enc_timestamp()

        title    = name
        subtitle = f"Encounter {enc}  |  {ts}"
        record = {
            'fear_name': name, 'stage': stage, 'wis': wis, 'dc': dc,
            'wis_str': getattr(self, '_enc_wis_roll_info', f"WIS {wis} vs DC {dc}"),
            'passed': True, 'choice': 'pass',
            'subtitle': subtitle,
        }
        if self._enc_item is not None:
            self._enc_item._enc_record = record
        shell = self._build_frozen_encounter_shell(record)
        self._resolve_encounter(
            title, subtitle, shell,
            after_complete=lambda: (
                self._log("Passed -- encounter ends cleanly."),
                self._end_enc(),
                self._save(),
            ),
        )

    # Ã¢"â‚¬Ã¢"â‚¬ Event: Confront Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬

    def _on_push(self, *_):
        app  = self._app()
        amt  = self._enc.roll_total or 0
        name = self._enc.fear_name
        self._san_result_lbl.text = ""
        self._push_btn.disabled   = True
        self._avoid_btn.disabled  = True
        self._enc_stage_tabs["choice"]._cap_hex = T.BLOOD_LT
        self._refresh_tab_highlights(layout_tabs=False)

        cur_rung = app.fm.get_desens(name)
        fear_cured = (cur_rung == 4)
        new_rung_preview = min(4, cur_rung + 1)
        wis_s = self._enc.wis_save_total or 0
        dc_s = self._enc_dc_used
        enc_s = self._current_enc_num
        ts_s = self._enc_timestamp()
        record_conf = {
            'fear_name': name, 'stage': self._enc.fear_stage or 1,
            'wis': wis_s, 'dc': dc_s,
            'wis_str': getattr(self, '_enc_wis_roll_info', f"WIS {wis_s} vs DC {dc_s}"),
            'passed': False, 'choice': 'confront',
            'san_roll': amt, 'san_change': amt,
            'san_info': self._san_info_lbl.text,
            'desens_old': cur_rung, 'desens_new': new_rung_preview, 'fear_removed': fear_cured,
            'choice_preview': {
                'sanity_text': self._conf_sanity_lbl.text,
                'desens_text': self._conf_desens_lbl.text,
            },
            'subtitle': f"Encounter {enc_s}  |  {ts_s}",
        }
        if self._enc_item is not None:
            self._enc_item._enc_record = record_conf
        shell_conf = self._build_frozen_encounter_shell(record_conf)

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
                    _thresh_notif = f" [color={_ins_col}]Ã¢â€ â€™ Cured {self._kind_label(_tk)} Insanity[/color]"
                elif _pre_kind_counts.get(_tk, 0) > 0 and _tk == "indefinite":
                    continue
                else:
                    _thresh_notif = f" [color={_ins_col}]Ã¢â€ â€™ {self._kind_label(_tk)} Insanity[/color]"
            if fear_cured:
                self._log(f"FEAR CURED: {name} ÃƒÂ¢Ã¢â€šÂ¬Ã¢â‚¬Â Extreme Desensitization reached, fear removed.")
                Clock.schedule_once(
                    lambda _: app._san_bar.after_animation(
                        lambda: app.notify_event(
                            f"Fear conquered: {name}!",
                            "fears", T.STAGE_1,
                            action_cb=lambda n=name: self.open_fear(n)
                        )
                    ), 0)
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
            lambda _: self._resolve_encounter(
                name,
                f"Encounter {enc_s}  |  {ts_s}",
                shell_conf,
                after_complete=_apply_confront_consequences,
            ), 0.05))
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
                _thresh_notif = f" [color={_ins_col}]â†' Cured {self._kind_label(_tk)} Insanity[/color]"
            elif _pre_kind_counts.get(_tk, 0) > 0 and _tk == "indefinite":
                continue
            else:
                _thresh_notif = f" [color={_ins_col}]â†' {self._kind_label(_tk)} Insanity[/color]"
        if fear_cured:
            self._log(f"FEAR CURED: {name} — Extreme Desensitization reached, fear removed.")
            app.notify_event(
                f"Fear conquered: {name}!",
                "fears", T.STAGE_1,
                action_cb=lambda n=name: self.open_fear(n)
            )
        else:
            # Sanity loss + desensitization change — batched into one card
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

    # Ã¢"â‚¬Ã¢"â‚¬ Event: Avoid Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬

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

        old_rung_preview = app.fm.get_desens(name)
        new_rung_preview = max(1, old_rung_preview - 1)
        new_stage_preview = min(4, stage + 1)
        wis_av = self._enc.wis_save_total or 0
        dc_av = self._enc_dc_used
        enc_av = self._current_enc_num
        ts_av = self._enc_timestamp()
        record_av = {
            'fear_name': name, 'stage': stage,
            'wis': wis_av, 'dc': dc_av,
            'wis_str': getattr(self, '_enc_wis_roll_info', f"WIS {wis_av} vs DC {dc_av}"),
            'passed': False, 'choice': 'avoid',
            'san_roll': amt, 'san_change': amt,
            'san_info': self._san_info_lbl.text,
            'sev_old': stage, 'sev_new': new_stage_preview,
            'desens_old': old_rung_preview, 'desens_new': new_rung_preview,
            'choice_preview': {
                'sanity_text': self._avd_sanity_lbl.text,
                'severity_text': self._avd_sev_lbl.text,
                'desens_text': self._avd_desens_lbl.text,
            },
            'subtitle': f"Encounter {enc_av}  |  {ts_av}",
        }
        if self._enc_item is not None:
            self._enc_item._enc_record = record_av
        shell_av = self._build_frozen_encounter_shell(record_av)

        def _apply_avoid_consequences():
            self._push_undo()
            _pre_madness_kinds = [m.kind for m in app.state.madnesses]
            cleared   = app.state.apply_recovery(amt)
            new_stage = app.fm.increment_stage(name)
            old_rung  = app.fm.get_desens(name)
            new_rung  = app.fm.decr_desens(name)
            self._log(
                f"Avoided ÃƒÂ¢Ã¢â€šÂ¬Ã¢â‚¬Â recovered {amt} sanity  |  "
                f"{name}: Severity {stage}>{new_stage}  |  "
                f"Desensitization > {DESENS_NAMES[new_rung]}")

            if stage == 4:
                new_fear = app.fm.add_random()
                if new_fear:
                    self._log(f"Extreme Avoid ÃƒÂ¢Ã¢â€šÂ¬Ã¢â‚¬Â panic: new fear added: {new_fear}")
                    Clock.schedule_once(
                        lambda _: app._san_bar.after_animation(
                            lambda: app.notify_event(
                                f"Panic! New fear: {new_fear}", "fears", T.STAGE_4,
                                action_cb=lambda f=new_fear: self.open_fear(f)
                            )
                        ), 0)

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
                    _avoid_thresh_notif = f" [color={_ins_col}]Ã¢â€ â€™ Cured {self._kind_label(_kind)} Insanity[/color]"
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
            lambda _: self._resolve_encounter(
                name,
                f"Encounter {enc_av}  |  {ts_av}",
                shell_av,
                after_complete=_apply_avoid_consequences,
            ), 0.05))
        return
        self._push_undo()
        _pre_madness_kinds = [m.kind for m in app.state.madnesses]
        cleared   = app.state.apply_recovery(amt)
        new_stage = app.fm.increment_stage(name)
        old_rung  = app.fm.get_desens(name)
        new_rung  = app.fm.decr_desens(name)
        self._log(
            f"Avoided — recovered {amt} sanity  |  "
            f"{name}: Severity {stage}>{new_stage}  |  "
            f"Desensitization > {DESENS_NAMES[new_rung]}")

        # Extreme Severity Avoid Ã¢â€ â€™ add random new fear
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
        pct = int(cur / mx * 100) if mx else 0
        _avoid_thresh_notif = ""
        _pre_kind_counts = {k: _pre_madness_kinds.count(k) for k in ("short", "long", "indefinite")}
        for _, _c, _kind in cleared:
            if _kind == "zero":
                continue
            _ins_col = self._kind_color(_kind)
            if _pre_kind_counts.get(_kind, 0) > 0 and _kind != "indefinite":
                _avoid_thresh_notif = f" [color={_ins_col}]â†' Cured {self._kind_label(_kind)} Insanity[/color]"
            elif _pre_kind_counts.get(_kind, 0) > 0 and _kind == "indefinite":
                continue

        # Sanity gain + severity increase + desensitization decrease — batched into one card
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

    # Ã¢"â‚¬Ã¢"â‚¬ Threshold handling Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬

    def _handle_thresholds(self, threshs):
        app = self._app()
        sanity_tab = app._sanity_tab
        events = []
        for label, kind in threshs:
            if kind == "zero":
                self._log(f"WARNING: {label}")
                events.append((T.BLOOD, None, None, label))
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
            def _emit_threshold_events():
                for color, entry, cured_name, lbl in events:
                    if entry is None and cured_name is None:
                        app.notify_event(lbl, "sanity", color)
                    elif cured_name:
                        app.notify_event(f"Threshold cured: {cured_name}", "sanity", color)
                    else:
                        app.notify_event(
                            f"{entry.kind_label} Insanity: [color={color}]{entry.name}[/color]",
                            "sanity", color,
                            action_cb=lambda ee=entry: sanity_tab.open_madness(ee)
                        )
            app.refresh_all(after_sanity=_emit_threshold_events)

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
            if existing and kind != "indefinite":
                cured = existing[0]
                app.state.madnesses.remove(cured)
                cured_name = cured.name if cured.name else cured.kind_label
                self._log(f"THRESHOLD CLEARED (avoid): {label} — {cured_name} cured")
                events.append((color, cured_name))
            elif existing and kind == "indefinite":
                self._log(f"THRESHOLD CLEARED (avoid): {label}")
            else:
                self._log(f"THRESHOLD CLEARED (avoid): {label} — no matching insanity to cure")
        if events:
            def _emit_recovery_events():
                for color, cured_name in events:
                    app.notify_event(f"Insanity cured: {cured_name}", "sanity", color)
            app.refresh_all(after_sanity=_emit_recovery_events)

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
            if self._enc_item is not None:
                if self._enc_item.parent:
                    self._enc_item.parent.remove_widget(self._enc_item)
                self._enc_item = None


