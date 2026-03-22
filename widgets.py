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
from kivy.metrics import dp
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
        # Slower animation so the change is clearly visible on mobile
        self._anim_dur = clamp(0.7 + dist / 100 * 1.3, 0.7, 2.0)
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

            # Threshold marks at 25 / 50 / 75 % — larger, readable on mobile
            for thresh, label_str in ((0.25, "25"), (0.50, "50"), (0.75, "75")):
                tx = int(self.x + w * thresh)
                Color(*T.k(T.BORDER_LT, 0.85))
                Line(points=[tx, self.y, tx, self.y + h], width=dp(1.5),
                     dash_length=4, dash_offset=3)
                tlbl = CoreLabel(text=label_str, font_size=13, bold=True,
                                 color=T.k(T.BORDER_LT, 0.95))
                tlbl.refresh()
                Color(1, 1, 1, 1)
                Rectangle(texture=tlbl.texture,
                          pos=(tx - tlbl.texture.width // 2, self.y + 4),
                          size=tlbl.texture.size)

            # Moving indicator line at the fill edge
            ind_x = self.x + fill_w
            Color(*T.k(T.PURPLE_LT, 0.95))
            Line(points=[ind_x, self.y + 1, ind_x, self.y + h - 1], width=dp(2.5))

            # Percentage label in purple — attached to the indicator
            pct_str = f"{self._display_pct:.0f}%"
            plbl = CoreLabel(text=pct_str, font_size=16, bold=True,
                             color=T.k(T.PURPLE_LT))
            plbl.refresh()
            # Right of indicator when below 75% mark, left when above
            if pct < 0.75:
                px = ind_x + dp(5)
            else:
                px = ind_x - plbl.texture.width - dp(5)
            px = max(self.x + 2, min(px, self.x + w - plbl.texture.width - 2))
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
    Each pip displays its level number (1-6) inside it.
    Tap a pip to set exhaustion to that level; tap filled pip to clear to one below.
    Draws its own 'EXHAUSTION' label above the pips in a large, mobile-readable font.
    """
    level = BoundedNumericProperty(0, min=0, max=6)

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._on_change  = None
        self._pip_info   = []   # list of (x, y, d) per pip — set during _redraw
        self._flash_pip  = 0    # 1-6 = which pip is flashing; 0 = none
        self._flash_hl   = False
        self._flash_phase = 0
        self.bind(pos=self._redraw, size=self._redraw, level=self._redraw)
        Clock.schedule_once(self._redraw)

    def flash_pip(self, pip_number: int):
        """Flash the pip at 1-based pip_number (4 on/off cycles, gold highlight)."""
        if pip_number < 1 or pip_number > 6:
            return
        self._flash_pip   = pip_number
        self._flash_phase = 0
        Clock.schedule_once(self._tick_flash)

    def _tick_flash(self, dt):
        phase = self._flash_phase
        self._flash_phase += 1
        if phase >= 8:          # 4 full on/off cycles
            self._flash_pip = 0
            self._flash_hl  = False
            self._redraw()
            return
        self._flash_hl = (phase % 2 == 0)
        self._redraw()
        Clock.schedule_once(self._tick_flash, 0.15)

    def set_change_callback(self, cb):
        self._on_change = cb

    def _redraw(self, *_):
        self.canvas.clear()
        w, h = self.width, self.height
        if w < 10 or h < 10:
            return
        n = 6

        # Title "EXHAUSTION" — sized like tab button text for visual consistency
        title_lbl = CoreLabel(text="EXHAUSTION", font_size=14, bold=True,
                              color=T.k(T.TEXT_DIM))
        title_lbl.refresh()
        title_h = title_lbl.texture.height + 4

        # Pip area fills remaining height
        pad = int(dp(4))
        pip_area_h = h - title_h - pad
        pip_w = (w - pad * (n + 1)) / n
        pip_d = max(int(dp(16)), min(pip_w, pip_area_h))
        pip_y = self.y + pad + max(0, (pip_area_h - pip_d) / 2)

        self._pip_info = []
        with self.canvas:
            # Title centred above pips
            Color(1, 1, 1, 1)
            Rectangle(
                texture=title_lbl.texture,
                pos=(self.x + (w - title_lbl.texture.width) / 2,
                     self.y + h - title_h + 2),
                size=title_lbl.texture.size)

            for i in range(n):
                x = self.x + pad + i * (pip_d + pad)
                self._pip_info.append((x, pip_y, pip_d))
                filled    = i < self.level
                flashing  = (self._flash_pip == i + 1) and self._flash_hl

                # Filled circle
                Color(*T.k(T.GOLD_LT if flashing else (T.BLOOD if filled else T.BG_INSET)))
                Ellipse(pos=(x, pip_y), size=(pip_d, pip_d))

                # Border ring
                Color(*T.k(T.GOLD_LT if flashing else (T.BLOOD if filled else T.BORDER)))
                Line(ellipse=(x, pip_y, pip_d, pip_d),
                     width=dp(2.5) if flashing else 1.5)

                # Level number inside pip
                num_fs = max(10, int(pip_d * 0.48))
                num_lbl = CoreLabel(
                    text=str(i + 1), font_size=num_fs, bold=True,
                    color=T.k(T.TEXT_BRIGHT if (filled or flashing) else T.TEXT_DIM))
                num_lbl.refresh()
                Color(1, 1, 1, 1)
                Rectangle(
                    texture=num_lbl.texture,
                    pos=(x + (pip_d - num_lbl.texture.width) / 2,
                         pip_y + (pip_d - num_lbl.texture.height) / 2),
                    size=num_lbl.texture.size)

    def on_touch_down(self, touch):
        if not self.collide_point(*touch.pos):
            return False
        for i, (px, py, pd) in enumerate(self._pip_info):
            if px <= touch.x <= px + pd and py <= touch.y <= py + pd:
                new_level = i + 1
                if self.level == new_level:
                    new_level = i  # tap same filled pip → decrease by 1
                self.level = int(clamp(new_level, 0, 6))
                if self._on_change:
                    self._on_change(self.level)
                return True
        return False
