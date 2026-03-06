"""
Custom Kivy Canvas widgets:
  - SanityBar      : animated gradient sanity bar with threshold marks + % label
  - MadnessBanner  : kept for import compat but zero-height (hidden)
  - ExhaustionWidget: 6 clickable round pips with EXHAUSTION title
"""
from __future__ import annotations

import time

from kivy.app import App
from kivy.clock import Clock
from kivy.core.text import Label as CoreLabel
from kivy.graphics import Color, Ellipse, Line, Rectangle
from kivy.uix.widget import Widget
from kivy.properties import NumericProperty, StringProperty, BoundedNumericProperty

from models import (
    MADNESS, MadnessStage, FEAR_STAGES,
    clamp, lerp, smoothstep, hex_lerp
)
import theme as T


# ────────────────────────────────────────────────────────────────────────────
# SANITY BAR  — gradient bar with threshold marks and live % label
# ────────────────────────────────────────────────────────────────────────────

class SanityBar(Widget):
    """
    Animated horizontal sanity bar.
    Set .pct (0-100) to update; animates with smoothstep easing.
    Set .madness_stage (MadnessStage) to change bar color palette.
    Draws threshold marks at 25/50/75 % and a centred percentage label.
    """
    pct = NumericProperty(100.0)

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._display_pct = 100.0
        self._anim_start  = 100.0
        self._anim_target = 100.0
        self._anim_t0     = 0.0
        self._anim_dur    = 0.5
        self._anim_token  = 0
        self._stage       = MadnessStage.STABLE
        self.bind(pos=self._redraw, size=self._redraw)
        Clock.schedule_once(self._redraw)

    def set_pct(self, pct: float, snap: bool = False):
        """Animate bar to new percentage."""
        pct = clamp(pct, 0.0, 100.0)
        if snap:
            self._display_pct = self._anim_target = pct
            self._redraw()
            return
        self._anim_start  = self._display_pct
        self._anim_target = pct
        self._anim_t0     = time.perf_counter()
        dist = abs(pct - self._anim_start)
        self._anim_dur = clamp(0.25 + dist / 100 * 0.8, 0.25, 1.0)
        self._anim_token += 1
        self._tick(self._anim_token)

    def set_stage(self, stage: MadnessStage):
        self._stage = stage
        self._redraw()

    def _tick(self, token):
        if token != self._anim_token:
            return
        elapsed = time.perf_counter() - self._anim_t0
        t = clamp(elapsed / max(0.001, self._anim_dur), 0.0, 1.0)
        self._display_pct = lerp(self._anim_start, self._anim_target, smoothstep(t))
        self._redraw()
        if t < 1.0:
            Clock.schedule_once(lambda dt: self._tick(token), 1/30)

    def _redraw(self, *_):
        self.canvas.clear()
        w, h = self.width, self.height
        if w < 2 or h < 2:
            return

        info    = MADNESS.get(self._stage, MADNESS[MadnessStage.STABLE])
        c_dark  = info.bar_dark
        c_light = info.bar_light
        pct     = self._display_pct / 100.0
        fill_w  = int(w * pct)
        bands   = max(1, fill_w)

        with self.canvas:
            # Background
            Color(*T.k(T.BG_INSET))
            Rectangle(pos=self.pos, size=self.size)

            # Gradient fill (light centre → dark edges)
            if fill_w > 0:
                for i in range(bands):
                    t_val = abs(2 * i / max(1, bands - 1) - 1)
                    col = hex_lerp(c_light, c_dark, t_val * t_val)
                    Color(*T.k(col))
                    Rectangle(pos=(self.x + i, self.y), size=(1, h))

            # Threshold marks at 25 / 50 / 75 % with tiny labels
            for thresh, label_str in ((0.25, "25%"), (0.50, "50%"), (0.75, "75%")):
                tx = int(self.x + w * thresh)
                Color(*T.k(T.BORDER_LT))
                Line(points=[tx, self.y, tx, self.y + h], width=1,
                     dash_length=3, dash_offset=2)
                # Small threshold text above tick
                tlbl = CoreLabel(text=label_str, font_size=7,
                                 color=T.k(T.BORDER_LT))
                tlbl.refresh()
                Color(1, 1, 1, 1)
                Rectangle(texture=tlbl.texture,
                          pos=(tx - tlbl.texture.width // 2,
                               self.y + h - tlbl.texture.height - 1),
                          size=tlbl.texture.size)

            # Percentage label centred in the fill area
            pct_str = f"{self._display_pct:.0f}%"
            plbl = CoreLabel(text=pct_str, font_size=10, bold=True,
                             color=T.k(T.TEXT_BRIGHT))
            plbl.refresh()
            px = self.x + (w - plbl.texture.width) / 2
            py = self.y + (h - plbl.texture.height) / 2
            Color(1, 1, 1, 1)
            Rectangle(texture=plbl.texture, pos=(px, py), size=plbl.texture.size)

            # Border
            Color(*T.k(T.BORDER))
            Line(rectangle=(self.x, self.y, w, h), width=1)


