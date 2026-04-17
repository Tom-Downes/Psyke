"""
Swipe decision control for the fear save Hope prompt.

The control starts with the thumb centered. Drag left to accept failure,
or drag right to spend Hope. Releasing past the confirmation threshold
locks the decision and fires the matching callback; releasing near the
center snaps back to neutral.
"""
from __future__ import annotations

from kivy.animation import Animation
from kivy.clock import Clock
from kivy.graphics import Color, Ellipse, Line, RoundedRectangle
from kivy.metrics import dp
from kivy.properties import BooleanProperty, NumericProperty
from kivy.uix.widget import Widget

from kivymd.uix.boxlayout import MDBoxLayout
from kivymd.uix.label import MDLabel

import theme as T


class HopeDecisionToggle(MDBoxLayout):
    """
    Center-start swipe selector for the Hope decision.

    Swipe left  -> accept failure
    Swipe right -> use Hope

    Callbacks receive the widget instance:
      - on_accept_failure(widget)
      - on_use_hope(widget)
    """

    slide_t = NumericProperty(0.0)   # -1.0 .. 1.0
    locked = BooleanProperty(False)
    dragging = BooleanProperty(False)

    def __init__(self, on_accept_failure=None, on_use_hope=None, **kwargs):
        kwargs.setdefault("orientation", "vertical")
        kwargs.setdefault("adaptive_height", True)
        kwargs.setdefault("spacing", dp(8))
        super().__init__(**kwargs)

        self._on_accept_failure = on_accept_failure
        self._on_use_hope = on_use_hope
        self._drag_touch = None
        self._drag_start_x = 0.0
        self._drag_start_t = 0.0
        self._track_rect = None
        self._thumb_outer = None
        self._thumb_inner = None
        self._center_line = None
        self._left_fill = None
        self._right_fill = None
        self._left_guide = None
        self._right_guide = None
        self._settle_anim = None
        self._thumb_fire = {}

        self.add_widget(self._build_caption())
        self.add_widget(self._build_track_row())

        self.bind(slide_t=self._redraw_track)
        Clock.schedule_once(lambda *_: self._redraw_track(), 0)

    def _build_caption(self):
        box = MDBoxLayout(
            orientation="vertical",
            adaptive_height=True,
            spacing=dp(2),
        )
        prompt = MDLabel(
            text="Swipe To Decide",
            bold=True,
            theme_text_color="Custom",
            text_color=T.k(T.TEXT_BRIGHT),
            font_style="Button",
            size_hint_y=None,
            height=dp(20),
            halign="center",
        )
        hint = MDLabel(
            text="Left: Fail    Right: Pass",
            theme_text_color="Custom",
            text_color=T.k(T.TEXT_DIM),
            font_style="Caption",
            size_hint_y=None,
            height=dp(18),
            halign="center",
        )
        box.add_widget(prompt)
        box.add_widget(hint)
        return box

    def _build_track_row(self):
        row = MDBoxLayout(
            orientation="horizontal",
            size_hint_y=None,
            height=dp(56),
            spacing=dp(2),
        )

        left_wrap = MDBoxLayout(
            orientation="vertical",
            size_hint_x=0.20,
            size_hint_y=1,
        )
        left_wrap.add_widget(Widget())
        self._left_lbl = MDLabel(
            text="SUFFER FAILURE",
            bold=True,
            theme_text_color="Custom",
            text_color=T.k(T.TEXT_DIM),
            font_style="Caption",
            size_hint_x=1,
            size_hint_y=None,
            height=dp(28),
            halign="center",
            valign="middle",
        )
        self._left_lbl.bind(size=lambda inst, *_: setattr(inst, "text_size", inst.size))
        left_wrap.add_widget(self._left_lbl)
        left_wrap.add_widget(Widget())

        self._track = Widget(size_hint_x=0.60, size_hint_y=None, height=dp(56))
        self._track.bind(pos=self._redraw_track, size=self._redraw_track)
        with self._track.canvas.before:
            self._track_bd_col = Color(*T.k(T.BORDER_LT, 0.70))
            self._track_bd = RoundedRectangle(radius=[dp(18)])
            self._track_bg_col = Color(*T.k(T.BG_INSET))
            self._track_bg = RoundedRectangle(radius=[dp(17)])
            self._left_fill_col = Color(*T.k(T.RED_DK, 0.0))
            self._left_fill = RoundedRectangle(radius=[dp(17), 0, 0, dp(17)])
            self._right_fill_col = Color(*T.k(T.GOLD_DK, 0.0))
            self._right_fill = RoundedRectangle(radius=[0, dp(17), dp(17), 0])
            self._center_line_col = Color(*T.k(T.BORDER_LT, 0.75))
            self._center_line = Line(width=dp(1.2))
            self._left_guide_col = Color(*T.k(T.RED, 0.65))
            self._left_guide = Line(width=dp(1.4), cap="round")
            self._right_guide_col = Color(*T.k(T.GOLD, 0.75))
            self._right_guide = Line(width=dp(1.4), cap="round")
        with self._track.canvas.after:
            self._thumb_bd_col = Color(*T.k(T.BORDER_LT))
            self._thumb_outer = Ellipse()
            self._thumb_bg_col = Color(*T.k(T.BG_CARD))
            self._thumb_inner = Ellipse()
            self._thumb_shadow_col = Color(0.0, 0.0, 0.0, 0.40)
            self._thumb_shadow = Ellipse()
            self._thumb_ring_col = Color(*T.k(T.BORDER_LT, 0.82))
            self._thumb_ring = Ellipse()
            self._thumb_ember_col = Color(0.72, 0.24, 0.04, 0.25)
            self._thumb_ember = Ellipse()
            self._thumb_log_col = Color(0.36, 0.18, 0.06, 0.82)
            self._thumb_log_a = Line(width=dp(1.6), cap="round")
            self._thumb_log_b = Line(width=dp(1.6), cap="round")
            self._thumb_heat_col = Color(0.78, 0.20, 0.04, 0.0)
            self._thumb_heat = Ellipse()
            self._thumb_flame_outer_col = Color(0.87, 0.42, 0.07, 0.28)
            self._thumb_flame_outer = Ellipse()
            self._thumb_flame_mid_col = Color(*T.k(T.GOLD, 0.18))
            self._thumb_flame_mid = Ellipse()
            self._thumb_flame_core_col = Color(*T.k(T.GOLD_LT, 0.10))
            self._thumb_flame_core = Ellipse()
            self._thumb_spark_col = Color(1.0, 0.97, 0.76, 0.0)
            self._thumb_spark = Ellipse()

        right_wrap = MDBoxLayout(
            orientation="vertical",
            size_hint_x=0.20,
            size_hint_y=1,
        )
        right_wrap.add_widget(Widget())
        self._right_lbl = MDLabel(
            text="SPEND HOPE",
            bold=True,
            theme_text_color="Custom",
            text_color=T.k(T.TEXT_DIM),
            font_style="Caption",
            size_hint_x=1,
            size_hint_y=None,
            height=dp(28),
            halign="center",
            valign="middle",
        )
        self._right_lbl.bind(size=lambda inst, *_: setattr(inst, "text_size", inst.size))
        right_wrap.add_widget(self._right_lbl)
        right_wrap.add_widget(Widget())

        row.add_widget(left_wrap)
        row.add_widget(self._track)
        row.add_widget(right_wrap)
        return row

    def reset(self, animate: bool = True):
        self.locked = False
        self._animate_to(0.0) if animate else setattr(self, "slide_t", 0.0)

    def _animate_to(self, target: float, on_complete=None):
        if self._settle_anim is not None:
            Animation.cancel_all(self, "slide_t")
            self._settle_anim = None
        anim = Animation(slide_t=target, duration=0.18, t="out_cubic")
        if on_complete is not None:
            anim.bind(on_complete=lambda *_: on_complete())
        self._settle_anim = anim
        anim.start(self)

    def _confirm(self, direction: str):
        if self.locked:
            return
        self.locked = True
        if direction == "left":
            self._animate_to(-1.0, on_complete=lambda: self._dispatch_left())
        else:
            self._animate_to(1.0, on_complete=lambda: self._dispatch_right())

    def _dispatch_left(self):
        if callable(self._on_accept_failure):
            self._on_accept_failure(self)

    def _dispatch_right(self):
        if callable(self._on_use_hope):
            self._on_use_hope(self)

    def _redraw_track(self, *_):
        if not self._track.width or not self._track.height:
            return

        x = self._track.x
        y = self._track.y
        w = self._track.width
        h = self._track.height
        pad = dp(2)
        inner_x = x + pad
        inner_y = y + pad
        inner_w = max(0.0, w - pad * 2)
        inner_h = max(0.0, h - pad * 2)
        radius = inner_h / 2

        self._track_bd.pos = (x, y)
        self._track_bd.size = (w, h)
        self._track_bg.pos = (inner_x, inner_y)
        self._track_bg.size = (inner_w, inner_h)

        center_x = inner_x + inner_w / 2
        self._center_line.points = [center_x, inner_y + dp(8), center_x, inner_y + inner_h - dp(8)]

        guide_y = inner_y + inner_h / 2
        guide_len = dp(12)
        self._left_guide.points = [
            center_x - dp(18), guide_y,
            center_x - dp(18) - guide_len, guide_y,
        ]
        self._right_guide.points = [
            center_x + dp(18), guide_y,
            center_x + dp(18) + guide_len, guide_y,
        ]

        left_alpha = max(0.0, -self.slide_t) * 0.55
        right_alpha = max(0.0, self.slide_t) * 0.55
        self._left_fill_col.rgba = T.k(T.BLOOD_DK, left_alpha)
        self._right_fill_col.rgba = T.k(T.GOLD_DK, right_alpha)
        self._left_fill.pos = (inner_x, inner_y)
        self._left_fill.size = (max(0.0, center_x - inner_x), inner_h)
        self._right_fill.pos = (center_x, inner_y)
        self._right_fill.size = (max(0.0, inner_x + inner_w - center_x), inner_h)

        self._track_bd_col.rgba = T.k(T.BORDER_LT, 0.92 if self.locked else 0.70)
        self._center_line_col.rgba = T.k(T.BORDER_LT, 0.55 if self.locked else 0.75)
        self._left_guide_col.rgba = T.k(T.RED, 0.95 if self.slide_t < -0.70 else 0.65)
        self._right_guide_col.rgba = T.k(T.GOLD, 0.95 if self.slide_t > 0.70 else 0.75)

        thumb_d = max(dp(28), inner_h - dp(6))
        travel = max(0.0, (inner_w - thumb_d) / 2)
        thumb_cx = center_x + travel * self.slide_t
        thumb_x = thumb_cx - thumb_d / 2
        thumb_y = inner_y + (inner_h - thumb_d) / 2

        outer_d = thumb_d + dp(4)
        self._thumb_outer.pos = (thumb_cx - outer_d / 2, inner_y + (inner_h - outer_d) / 2)
        self._thumb_outer.size = (outer_d, outer_d)
        self._thumb_inner.pos = (thumb_x, thumb_y)
        self._thumb_inner.size = (thumb_d, thumb_d)

        if self.slide_t < -0.15:
            self._thumb_bd_col.rgba = T.k(T.RED_LT if self.locked else T.RED)
            self._thumb_bg_col.rgba = T.k(T.BLOOD_DK, 0.95)
            self._left_lbl.text_color = T.k(T.RED_LT if self.locked else T.RED)
            self._right_lbl.text_color = T.k(T.TEXT_DIM, 0.70)
        elif self.slide_t > 0.15:
            self._thumb_bd_col.rgba = T.k(T.GOLD_LT if self.locked else T.GOLD)
            self._thumb_bg_col.rgba = T.k(T.GOLD_DK, 0.95)
            self._left_lbl.text_color = T.k(T.TEXT_DIM, 0.70)
            self._right_lbl.text_color = T.k(T.GOLD_LT if self.locked else T.GOLD)
        else:
            self._thumb_bd_col.rgba = T.k(T.BORDER_LT)
            self._thumb_bg_col.rgba = T.k(T.BG_CARD)
            self._left_lbl.text_color = T.k(T.TEXT_DIM)
            self._right_lbl.text_color = T.k(T.TEXT_DIM)

        # Fire state spans the full swipe distance:
        # far left  -> fully dim / inactive
        # center    -> mid fire
        # far right -> fully lit hope fire
        fire_level = max(0.0, min(1.0, (self.slide_t + 1.0) / 2.0))

        flame_alpha = fire_level
        heat_alpha = max(0.0, (fire_level - 0.18) / 0.82) * 0.22
        spark_alpha = max(0.0, (fire_level - 0.40) / 0.60) * 0.95
        ember_alpha = 0.24 + (1.0 - fire_level) * 0.34
        ring_alpha = 0.70 + fire_level * 0.20
        log_alpha = 0.72 + fire_level * 0.20

        self._thumb_shadow_col.rgba = (0.0, 0.0, 0.0, 0.30 + fire_level * 0.20)
        self._thumb_ring_col.rgba = T.k(T.BORDER_LT, ring_alpha)
        self._thumb_ember_col.rgba = (0.72, 0.24, 0.04, ember_alpha)
        self._thumb_log_col.rgba = (0.36, 0.18, 0.06, log_alpha)
        self._thumb_heat_col.rgba = (0.78, 0.20, 0.04, heat_alpha)
        self._thumb_flame_outer_col.rgba = (0.87, 0.42, 0.07, flame_alpha * 0.90)
        self._thumb_flame_mid_col.rgba = T.k(T.GOLD, flame_alpha * 0.96)
        self._thumb_flame_core_col.rgba = T.k(T.GOLD_LT, flame_alpha)
        self._thumb_spark_col.rgba = (1.0, 0.97, 0.76, spark_alpha)

        fire_pad = thumb_d * 0.12
        fire_w = thumb_d - fire_pad * 2
        fire_h = thumb_d - fire_pad * 2
        fx = thumb_x + fire_pad
        fy = thumb_y + fire_pad * 0.85
        cx = fx + fire_w / 2

        self._thumb_shadow.pos = (cx - fire_w * 0.28, fy + fire_h * 0.08)
        self._thumb_shadow.size = (fire_w * 0.56, fire_h * 0.12)
        self._thumb_ring.pos = (cx - fire_w * 0.27, fy + fire_h * 0.11)
        self._thumb_ring.size = (fire_w * 0.54, fire_h * 0.11)
        self._thumb_ember.pos = (cx - fire_w * 0.18, fy + fire_h * 0.14)
        self._thumb_ember.size = (fire_w * 0.36, fire_h * 0.06)
        self._thumb_log_a.points = [
            fx + fire_w * 0.20, fy + fire_h * 0.20,
            fx + fire_w * 0.68, fy + fire_h * 0.46,
        ]
        self._thumb_log_b.points = [
            fx + fire_w * 0.80, fy + fire_h * 0.20,
            fx + fire_w * 0.32, fy + fire_h * 0.46,
        ]
        self._thumb_heat.pos = (cx - fire_w * 0.30, fy + fire_h * 0.24)
        self._thumb_heat.size = (fire_w * 0.60, fire_h * (0.26 + fire_level * 0.34))

        flame_scale = 0.30 + fire_level * 0.70
        self._thumb_flame_outer.pos = (
            cx - fire_w * 0.19 * flame_scale,
            fy + fire_h * 0.24,
        )
        self._thumb_flame_outer.size = (
            fire_w * 0.38 * flame_scale,
            fire_h * 0.55 * flame_scale,
        )
        self._thumb_flame_mid.pos = (
            cx - fire_w * 0.12 * flame_scale,
            fy + fire_h * 0.34,
        )
        self._thumb_flame_mid.size = (
            fire_w * 0.24 * flame_scale,
            fire_h * 0.40 * flame_scale,
        )
        self._thumb_flame_core.pos = (
            cx - fire_w * 0.07 * flame_scale,
            fy + fire_h * 0.46,
        )
        self._thumb_flame_core.size = (
            fire_w * 0.14 * flame_scale,
            fire_h * 0.24 * flame_scale,
        )
        self._thumb_spark.pos = (
            cx - fire_w * 0.025,
            fy + fire_h * (0.64 + fire_level * 0.08),
        )
        self._thumb_spark.size = (fire_w * 0.05, fire_h * 0.08)

    def on_touch_down(self, touch):
        if self.locked or not self._track.collide_point(*touch.pos):
            return super().on_touch_down(touch)
        touch.ud["hope_toggle_touch"] = True
        touch.grab(self)
        self.dragging = True
        self._drag_touch = touch
        self._drag_start_x = touch.x
        self._drag_start_t = self.slide_t
        if self._settle_anim is not None:
            Animation.cancel_all(self, "slide_t")
            self._settle_anim = None
        return True

    def on_touch_move(self, touch):
        if touch.grab_current is not self or self.locked:
            return super().on_touch_move(touch)
        inner_w = max(1.0, self._track.width - dp(4))
        travel = max(1.0, (inner_w - max(dp(28), self._track.height - dp(10))) / 2)
        delta = (touch.x - self._drag_start_x) / travel
        self.slide_t = max(-1.0, min(1.0, self._drag_start_t + delta))
        return True

    def on_touch_up(self, touch):
        if touch.grab_current is not self:
            return super().on_touch_up(touch)
        touch.ungrab(self)
        self.dragging = False
        self._drag_touch = None
        if self.locked:
            return True
        if self.slide_t <= -0.58:
            self._confirm("left")
        elif self.slide_t >= 0.58:
            self._confirm("right")
        else:
            self._animate_to(0.0)
        return True
