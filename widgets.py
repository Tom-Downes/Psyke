"""
Custom Kivy Canvas widgets:
  - SanityBar      : animated gradient sanity bar with threshold marks
  - MadnessBanner  : stage/madness status banner with pulse animation
  - ExhaustionWidget: 6 clickable pip tracker
"""
from __future__ import annotations

import time

from kivy.app import App
from kivy.clock import Clock
from kivy.core.text import Label as CoreLabel
from kivy.graphics import Color, Line, Rectangle
from kivy.uix.widget import Widget
from kivy.properties import NumericProperty, StringProperty, BoundedNumericProperty

from models import (
    MADNESS, MadnessStage, FEAR_STAGES,
    clamp, lerp, smoothstep, hex_lerp
)
import theme as T


# ────────────────────────────────────────────────────────────────────────────
# SANITY BAR
# ────────────────────────────────────────────────────────────────────────────

class SanityBar(Widget):
    """
    Animated horizontal sanity bar.
    Set .pct (0-100) to update; animates with smoothstep easing.
    Set .madness_stage (MadnessStage) to change bar color palette.
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

        info   = MADNESS.get(self._stage, MADNESS[MadnessStage.STABLE])
        c_dark  = info.bar_dark
        c_light = info.bar_light
        pct    = self._display_pct / 100.0
        fill_w = int(w * pct)
        bands  = max(1, fill_w)

        with self.canvas:
            # Background
            Color(*T.k(T.BG_INSET))
            Rectangle(pos=self.pos, size=self.size)

            # Gradient bands (light centre → dark edges, matching original)
            if fill_w > 0:
                for i in range(bands):
                    t_val = abs(2 * i / max(1, bands - 1) - 1)
                    col = hex_lerp(c_light, c_dark, t_val * t_val)
                    Color(*T.k(col))
                    Rectangle(pos=(self.x + i, self.y), size=(1, h))

            # Threshold marks at 25 / 50 / 75 %
            Color(*T.k(T.BORDER_LT))
            for thresh in (0.25, 0.50, 0.75):
                tx = int(self.x + w * thresh)
                Line(points=[tx, self.y, tx, self.y + h], width=1, dash_length=3, dash_offset=2)

            # Border
            Color(*T.k(T.BORDER))
            Line(rectangle=(self.x, self.y, w, h), width=1)


# ────────────────────────────────────────────────────────────────────────────
# MADNESS BANNER
# ────────────────────────────────────────────────────────────────────────────

class MadnessBanner(Widget):
    """
    Full-width banner displaying current madness stage.
    Pulses border on threshold crossing.
    """
    stage_key = StringProperty("STABLE")

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._pulse      = 0.0
        self._pulse_dir  = 1
        self._pulse_evt  = None
        self.bind(pos=self._redraw, size=self._redraw, stage_key=self._redraw)
        Clock.schedule_once(self._redraw)

    def set_stage(self, stage: MadnessStage):
        self.stage_key = stage.name

    def pulse(self, cycles: int = 6):
        """Start a border-pulse animation (called on threshold crossing)."""
        if self._pulse_evt:
            self._pulse_evt.cancel()
        self._pulse     = 0.0
        self._pulse_dir = 1
        self._remain    = cycles * 2
        self._pulse_evt = Clock.schedule_interval(self._pulse_step, 1/20)

    def _pulse_step(self, dt):
        self._pulse += self._pulse_dir * 0.15
        if self._pulse >= 1.0:
            self._pulse = 1.0; self._pulse_dir = -1
        elif self._pulse <= 0.0:
            self._pulse = 0.0; self._pulse_dir = 1
            self._remain -= 1
            if self._remain <= 0:
                self._pulse_evt.cancel()
                self._pulse_evt = None
        self._redraw()

    def _redraw(self, *_):
        self.canvas.clear()
        w, h = self.width, self.height
        if w < 30 or h < 6:
            return

        info     = MADNESS.get(MadnessStage[self.stage_key], MADNESS[MadnessStage.STABLE])
        bg_color = hex_lerp(T.BG_CARD, info.color, 0.15)
        bw       = int(lerp(1, 4, self._pulse))
        bar_w    = 5

        with self.canvas:
            # Background
            Color(*T.k(bg_color))
            Rectangle(pos=self.pos, size=self.size)

            # Left accent bar
            Color(*T.k(info.color))
            Rectangle(pos=self.pos, size=(bar_w, h))

            # Border (pulses on threshold)
            border_col = hex_lerp(info.color, T.TEXT_BRIGHT, self._pulse * 0.5)
            Color(*T.k(border_col))
            Line(rectangle=(self.x + bw, self.y + bw,
                             w - bw * 2, h - bw * 2), width=max(1, bw))

            # Available text width (after accent bar + padding)
            tx   = self.x + bar_w + 8
            avail_w = max(10, w - bar_w - 12)

            # Title — vertically centered in top half
            title_lbl = CoreLabel(
                text=info.title, font_size=13,
                text_size=(avail_w, None),
                color=T.k(info.color))
            title_lbl.refresh()
            tw, th = title_lbl.texture.size
            ty = self.y + h // 2 + 2
            Color(1, 1, 1, 1)
            Rectangle(texture=title_lbl.texture,
                      pos=(tx, ty),
                      size=(min(tw, avail_w), th))

            # Description — lower portion, clamped to available width
            desc_text = info.desc.split("\n")[0]
            desc_lbl = CoreLabel(
                text=desc_text, font_size=10,
                text_size=(avail_w, None),
                color=T.k(T.TEXT_DIM))
            desc_lbl.refresh()
            dw, dh = desc_lbl.texture.size
            dy = self.y + 4
            Color(1, 1, 1, 1)
            Rectangle(texture=desc_lbl.texture,
                      pos=(tx, dy),
                      size=(min(dw, avail_w), dh))


# ────────────────────────────────────────────────────────────────────────────
# EXHAUSTION WIDGET
# ────────────────────────────────────────────────────────────────────────────

class ExhaustionWidget(Widget):
    """
    6 clickable pips showing exhaustion level (0-6).
    Tap a pip to set exhaustion to that level; tap filled pip to clear to one below.
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
        w, h   = self.width, self.height
        n      = 6
        pad    = 4
        pip_w  = (w - pad * (n + 1)) / n
        pip_h  = h - pad * 2

        with self.canvas:
            for i in range(n):
                x = self.x + pad + i * (pip_w + pad)
                y = self.y + pad
                filled = i < self.level

                # Pip background
                Color(*T.k(T.BLOOD if filled else T.BG_INSET))
                Rectangle(pos=(x, y), size=(pip_w, pip_h))

                # Pip border
                Color(*T.k(T.BLOOD if filled else T.BORDER))
                Line(rectangle=(x, y, pip_w, pip_h), width=1)

                # Number label
                lbl = CoreLabel(text=str(i + 1), font_size=9,
                                 color=T.k(T.TEXT_BRIGHT if filled else T.TEXT_DIM))
                lbl.refresh()
                tx = x + (pip_w - lbl.texture.width) / 2
                ty = y + (pip_h - lbl.texture.height) / 2
                Color(1, 1, 1, 1)
                Rectangle(texture=lbl.texture, pos=(tx, ty), size=lbl.texture.size)

    def on_touch_down(self, touch):
        if not self.collide_point(*touch.pos):
            return False
        w, h  = self.width, self.height
        n     = 6
        pad   = 4
        pip_w = (w - pad * (n + 1)) / n
        # Determine which pip was tapped
        rel_x = touch.x - self.x
        for i in range(n):
            pip_x = pad + i * (pip_w + pad)
            if pip_x <= rel_x <= pip_x + pip_w:
                new_level = i + 1
                if self.level == new_level:
                    new_level = i  # Tap same pip to decrease
                self.level = int(clamp(new_level, 0, 6))
                if self._on_change:
                    self._on_change(self.level)
                return True
        return False