# ────────────────────────────────────────────────────────────────────────────
# MADNESS BANNER  — kept for import compatibility, zero height / invisible
# ────────────────────────────────────────────────────────────────────────────

class MadnessBanner(Widget):
    """Stub — banner removed per user request. Zero-size invisible widget."""
    stage_key = StringProperty("STABLE")

    def set_stage(self, stage: MadnessStage):
        pass  # no-op

    def pulse(self, cycles: int = 6):
        pass  # no-op


# ────────────────────────────────────────────────────────────────────────────
# EXHAUSTION WIDGET  — 6 round pips, no numbers, EXHAUSTION title above
# ────────────────────────────────────────────────────────────────────────────

class ExhaustionWidget(Widget):
    """
    6 clickable round pips showing exhaustion level (0-6).
    Tap a pip to set exhaustion to that level; tap filled pip to clear to one below.
    Draws its own 'EXHAUSTION' label above the pips.
    """
    level = BoundedNumericProperty(0, min=0, max=6)

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._on_change = None
        self.bind(pos=self._redraw, size=self._redraw, level=self._redraw)
        Clock.schedule_once(self._redraw)

    def set_change_callback(self, cb):
        self._on_change = cb

    def _redraw(self, *_):
        self.canvas.clear()
        w, h = self.width, self.height
        if w < 10 or h < 10:
            return
        n = 6

        # Title "EXHAUSTION" at top of widget
        title_lbl = CoreLabel(text="EXHAUSTION", font_size=8,
                              color=T.k(T.TEXT_DIM))
        title_lbl.refresh()
        title_h = title_lbl.texture.height + 2

        # Pip area below title
        pad = 3
        pip_area_h = h - title_h - pad * 2
        pip_w = (w - pad * (n + 1)) / n
        # Make pips square-ish but capped to available height
        pip_d = min(pip_w, pip_area_h)
        pip_y = self.y + pad + (pip_area_h - pip_d) / 2

        with self.canvas:
            # Title
            Color(1, 1, 1, 1)
            Rectangle(
                texture=title_lbl.texture,
                pos=(self.x + (w - title_lbl.texture.width) / 2,
                     self.y + h - title_h),
                size=title_lbl.texture.size)

            # Pips
            for i in range(n):
                x = self.x + pad + i * (pip_d + pad)
                filled = i < self.level

                # Filled circle
                Color(*T.k(T.BLOOD if filled else T.BG_INSET))
                Ellipse(pos=(x, pip_y), size=(pip_d, pip_d))

                # Border circle
                Color(*T.k(T.BLOOD if filled else T.BORDER))
                Line(ellipse=(x, pip_y, pip_d, pip_d), width=1.2)

    def on_touch_down(self, touch):
        if not self.collide_point(*touch.pos):
            return False
        w = self.width
        n = 6
        pad = 3
        pip_d = min((w - pad * (n + 1)) / n, self.height)
        rel_x = touch.x - self.x
        for i in range(n):
            pip_x = pad + i * (pip_d + pad)
            if pip_x <= rel_x <= pip_x + pip_d:
                new_level = i + 1
                if self.level == new_level:
                    new_level = i  # tap same pip → decrease
                self.level = int(clamp(new_level, 0, 6))
                if self._on_change:
                    self._on_change(self.level)
                return True
        return False
