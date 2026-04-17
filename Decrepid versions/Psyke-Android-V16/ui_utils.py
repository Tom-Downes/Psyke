"""
Shared UI building blocks for FSM-Android.
Provides FSM-V4.3-style bordered cards, accent cards, dividers, list items
using correct Kivy layout patterns (no MDCard orientation anti-patterns).
"""
from __future__ import annotations

import math
import re as _re
from kivy.animation import Animation
from kivy.clock import Clock
from kivy.graphics import (Color, Ellipse, Line, Rectangle, RoundedRectangle,
                           ScissorPush, ScissorPop)
from kivy.core.text import Label as CoreLabel
from kivy.metrics import dp, sp
from kivy.properties import BooleanProperty, ListProperty, NumericProperty, StringProperty
from kivy.uix.anchorlayout import AnchorLayout
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.widget import Widget

from kivymd.uix.boxlayout import MDBoxLayout
from kivymd.uix.button import MDFlatButton, MDIconButton
from kivymd.uix.label import MDLabel
from kivymd.uix.textfield import MDTextField

import theme as T


def themed_field(hint_text: str, accent_hex: str = None, **kwargs) -> MDTextField:
    """MDTextField with white focus border (overrides KivyMD's default purple)."""
    kwargs.setdefault("mode", "rectangle")
    kwargs.setdefault("line_color_normal", T.k(T.BORDER))
    focus_color = T.k(accent_hex) if accent_hex else (1.0, 1.0, 1.0, 0.85)
    field = MDTextField(hint_text=hint_text, **kwargs)
    # Set AFTER creation so it overrides KivyMD's kv bindings / primary_palette purple
    field.line_color_focus      = focus_color
    field.hint_text_color_focus = focus_color
    field.text_color_focus      = T.k(T.TEXT_BRIGHT)
    field.foreground_color      = T.k(T.TEXT_BRIGHT)
    return field


# ────────────────────────────────────────────────────────────────────────────
# BorderCard
# Dark card with a 1px colored border — matches FSM-V4.3's
#   tk.Frame(bg=COLOR, padx=1, pady=1) + inner tk.Frame(bg=BG_CARD) pattern.
# ────────────────────────────────────────────────────────────────────────────

class BorderCard(MDBoxLayout):
    """
    MDBoxLayout with a 1px colored border and dark card background.
    orientation="vertical" by default.
    All children must have size_hint_y=None + height (or adaptive_height=True).
    """

    def __init__(self, border_hex: str = T.BORDER, **kwargs):
        kwargs.setdefault("orientation", "vertical")
        kwargs.setdefault("spacing", dp(6))
        kwargs.setdefault("padding", dp(12))
        kwargs.setdefault("adaptive_height", True)
        super().__init__(**kwargs)
        self._bh = border_hex
        with self.canvas.before:
            # Border rectangle
            Color(*T.k(border_hex))
            self._bd = RoundedRectangle(radius=[dp(6)])
            # Inner background (1px inset)
            Color(*T.k(T.BG_CARD))
            self._bg = RoundedRectangle(radius=[dp(5)])
        self.bind(pos=self._upd, size=self._upd)

    def _upd(self, *_):
        self._bd.pos  = self.pos
        self._bd.size = self.size
        self._bg.pos  = (self.x + 1, self.y + 1)
        self._bg.size = (max(0, self.width - 2), max(0, self.height - 2))


# ────────────────────────────────────────────────────────────────────────────
# AccentCard
# Inset card with a 4dp left color accent bar — matches FSM-V4.3
#   stage effects box and madness detail box style.
# ────────────────────────────────────────────────────────────────────────────

class AccentCard(MDBoxLayout):
    """
    Darker inset card with a left accent bar (like FSM-V4.3 stage effects).
    orientation="vertical" by default. Adds extra left padding for the bar.
    """

    def __init__(self, accent_hex: str = T.GOLD, **kwargs):
        kwargs.setdefault("orientation", "vertical")
        kwargs.setdefault("spacing", dp(4))
        # Extra left padding for the 4dp accent bar
        kwargs.setdefault("padding", [dp(10), dp(8), dp(8), dp(8)])
        kwargs.setdefault("adaptive_height", True)
        super().__init__(**kwargs)
        self._ah = accent_hex
        with self.canvas.before:
            Color(*T.k(accent_hex))
            self._bar = Rectangle()
        self.bind(pos=self._upd, size=self._upd)

    def _upd(self, *_):
        self._bar.pos  = (self.x, self.y)
        self._bar.size = (dp(4), self.height)

    def set_accent(self, hex_color: str):
        self._ah = hex_color
        self.canvas.before.clear()
        with self.canvas.before:
            Color(*T.k(hex_color))
            self._bar = Rectangle()
        self._upd()


# ────────────────────────────────────────────────────────────────────────────
# DescriptionCard
# Bordered card for effect/description popups — full colored border,
# colored bold title at top, adaptive height so text is never cropped.
# ────────────────────────────────────────────────────────────────────────────

class DescriptionCard(MDBoxLayout):
    """
    Inset card with a full rounded border and a colored title label.
    Used for all effect/description popup boxes (wounds, madness, fear).
    No left-bar sliver — uses a full border instead.
    """

    def __init__(self, title: str = "", color_hex: str = T.BORDER, **kwargs):
        kwargs.setdefault("orientation", "vertical")
        kwargs.setdefault("spacing", dp(6))
        kwargs.setdefault("padding", [dp(10), dp(8), dp(10), dp(10)])
        kwargs.setdefault("adaptive_height", True)
        super().__init__(**kwargs)
        self._ch = color_hex
        with self.canvas.before:
            Color(*T.k(color_hex, 0.35))
            self._bd = RoundedRectangle(radius=[dp(5)])
            Color(*T.k(T.BG_INSET))
            self._bg = RoundedRectangle(radius=[dp(4)])
        self.bind(pos=self._upd, size=self._upd)
        self._title_lbl = None
        self.set_title(title)

    def _upd(self, *_):
        self._bd.pos  = self.pos
        self._bd.size = self.size
        self._bg.pos  = (self.x + 1, self.y + 1)
        self._bg.size = (max(0, self.width - 2), max(0, self.height - 2))

    def set_title(self, title: str, color_hex: str = None):
        """Update the title text and optionally redraw with a new color."""
        title = title or ""
        if title:
            if self._title_lbl is None:
                self._title_lbl = MDLabel(
                    text=title, bold=True,
                    theme_text_color="Custom", text_color=T.k(self._ch),
                    font_style="Caption",
                    size_hint_y=None, height=dp(20))
                self.add_widget(self._title_lbl, index=0)
            else:
                self._title_lbl.text = title
        elif self._title_lbl is not None:
            self.remove_widget(self._title_lbl)
            self._title_lbl = None
        if color_hex and color_hex != self._ch:
            self._ch = color_hex
            if self._title_lbl is not None:
                self._title_lbl.text_color = T.k(color_hex)
            self.canvas.before.clear()
            with self.canvas.before:
                Color(*T.k(color_hex, 0.35))
                self._bd = RoundedRectangle(radius=[dp(5)])
                Color(*T.k(T.BG_INSET))
                self._bg = RoundedRectangle(radius=[dp(4)])
            self._upd()


# ────────────────────────────────────────────────────────────────────────────
# Divider
# 1dp horizontal colored line.
# ────────────────────────────────────────────────────────────────────────────

class Divider(Widget):
    """1dp colored horizontal divider."""

    def __init__(self, color_hex: str = T.BORDER, **kwargs):
        kwargs.setdefault("size_hint_y", None)
        kwargs.setdefault("height", dp(1))
        super().__init__(**kwargs)
        with self.canvas:
            Color(*T.k(color_hex))
            self._rect = Rectangle(pos=self.pos, size=self.size)
        self.bind(pos=lambda *_: setattr(self._rect, "pos", self.pos),
                  size=lambda *_: setattr(self._rect, "size", self.size))


# ────────────────────────────────────────────────────────────────────────────
# HopeButton
# Round campfire button with pulsing "USE HOPE" label.
# ────────────────────────────────────────────────────────────────────────────

class HopeButton(MDBoxLayout):
    """
    Round lit-campfire button with an animated 'USE HOPE' label below.
    Only shown when the player has hope and the encounter result is a fail.
    Calls on_use() when tapped.
    """

    def __init__(self, on_use, **kwargs):
        kwargs.setdefault("orientation", "vertical")
        kwargs.setdefault("size_hint", (None, None))
        kwargs.setdefault("size", (dp(72), dp(96)))
        kwargs.setdefault("spacing", dp(4))
        super().__init__(**kwargs)
        self._on_use     = on_use
        self._anim_alpha = 1.0
        self._anim_dir   = -1
        self._anim_token = 0

        self._fire_w = Widget(size_hint=(1, 1))
        self._fire_w.bind(pos=self._redraw, size=self._redraw)

        self._lbl = MDLabel(
            text="USE HOPE",
            theme_text_color="Custom",
            text_color=T.k(T.BLOOD_LT),
            font_style="Caption",
            bold=True,
            halign="center",
            size_hint_y=None,
            height=dp(16))

        self.add_widget(self._fire_w)
        self.add_widget(self._lbl)

        Clock.schedule_once(self._redraw)
        self._start_anim()

    def _start_anim(self):
        self._anim_token += 1
        self._tick(self._anim_token)

    def _tick(self, token):
        if token != self._anim_token:
            return
        self._anim_alpha += self._anim_dir * 0.05
        if self._anim_alpha <= 0.12:
            self._anim_alpha = 0.12
            self._anim_dir   = 1
        elif self._anim_alpha >= 1.0:
            self._anim_alpha = 1.0
            self._anim_dir   = -1
        self._lbl.text_color = T.k(T.BLOOD_LT, self._anim_alpha)
        Clock.schedule_once(lambda dt: self._tick(token), 1 / 20)

    def _redraw(self, *_):
        w   = self._fire_w
        d   = max(min(w.width, w.height) - dp(4), dp(10))
        bw  = dp(3)
        x   = w.x + (w.width  - d) / 2
        y   = w.y + (w.height - d) / 2
        id_ = d - bw * 2
        ix, iy = x + bw, y + bw
        cx  = ix + id_ / 2

        w.canvas.clear()
        with w.canvas:
            Color(*T.k(T.BLOOD_LT))
            Ellipse(pos=(x, y), size=(d, d))
            Color(*T.k(T.BG_INSET))
            Ellipse(pos=(ix, iy), size=(id_, id_))
            # Stone ring shadow + ring
            Color(0.0, 0.0, 0.0, 0.55)
            Ellipse(pos=(cx - id_*0.29, iy + id_*0.03), size=(id_*0.58, id_*0.14))
            Color(*T.k(T.BORDER_LT, 0.92))
            Ellipse(pos=(cx - id_*0.27, iy + id_*0.06), size=(id_*0.54, id_*0.13))
            # Embers
            Color(0.72, 0.24, 0.04, 0.65)
            Ellipse(pos=(cx - id_*0.18, iy + id_*0.08), size=(id_*0.36, id_*0.07))
            # Logs
            Color(0.36, 0.18, 0.06, 1.0)
            Line(points=[ix+id_*0.18, iy+id_*0.14, ix+id_*0.70, iy+id_*0.46], width=dp(2.5))
            Line(points=[ix+id_*0.82, iy+id_*0.14, ix+id_*0.30, iy+id_*0.46], width=dp(2.5))
            # Heat bloom
            Color(0.78, 0.20, 0.04, 0.20)
            Ellipse(pos=(cx - id_*0.30, iy + id_*0.20), size=(id_*0.60, id_*0.66))
            # Flames
            Color(0.87, 0.42, 0.07, 0.90)
            Ellipse(pos=(cx - id_*0.19, iy + id_*0.24), size=(id_*0.38, id_*0.55))
            Color(*T.k(T.GOLD, 0.96))
            Ellipse(pos=(cx - id_*0.12, iy + id_*0.34), size=(id_*0.24, id_*0.40))
            Color(*T.k(T.GOLD_LT, 1.0))
            Ellipse(pos=(cx - id_*0.07, iy + id_*0.46), size=(id_*0.14, id_*0.24))
            Color(1.0, 0.97, 0.76, 0.88)
            Ellipse(pos=(cx - id_*0.025, iy + id_*0.61), size=(id_*0.05, id_*0.08))

    def on_touch_down(self, touch):
        w   = self._fire_w
        d   = max(min(w.width, w.height) - dp(4), dp(10))
        x   = w.x + (w.width  - d) / 2
        y   = w.y + (w.height - d) / 2
        cx, cy, r = x + d / 2, y + d / 2, d / 2
        if ((touch.x - cx) ** 2 + (touch.y - cy) ** 2) <= r ** 2:
            self._on_use()
            return True
        return super().on_touch_down(touch)


# ────────────────────────────────────────────────────────────────────────────
# SectionLabel
# Properly constrained section header label.
# ────────────────────────────────────────────────────────────────────────────

class SectionLabel(MDLabel):
    """Bold section header with guaranteed height constraint."""

    def __init__(self, text: str, color_hex: str = T.TEXT, height_dp: int = 24, **kwargs):
        kwargs.setdefault("size_hint_y", None)
        kwargs.setdefault("height", dp(height_dp))
        kwargs.setdefault("bold", True)
        kwargs.setdefault("font_style", "Button")
        super().__init__(
            text=text,
            theme_text_color="Custom",
            text_color=T.k(color_hex),
            **kwargs
        )


class CaptionLabel(MDLabel):
    """Smaller dim label with guaranteed height constraint."""

    def __init__(self, text: str, color_hex: str = T.TEXT_DIM, height_dp: int = 20, **kwargs):
        kwargs.setdefault("size_hint_y", None)
        kwargs.setdefault("height", dp(height_dp))
        super().__init__(
            text=text,
            theme_text_color="Custom",
            text_color=T.k(color_hex),
            font_style="Caption",
            **kwargs
        )


class MultilineLabel(MDLabel):
    """Multi-line label with adaptive_height=True and proper size_hint_y=None."""

    def __init__(self, text: str = "", color_hex: str = T.TEXT_DIM, **kwargs):
        kwargs.setdefault("size_hint_y", None)
        kwargs.setdefault("adaptive_height", True)
        super().__init__(
            text=text,
            theme_text_color="Custom",
            text_color=T.k(color_hex),
            font_style="Caption",
            **kwargs
        )


# ────────────────────────────────────────────────────────────────────────────
# ListItem
# Touch-target list row (replaces MDList + TwoLineListItem).
# All items have fixed dp(60) height for consistent touch targets.
# ────────────────────────────────────────────────────────────────────────────

class ListItem(BoxLayout):
    """
    A single list row with a colored left indicator and two text lines.
    Touch-friendly (56dp height). Calls on_tap(self) when pressed.

    Supports persistent selection: call set_selected(True, persist=True) to keep
    it highlighted until explicitly deselected. Normal taps show a brief flash.
    """

    def __init__(self, primary: str, secondary: str = "",
                 accent_hex: str = T.BORDER, on_tap=None, **kwargs):
        kwargs.setdefault("size_hint_y", None)
        kwargs.setdefault("height", dp(56))
        kwargs.setdefault("orientation", "horizontal")
        super().__init__(**kwargs)
        self._on_tap     = on_tap
        self._accent_hex = accent_hex
        self._persist    = False

        with self.canvas.before:
            # Transparent by default; BG_HOVER when selected
            self._bg_color = Color(0, 0, 0, 0)
            self._bg       = Rectangle()
            Color(*T.k(accent_hex))
            self._bar      = Rectangle()
        self.bind(pos=self._upd, size=self._upd)

        # 4dp accent bar spacer
        self.add_widget(Widget(size_hint_x=None, width=dp(4)))

        # Text column
        text_col = BoxLayout(orientation="vertical",
                             padding=[dp(8), dp(4), dp(4), dp(4)])
        self._primary_lbl = MDLabel(
            text=primary, bold=True,
            theme_text_color="Custom", text_color=T.k(T.TEXT_BRIGHT),
            font_style="Body2", size_hint_y=None, height=dp(26))
        self._secondary_lbl = MDLabel(
            text=secondary,
            markup=True,
            theme_text_color="Custom", text_color=T.k(T.TEXT_DIM),
            font_style="Caption", size_hint_y=None, height=dp(18))
        text_col.add_widget(self._primary_lbl)
        text_col.add_widget(self._secondary_lbl)
        self.add_widget(text_col)

    def update_text(self, primary: str, secondary: str = ""):
        self._primary_lbl.text   = primary
        self._secondary_lbl.text = secondary

    def set_selected(self, selected: bool, persist: bool = False):
        """Highlight this row. Pass persist=True to keep it highlighted."""
        self._persist       = persist
        self._bg_color.rgba = T.k(T.BG_HOVER) if selected else (0, 0, 0, 0)
        self._upd()

    def flash(self):
        """Directional stroke-loop: accent stroke sweeps clockwise from left bar, becomes outline."""
        if hasattr(self, '_flash_evt') and self._flash_evt:
            self._flash_evt.cancel()
            self._flash_evt = None
        if hasattr(self, '_stroke_col'):
            try:
                self.canvas.after.remove(self._stroke_col)
                self.canvas.after.remove(self._stroke_line)
            except Exception:
                pass
        self._flash_prog = 0.0
        with self.canvas.after:
            self._stroke_col  = Color(*T.k(self._accent_hex), 1.0)
            self._stroke_line = Line(width=dp(2), cap='none', joint='miter')
        self._flash_evt = Clock.schedule_interval(self._tick_stroke, 1 / 60)

    def _tick_stroke(self, dt):
        SPEED = 2.0   # perimeter traversals per second
        HOLD  = 0.25  # seconds to hold full outline
        FADE  = 0.35  # seconds to fade out
        self._flash_prog += dt
        total = 1.0 / SPEED + HOLD + FADE
        if self._flash_prog >= total:
            try:
                self.canvas.after.remove(self._stroke_col)
                self.canvas.after.remove(self._stroke_line)
            except Exception:
                pass
            self._flash_evt.cancel()
            self._flash_evt = None
            return
        draw_prog  = min(self._flash_prog * SPEED, 1.0)
        fade_start = 1.0 / SPEED + HOLD
        alpha = max(0.0, 1.0 - (self._flash_prog - fade_start) / FADE) \
                if self._flash_prog >= fade_start else 1.0
        self._stroke_col.rgba = (*T.k(self._accent_hex)[:3], alpha)
        # Perimeter starting bottom-left, going: up left edge → right top → down right → left bottom
        x  = self.x + dp(1);  y  = self.y + dp(1)
        w  = self.width - dp(2); h = self.height - dp(2)
        segs = [
            ((x,   y),   (x,   y+h), h),   # left side up
            ((x,   y+h), (x+w, y+h), w),   # top right
            ((x+w, y+h), (x+w, y  ), h),   # right side down
            ((x+w, y  ), (x,   y  ), w),   # bottom left
        ]
        dist = draw_prog * 2 * (w + h)
        pts  = [x, y]
        rem  = dist
        for (x0, y0), (x1, y1), seg_len in segs:
            if rem <= 0:
                break
            if rem >= seg_len:
                pts += [x1, y1]
                rem -= seg_len
            else:
                t = rem / seg_len
                pts += [x0 + t * (x1 - x0), y0 + t * (y1 - y0)]
                break
        self._stroke_line.points = pts

    def _upd(self, *_):
        self._bg.pos   = self.pos
        self._bg.size  = self.size
        self._bar.pos  = (self.x, self.y)
        self._bar.size = (dp(4), self.height)

    def on_touch_down(self, touch):
        if self.collide_point(*touch.pos):
            self._persist       = False       # reset: callback will re-set if needed
            self._bg_color.rgba = T.k(T.BG_HOVER)
            if self._on_tap:
                self._on_tap(self)
            return True
        return super().on_touch_down(touch)

    def on_touch_up(self, touch):
        if self.collide_point(*touch.pos) and not self._persist:
            self._bg_color.rgba = (0, 0, 0, 0)
        return super().on_touch_up(touch)


# ────────────────────────────────────────────────────────────────────────────
# FillSwipeTitle
# Renders text as two overlapping layers: dim-white base + colour fill that
# sweeps left-to-right as fill_t goes 0 → 1.  Used by ExpandingEffectCard.
# ────────────────────────────────────────────────────────────────────────────

class FillSwipeTitle(Widget):
    """Left-to-right colour fill over text driven by fill_t (0 → 1)."""
    text      = StringProperty("")
    fill_t    = NumericProperty(0.0)
    fill_rgba = ListProperty(list(T.k(T.PURPLE)))

    def __init__(self, **kwargs):
        kwargs.setdefault("size_hint_y", None)
        kwargs.setdefault("height", dp(24))
        super().__init__(**kwargs)
        self._base_label  = None
        self._fill_label  = None
        self._text_width  = 0
        self._text_height = 0

        with self.canvas:
            Color(1, 1, 1, 1)
            self._base_rect = Rectangle()
            Color(1, 1, 1, 1)
            self._fill_rect = Rectangle()

        self.bind(pos=self._redraw, size=self._redraw,
                  text=self._redraw, fill_t=self._redraw, fill_rgba=self._redraw)
        self._redraw()

    def _redraw(self, *_):
        if not self.text:
            self._base_rect.texture = None
            self._fill_rect.texture = None
            return

        self._base_label = CoreLabel(
            text=self.text, font_size=dp(14), bold=True,
            color=T.k(T.TEXT_BRIGHT),
        )
        self._base_label.refresh()

        self._fill_label = CoreLabel(
            text=self.text, font_size=dp(14), bold=True,
            color=tuple(self.fill_rgba),
        )
        self._fill_label.refresh()

        tex = self._base_label.texture
        self._text_width  = tex.width
        self._text_height = tex.height
        x = self.x
        y = self.y + (self.height - self._text_height) / 2

        fill_w = int(max(0, min(self._text_width, round(self._text_width * self.fill_t))))
        draw_w = min(self._text_width, fill_w + (1 if fill_w > 0 else 0))

        base_w = max(0, self._text_width - fill_w)
        self._base_rect.texture = tex
        self._base_rect.tex_coords = (
            fill_w / max(1, self._text_width), 1,
            1, 1,
            1, 0,
            fill_w / max(1, self._text_width), 0,
        )
        self._base_rect.pos  = (x + fill_w, y)
        self._base_rect.size = (base_w, self._text_height)

        self._fill_rect.texture    = self._fill_label.texture
        self._fill_rect.tex_coords = (
            0, 1,
            draw_w / max(1, self._text_width), 1,
            draw_w / max(1, self._text_width), 0,
            0, 0,
        )
        self._fill_rect.pos  = (x, y)
        self._fill_rect.size = (draw_w, self._text_height)


# ────────────────────────────────────────────────────────────────────────────
# ExpandingEffectCard
# Self-contained expandable row: replaces ListItem + hidden detail MDBoxLayout.
# Tapping animates open/closed with title fill-sweep, subtitle brightening,
# and body-text reveal.  Collapsed height matches ListItem (dp(56)).
# ────────────────────────────────────────────────────────────────────────────

class SwipeFillListItem(MDBoxLayout):
    """Non-expanding card row with a title swipe-fill selection state."""

    accent_rgba = ListProperty(list(T.k(T.GOLD)))

    def __init__(self, primary: str, secondary: str = "",
                 accent_hex: str = T.GOLD, on_tap=None, **kwargs):
        kwargs.setdefault("orientation", "vertical")
        kwargs.setdefault("size_hint_y", None)
        kwargs.setdefault("height", dp(56))
        kwargs.setdefault("padding", [dp(14), dp(6), dp(14), dp(6)])
        super().__init__(**kwargs)
        self._on_tap = on_tap
        self._persist = False
        self._selected = False
        self._flash_evt = None

        with self.canvas.before:
            Color(*T.k(T.BORDER))
            self._outer = RoundedRectangle(radius=[dp(10)])
            self._bg_color = Color(*T.k(T.BG_CARD))
            self._inner = RoundedRectangle(radius=[dp(9)])
            self._accent_color = Color(*T.k(accent_hex))
            self._bar = RoundedRectangle(radius=[dp(9), 0, 0, dp(9)])

        self._text_col = MDBoxLayout(
            orientation="vertical",
            spacing=dp(0),
            size_hint_y=None,
            adaptive_height=True,
        )
        self._title_stage = FillSwipeTitle(fill_rgba=list(T.k(accent_hex)))
        self._subtitle_lbl = MDLabel(
            text=secondary,
            markup=True,
            theme_text_color="Custom",
            text_color=T.k(T.TEXT_DIM),
            font_style="Caption",
            size_hint_y=None,
            adaptive_height=True,
        )
        self._text_col.add_widget(self._title_stage)
        self._text_col.add_widget(self._subtitle_lbl)
        self.add_widget(self._text_col)

        self.bind(pos=self._redraw, size=self._redraw, accent_rgba=self._redraw)
        self.update_text(primary, secondary)

    def update_text(self, primary: str, secondary: str = ""):
        self._title_stage.text = primary
        self._subtitle_lbl.text = secondary

    def set_selected(self, selected: bool, persist: bool = False, animate: bool = True):
        self._persist = persist
        self._selected = selected
        self._bg_color.rgba = T.k(T.BG_HOVER if selected else T.BG_CARD)
        Animation.cancel_all(self._title_stage, "fill_t")
        target_fill = 1.0 if selected else 0.0
        if animate:
            Animation(fill_t=target_fill, duration=0.28, t="out_cubic").start(self._title_stage)
        else:
            self._title_stage.fill_t = target_fill
        self._redraw()

    def flash(self):
        if self._flash_evt:
            self._flash_evt.cancel()
            self._flash_evt = None
        if hasattr(self, "_stroke_col"):
            try:
                self.canvas.after.remove(self._stroke_col)
                self.canvas.after.remove(self._stroke_line)
            except Exception:
                pass
        self._flash_prog = 0.0
        with self.canvas.after:
            self._stroke_col = Color(*self.accent_rgba[:3], 1.0)
            self._stroke_line = Line(width=dp(2), cap="none", joint="miter")
        self._flash_evt = Clock.schedule_interval(self._tick_stroke, 1 / 60)

    def _tick_stroke(self, dt):
        SPEED = 2.0
        HOLD = 0.25
        FADE = 0.35
        self._flash_prog += dt
        total = 1.0 / SPEED + HOLD + FADE
        if self._flash_prog >= total:
            try:
                self.canvas.after.remove(self._stroke_col)
                self.canvas.after.remove(self._stroke_line)
            except Exception:
                pass
            self._flash_evt.cancel()
            self._flash_evt = None
            return
        draw_prog = min(self._flash_prog * SPEED, 1.0)
        fade_start = 1.0 / SPEED + HOLD
        alpha = (max(0.0, 1.0 - (self._flash_prog - fade_start) / FADE)
                 if self._flash_prog >= fade_start else 1.0)
        self._stroke_col.rgba = (*self.accent_rgba[:3], alpha)
        x = self.x + dp(1)
        y = self.y + dp(1)
        w = self.width - dp(2)
        h = self.height - dp(2)
        segs = [
            ((x, y), (x, y + h), h),
            ((x, y + h), (x + w, y + h), w),
            ((x + w, y + h), (x + w, y), h),
            ((x + w, y), (x, y), w),
        ]
        dist = draw_prog * 2 * (w + h)
        pts = [x, y]
        rem = dist
        for (x0, y0), (x1, y1), seg_len in segs:
            if rem <= 0:
                break
            if rem >= seg_len:
                pts += [x1, y1]
                rem -= seg_len
            else:
                t = rem / seg_len
                pts += [x0 + t * (x1 - x0), y0 + t * (y1 - y0)]
                break
        self._stroke_line.points = pts

    def _redraw(self, *_):
        radius = dp(10)
        accent_w = dp(6)
        self._accent_color.rgba = list(self.accent_rgba)
        self._title_stage.fill_rgba = list(self.accent_rgba)

        self._outer.pos = self.pos
        self._outer.size = self.size
        self._outer.radius = [radius]

        self._inner.pos = (self.x + 1, self.y + 1)
        self._inner.size = (max(0, self.width - 2), max(0, self.height - 2))
        self._inner.radius = [max(0, radius - 1)]

        self._bar.pos = (self.x + 1, self.y + 1)
        self._bar.size = (accent_w, max(0, self.height - 2))
        self._bar.radius = [radius, 0, 0, radius]

    def on_touch_down(self, touch):
        if self.collide_point(*touch.pos):
            if self._on_tap:
                self._on_tap(self)
            return True
        return super().on_touch_down(touch)


class PickerListItem(MDBoxLayout):
    """
    Picker row that uses real labels inside the card and expands to reveal
    effect text inside the same box once a selection has been made.
    """

    title_text = StringProperty("")
    subtitle_text = StringProperty("")
    detail_body = StringProperty("")
    accent_rgba = ListProperty(list(T.k(T.PURPLE)))
    expand_t = NumericProperty(0.0)
    open_state = BooleanProperty(False)
    is_placeholder = BooleanProperty(True)

    def __init__(self, on_tap=None, accent_hex: str = T.PURPLE, **kwargs):
        accent_rgba = kwargs.pop("accent_rgba", list(T.k(accent_hex)))
        kwargs.setdefault("orientation", "vertical")
        kwargs.setdefault("size_hint_y", None)
        kwargs.setdefault("padding", [dp(14), dp(6), dp(14), dp(6)])
        kwargs.setdefault("spacing", dp(2))
        super().__init__(**kwargs)
        self._on_tap = on_tap
        self._base_h = dp(56)
        self._accent_hex = accent_hex
        self._placeholder_evt = None
        self.accent_rgba = accent_rgba

        with self.canvas.before:
            Color(*T.k(T.BORDER))
            self._outer = RoundedRectangle(radius=[dp(10)])
            self._bg_color = Color(*T.k(T.BG_CARD))
            self._inner = RoundedRectangle(radius=[dp(9)])
            self._accent_color = Color(*self.accent_rgba)
            self._bar = RoundedRectangle(radius=[dp(9), 0, 0, dp(9)])

        self.bind(
            pos=self._redraw,
            size=self._redraw,
            accent_rgba=self._redraw,
            expand_t=self._redraw,
            open_state=self._redraw,
        )

        self._header = MDBoxLayout(
            orientation="horizontal",
            size_hint_y=None,
            adaptive_height=True,
            spacing=dp(8),
        )
        self._text_col = MDBoxLayout(
            orientation="vertical",
            spacing=dp(0),
            size_hint_y=None,
            adaptive_height=True,
        )
        self._placeholder_lbl = MDLabel(
            text="",
            bold=True,
            theme_text_color="Custom",
            text_color=T.k(T.TEXT_BRIGHT),
            font_style="Subtitle2",
            size_hint_y=None,
            adaptive_height=True,
        )
        self._placeholder_lbl.bind(
            width=lambda inst, val: setattr(inst, "text_size", (val, None))
        )
        self._title_stage = FillSwipeTitle(fill_rgba=list(self.accent_rgba))
        self._subtitle_lbl = MDLabel(
            text="",
            theme_text_color="Custom",
            text_color=T.k(T.TEXT_DIM),
            font_style="Caption",
            size_hint_y=None,
            adaptive_height=True,
        )
        self._subtitle_lbl.bind(
            width=lambda inst, val: setattr(inst, "text_size", (val, None))
        )
        self._text_col.add_widget(self._placeholder_lbl)
        self._text_col.add_widget(self._title_stage)
        self._text_col.add_widget(self._subtitle_lbl)
        self._header.add_widget(self._text_col)
        arrow_slot = AnchorLayout(
            anchor_x="center",
            anchor_y="center",
            size_hint_x=None,
            width=dp(30),
        )
        self._arrow = HookMorphArrow(
            color_hex=self._accent_hex,
            t=0.0,
            size_hint_x=None,
            width=dp(24),
            size_hint_y=None,
            height=dp(24),
        )
        arrow_slot.add_widget(self._arrow)
        self._header.add_widget(arrow_slot)
        self._header_wrap = AnchorLayout(
            anchor_x="left",
            anchor_y="center",
            size_hint_y=None,
            height=self._base_h - self.padding[1] - self.padding[3],
        )
        self._header_wrap.add_widget(self._header)
        self.add_widget(self._header_wrap)

        self._detail_box = MDBoxLayout(
            orientation="vertical",
            size_hint_y=None,
            opacity=0,
            height=0,
        )
        self._detail_body_lbl = MDLabel(
            text="",
            theme_text_color="Custom",
            text_color=T.k(T.TEXT),
            font_style="Body2",
            size_hint_y=None,
            adaptive_height=True,
        )
        self._detail_body_lbl.bind(
            width=lambda inst, val: setattr(inst, "text_size", (val, None)),
            texture_size=lambda inst, sz: setattr(inst, "height", max(dp(16), sz[1])),
        )
        self._detail_box.add_widget(self._detail_body_lbl)
        self.add_widget(self._detail_box)

        self.bind(
            title_text=lambda *_: self._sync_copy(),
            subtitle_text=lambda *_: self._sync_copy(),
            detail_body=lambda *_: self._sync_copy(),
            accent_rgba=lambda *_: self._sync_copy(),
            is_placeholder=lambda *_: self._sync_copy(),
        )

        self.height = self._base_h
        self._sync_copy()

    def on_touch_down(self, touch):
        if self.collide_point(*touch.pos):
            if self._on_tap:
                self._on_tap(self)
            return True
        return super().on_touch_down(touch)

    def set_open(self, open_state: bool, animate: bool = True):
        if self._placeholder_evt is not None:
            self._placeholder_evt.cancel()
            self._placeholder_evt = None
        Animation.cancel_all(self, "height", "expand_t")
        self.open_state = open_state
        if not animate:
            self.expand_t = 1.0 if open_state else 0.0
            self.height = self._base_h
            self._sync_detail_state()
            if open_state:
                Clock.schedule_once(self._open_after_layout)
            return
        if not open_state:
            Animation(height=self._base_h, expand_t=0.0,
                      duration=0.28, t="out_cubic").start(self)
            return
        avail_w = max(dp(20), self.width - self.padding[0] - self.padding[2])
        self._detail_body_lbl.text_size = (avail_w, None)
        self.height = self._base_h
        self.expand_t = 0.0
        self._sync_detail_state()
        Clock.schedule_once(self._start_open_anim)

    def _start_open_anim(self, dt):
        if not self.open_state:
            return
        target_h = self._target_open_height()
        if target_h <= self._base_h:
            Clock.schedule_once(self._start_open_anim)
            return
        Animation(height=target_h, expand_t=1.0,
                  duration=0.28, t="out_cubic").start(self)

    def _open_after_layout(self, dt):
        if not self.open_state:
            return
        h = self._target_open_height()
        if h <= self._base_h:
            Clock.schedule_once(self._open_after_layout)
            return
        self.height = h
        self._sync_detail_state()

    def _target_open_height(self):
        body_h = max(dp(16), self._detail_body_lbl.height)
        return (
            self.padding[1] + self.padding[3]
            + self._header_wrap.height
            + self.spacing
            + body_h
            + dp(12)
        )

    def _sync_detail_state(self):
        t = self.expand_t
        body_alpha = max(0.0, min(1.0, (t - 0.50) / 0.24))
        self._detail_box.opacity = body_alpha
        self._detail_body_lbl.opacity = body_alpha
        self._detail_box.height = max(0.0, self.height - self._base_h)

        subtitle_mix = max(0.0, min(1.0, (t - 0.18) / 0.24))
        dim = T.k(T.TEXT_DIM)[:3]
        bright = T.k(T.TEXT_BRIGHT)[:3]
        sub_color = tuple(dim[i] + (bright[i] - dim[i]) * subtitle_mix for i in range(3))
        self._subtitle_lbl.text_color = (*sub_color, 1.0)
        self._subtitle_lbl.bold = subtitle_mix > 0.15
        if self.is_placeholder:
            self._placeholder_lbl.opacity = 1.0
            self._placeholder_lbl.height = dp(24)
            self._title_stage.opacity = 0.0
            self._title_stage.height = 0
            self._subtitle_lbl.opacity = 0.0
            self._subtitle_lbl.height = 0
            self._title_stage.fill_t = 0.0
            self._arrow._t = 0.0
        else:
            self._placeholder_lbl.opacity = 0.0
            self._placeholder_lbl.height = 0
            self._title_stage.opacity = 1.0
            self._title_stage.height = dp(24)
            self._subtitle_lbl.opacity = 1.0
            self._subtitle_lbl.height = max(dp(16), self._subtitle_lbl.texture_size[1])
            self._title_stage.fill_t = max(0.0, min(1.0, (t - 0.12) / 0.46))
            self._arrow._t = t

    def _redraw(self, *_):
        self._sync_detail_state()
        radius = dp(10 + 2 * self.expand_t)
        accent_w = dp(6 + 2 * self.expand_t)
        self._bg_color.rgba = T.k(T.BG_HOVER) if self.open_state else T.k(T.BG_CARD)
        self._accent_color.rgba = list(self.accent_rgba)

        self._outer.pos = self.pos
        self._outer.size = self.size
        self._outer.radius = [radius]

        self._inner.pos = (self.x + 1, self.y + 1)
        self._inner.size = (max(0, self.width - 2), max(0, self.height - 2))
        self._inner.radius = [max(0, radius - 1)]

        self._bar.pos = (self.x + 1, self.y + 1)
        self._bar.size = (accent_w, max(0, self.height - 2))
        self._bar.radius = [radius, 0, 0, radius]

    def _sync_copy(self):
        self._placeholder_lbl.text = self.title_text if self.is_placeholder else ""
        self._title_stage.text = "" if self.is_placeholder else self.title_text
        self._title_stage.fill_rgba = list(self.accent_rgba)
        self._subtitle_lbl.text = "" if self.is_placeholder else self.subtitle_text
        self._detail_body_lbl.text = self.detail_body

    def show_placeholder(self, text: str, animate: bool = True):
        if self._placeholder_evt is not None:
            self._placeholder_evt.cancel()
            self._placeholder_evt = None
        if not animate:
            self.title_text = text
            self.subtitle_text = ""
            self.detail_body = ""
            self.is_placeholder = True
            self.set_open(False, animate=False)
            self._sync_detail_state()
            self._redraw()
            return

        def _apply_placeholder(*_):
            self._placeholder_evt = None
            self.title_text = text
            self.subtitle_text = ""
            self.detail_body = ""
            self.is_placeholder = True
            self._sync_copy()
            self._sync_detail_state()
            self._redraw()

        if self.open_state:
            self.set_open(False, animate=True)
            self._placeholder_evt = Clock.schedule_once(_apply_placeholder, 0.30)
        else:
            _apply_placeholder()


class ExpandingEffectCard(MDBoxLayout):
    """
    One widget per entry — animated title fill + expanding detail on tap.
    Drop-in replacement for ListItem + a sibling hidden detail panel.
    """
    title_text    = StringProperty("")
    subtitle_text = StringProperty("")
    detail_body   = StringProperty("")
    accent_rgba   = ListProperty(list(T.k(T.PURPLE)))
    expand_t      = NumericProperty(0.0)
    open_state    = BooleanProperty(False)

    def __init__(self, on_tap=None, **kwargs):
        kwargs.setdefault("orientation", "vertical")
        kwargs.setdefault("size_hint_y", None)
        kwargs.setdefault("padding", [dp(14), dp(6), dp(14), dp(6)])
        kwargs.setdefault("spacing", dp(2))
        super().__init__(**kwargs)
        self._on_tap    = on_tap
        self._base_h    = dp(56)
        self._flash_evt = None

        with self.canvas.before:
            Color(*T.k(T.BORDER))
            self._outer        = RoundedRectangle(radius=[dp(10)])
            self._bg_color     = Color(*T.k(T.BG_CARD))
            self._inner        = RoundedRectangle(radius=[dp(9)])
            self._accent_color = Color(*self.accent_rgba)
            self._bar          = RoundedRectangle(radius=[dp(9), 0, 0, dp(9)])

        self.bind(
            pos=self._redraw, size=self._redraw,
            accent_rgba=self._redraw, expand_t=self._redraw, open_state=self._redraw,
        )

        # ── Header: FillSwipeTitle + subtitle label ────────────────────────
        self._header = MDBoxLayout(
            orientation="horizontal",
            size_hint_y=None,
            adaptive_height=True,
        )
        self._text_col = MDBoxLayout(
            orientation="vertical", spacing=dp(0),
            size_hint_y=None, adaptive_height=True,
        )
        self._title_stage  = FillSwipeTitle()
        self._subtitle_lbl = MDLabel(
            text="",
            theme_text_color="Custom",
            text_color=T.k(T.TEXT_DIM),
            font_style="Caption",
            size_hint_y=None,
            adaptive_height=True,
        )
        self._text_col.add_widget(self._title_stage)
        self._text_col.add_widget(self._subtitle_lbl)
        self._header.add_widget(self._text_col)
        self.add_widget(self._header)

        # ── Detail body — hidden (height=0, opacity=0) until expanded ─────
        self._detail_box = MDBoxLayout(
            orientation="vertical",
            size_hint_y=None,
            opacity=0,
            height=0,
        )
        self._detail_body_lbl = MDLabel(
            text="",
            theme_text_color="Custom",
            text_color=T.k(T.TEXT),
            font_style="Body2",
            size_hint_y=None,
            adaptive_height=True,
        )
        self._detail_body_lbl.bind(
            width=lambda inst, val: setattr(inst, "text_size", (val, None))
        )
        self._detail_box.add_widget(self._detail_body_lbl)
        self.add_widget(self._detail_box)

        self.bind(
            title_text=lambda *_: self._sync_copy(),
            subtitle_text=lambda *_: self._sync_copy(),
            detail_body=lambda *_: self._sync_copy(),
            accent_rgba=lambda *_: setattr(
                self._title_stage, "fill_rgba", list(self.accent_rgba)),
        )

        self.height = self._base_h
        self._sync_copy()

    # ── Touch ─────────────────────────────────────────────────────────────

    def on_touch_down(self, touch):
        if self.collide_point(*touch.pos):
            if self._on_tap:
                self._on_tap(self)
            return True
        return super().on_touch_down(touch)

    # ── Flash — same clockwise stroke sweep as ListItem ───────────────────

    def flash(self):
        if self._flash_evt:
            self._flash_evt.cancel()
            self._flash_evt = None
        if hasattr(self, "_stroke_col"):
            try:
                self.canvas.after.remove(self._stroke_col)
                self.canvas.after.remove(self._stroke_line)
            except Exception:
                pass
        self._flash_prog = 0.0
        with self.canvas.after:
            self._stroke_col  = Color(*self.accent_rgba[:3], 1.0)
            self._stroke_line = Line(width=dp(2), cap="none", joint="miter")
        self._flash_evt = Clock.schedule_interval(self._tick_stroke, 1 / 60)

    def _tick_stroke(self, dt):
        SPEED = 2.0
        HOLD  = 0.25
        FADE  = 0.35
        self._flash_prog += dt
        total = 1.0 / SPEED + HOLD + FADE
        if self._flash_prog >= total:
            try:
                self.canvas.after.remove(self._stroke_col)
                self.canvas.after.remove(self._stroke_line)
            except Exception:
                pass
            self._flash_evt.cancel()
            self._flash_evt = None
            return
        draw_prog  = min(self._flash_prog * SPEED, 1.0)
        fade_start = 1.0 / SPEED + HOLD
        alpha = (max(0.0, 1.0 - (self._flash_prog - fade_start) / FADE)
                 if self._flash_prog >= fade_start else 1.0)
        self._stroke_col.rgba = (*self.accent_rgba[:3], alpha)
        x = self.x + dp(1);  y = self.y + dp(1)
        w = self.width - dp(2);  h = self.height - dp(2)
        segs = [
            ((x,       y),       (x,       y + h), h),
            ((x,       y + h),   (x + w,   y + h), w),
            ((x + w,   y + h),   (x + w,   y),     h),
            ((x + w,   y),       (x,       y),     w),
        ]
        dist = draw_prog * 2 * (w + h)
        pts  = [x, y]
        rem  = dist
        for (x0, y0), (x1, y1), seg_len in segs:
            if rem <= 0:
                break
            if rem >= seg_len:
                pts += [x1, y1]
                rem -= seg_len
            else:
                t = rem / seg_len
                pts += [x0 + t * (x1 - x0), y0 + t * (y1 - y0)]
                break
        self._stroke_line.points = pts

    # ── Open / close ──────────────────────────────────────────────────────

    def set_open(self, open_state: bool, animate: bool = True):
        Animation.cancel_all(self, "height", "expand_t")
        self.open_state = open_state
        if not animate:
            self.expand_t = 1.0 if open_state else 0.0
            self.height   = self._base_h
            self._sync_detail_state()
            if open_state:
                # Height correction deferred until labels have a layout pass
                Clock.schedule_once(self._open_after_layout)
            return
        if not open_state:
            Animation(height=self._base_h, expand_t=0.0,
                      duration=0.28, t="out_cubic").start(self)
            return
        # Force label to measure against the correct width before animating.
        # Without this, text_size may be (0, None) on first open (label was
        # hidden in a height=0 box), producing a wrong target height.
        avail_w = max(dp(20), self.width - self.padding[0] - self.padding[2])
        self._detail_body_lbl.text_size = (avail_w, None)
        # Reset to collapsed so re-opens don't overflow while height shrinks
        self.height   = self._base_h
        self.expand_t = 0.0
        self._sync_detail_state()
        # Defer one frame so adaptive_height can update _detail_body_lbl.height
        Clock.schedule_once(self._start_open_anim)

    def _start_open_anim(self, dt):
        if not self.open_state:
            return
        target_h = self._target_open_height()
        if target_h <= self._base_h:
            # Label still measuring — retry next frame
            Clock.schedule_once(self._start_open_anim)
            return
        Animation(height=target_h, expand_t=1.0,
                  duration=0.28, t="out_cubic").start(self)

    def _open_after_layout(self, dt):
        if not self.open_state:
            return
        h = self._target_open_height()
        if h <= self._base_h:
            Clock.schedule_once(self._open_after_layout)
            return
        self.height = h
        self._sync_detail_state()

    def _target_open_height(self):
        body_h = max(dp(16), self._detail_body_lbl.height)
        return (
            self.padding[1] + self.padding[3]
            + self._header.height
            + self.spacing
            + body_h
            + dp(10)
        )

    # ── State sync ────────────────────────────────────────────────────────

    def _sync_detail_state(self):
        t = self.expand_t
        body_alpha = max(0.0, min(1.0, (t - 0.50) / 0.24))
        self._detail_box.opacity      = body_alpha
        self._detail_body_lbl.opacity = body_alpha
        extra_h = max(0.0, self.height - self._base_h)
        self._detail_box.height = extra_h

        subtitle_mix = max(0.0, min(1.0, (t - 0.18) / 0.24))
        dim    = T.k(T.TEXT_DIM)[:3]
        bright = T.k(T.TEXT_BRIGHT)[:3]
        color  = tuple(dim[i] + (bright[i] - dim[i]) * subtitle_mix for i in range(3))
        self._subtitle_lbl.text_color = (*color, 1.0)
        self._subtitle_lbl.bold       = subtitle_mix > 0.15
        self._title_stage.fill_t      = max(0.0, min(1.0, (t - 0.12) / 0.46))

    def _redraw(self, *_):
        self._sync_detail_state()
        radius   = dp(10 + 2 * self.expand_t)
        accent_w = dp(6 + 2 * self.expand_t)

        self._bg_color.rgba     = T.k(T.BG_HOVER) if self.open_state else T.k(T.BG_CARD)
        self._accent_color.rgba = list(self.accent_rgba)

        self._outer.pos    = self.pos
        self._outer.size   = self.size
        self._outer.radius = [radius]

        self._inner.pos    = (self.x + 1, self.y + 1)
        self._inner.size   = (max(0, self.width - 2), max(0, self.height - 2))
        self._inner.radius = [max(0, radius - 1)]

        self._bar.pos    = (self.x + 1, self.y + 1)
        self._bar.size   = (accent_w, max(0, self.height - 2))
        self._bar.radius = [radius, 0, 0, radius]

    def _sync_copy(self):
        self._title_stage.text      = self.title_text
        self._subtitle_lbl.text     = self.subtitle_text
        self._detail_body_lbl.text  = self.detail_body
        self._title_stage.fill_rgba = list(self.accent_rgba)


# ────────────────────────────────────────────────────────────────────────────
# PickerButton
# A bordered selector-style button (looks like a dropdown, not an action button).
# ────────────────────────────────────────────────────────────────────────────

class NotificationActionButton(BoxLayout):
    """Compact notification action button with accent outline sweep feedback."""

    def __init__(self, text: str, color_hex: str, on_release=None, **kwargs):
        kwargs.setdefault("size_hint_x", None)
        kwargs.setdefault("width", dp(98))
        kwargs.setdefault("size_hint_y", None)
        kwargs.setdefault("height", dp(34))
        kwargs.setdefault("padding", [dp(10), 0, dp(10), 0])
        super().__init__(orientation="horizontal", **kwargs)
        self._on_release = on_release
        self._accent_hex = color_hex
        self._pending_release = False

        with self.canvas.before:
            self._bd_color = Color(*T.k(color_hex, 0.55))
            self._bd = RoundedRectangle(radius=[dp(5)])
            self._bg_color = Color(*T.k(T.BG_INSET))
            self._bg = RoundedRectangle(radius=[dp(4)])
        self.bind(pos=self._upd, size=self._upd)

        self._lbl = MDLabel(
            text=text,
            bold=True,
            theme_text_color="Custom",
            text_color=T.k(color_hex),
            font_style="Button",
            halign="center",
            valign="middle",
        )
        self._lbl.bind(size=lambda inst, *_: setattr(inst, "text_size", inst.size))
        self.add_widget(self._lbl)

    def _upd(self, *_):
        self._bd.pos = self.pos
        self._bd.size = self.size
        self._bg.pos = (self.x + 1, self.y + 1)
        self._bg.size = (max(0, self.width - 2), max(0, self.height - 2))

    def _set_pressed(self, pressed: bool):
        self._bg_color.rgba = T.k(self._accent_hex, 0.12) if pressed else T.k(T.BG_INSET)
        self._bd_color.rgba = T.k(self._accent_hex, 0.9 if pressed else 0.55)

    def play_select_anim(self):
        if hasattr(self, "_flash_evt") and self._flash_evt:
            self._flash_evt.cancel()
            self._flash_evt = None
        if hasattr(self, "_stroke_col"):
            try:
                self.canvas.after.remove(self._stroke_col)
                self.canvas.after.remove(self._stroke_line)
            except Exception:
                pass
        self._flash_prog = 0.0
        with self.canvas.after:
            self._stroke_col = Color(*T.k(self._accent_hex), 1.0)
            self._stroke_line = Line(width=dp(2), cap="none", joint="miter")
        self._flash_evt = Clock.schedule_interval(self._tick_stroke, 1 / 60)

    def _tick_stroke(self, dt):
        speed = 2.25
        hold = 0.16
        fade = 0.28
        self._flash_prog += dt
        total = 1.0 / speed + hold + fade
        if self._flash_prog >= total:
            try:
                self.canvas.after.remove(self._stroke_col)
                self.canvas.after.remove(self._stroke_line)
            except Exception:
                pass
            self._flash_evt.cancel()
            self._flash_evt = None
            return
        draw_prog = min(self._flash_prog * speed, 1.0)
        fade_start = 1.0 / speed + hold
        alpha = max(0.0, 1.0 - (self._flash_prog - fade_start) / fade) \
                if self._flash_prog >= fade_start else 1.0
        self._stroke_col.rgba = (*T.k(self._accent_hex)[:3], alpha)

        x = self.x + dp(1)
        y = self.y + dp(1)
        w = self.width - dp(2)
        h = self.height - dp(2)
        segs = [
            ((x, y), (x, y + h), h),
            ((x, y + h), (x + w, y + h), w),
            ((x + w, y + h), (x + w, y), h),
            ((x + w, y), (x, y), w),
        ]
        dist = draw_prog * 2 * (w + h)
        pts = [x, y]
        rem = dist
        for (x0, y0), (x1, y1), seg_len in segs:
            if rem <= 0:
                break
            if rem >= seg_len:
                pts += [x1, y1]
                rem -= seg_len
            else:
                t = rem / seg_len
                pts += [x0 + t * (x1 - x0), y0 + t * (y1 - y0)]
                break
        self._stroke_line.points = pts

    def _dispatch_release(self, *_):
        self._pending_release = False
        if self._on_release:
            self._on_release(self)

    def on_touch_down(self, touch):
        if self.collide_point(*touch.pos) and not self._pending_release:
            touch.grab(self)
            self._set_pressed(True)
            return True
        return super().on_touch_down(touch)

    def on_touch_move(self, touch):
        if touch.grab_current is self:
            self._set_pressed(self.collide_point(*touch.pos))
            return True
        return super().on_touch_move(touch)

    def on_touch_up(self, touch):
        if touch.grab_current is self:
            touch.ungrab(self)
            inside = self.collide_point(*touch.pos)
            self._set_pressed(False)
            if inside and not self._pending_release:
                self._pending_release = True
                self._dispatch_release()
            return True
        return super().on_touch_up(touch)


class MorphArrow(Widget):
    # ── Collapsed: clean right-pointing →
    # ── Expanded:  L-hook (goes right, bends 90° down) — downward ↪
    #
    # Seven normalised vertices (Kivy: y=0 bottom, y=1 top):
    #   s0–s3  shaft waypoints  (drawn as one round-jointed polyline)
    #   tip    arrowhead apex
    #   a1,a2  arrowhead arm ends

    _t = NumericProperty(0.0)

    _PTS_COLLAPSED = (              # →
        (0.06, 0.50),               # s0  tail — left centre
        (0.30, 0.50),               # s1
        (0.55, 0.50),               # s2
        (0.72, 0.50),               # s3  near-tip
        (0.92, 0.50),               # tip — right centre
        (0.70, 0.73),               # a1  upper arm
        (0.70, 0.27),               # a2  lower arm
    )
    _PTS_EXPANDED = (               # downward ↪  (right then down)
        (0.08, 0.80),               # s0  tail — upper left
        (0.36, 0.80),               # s1  horizontal run
        (0.66, 0.80),               # s2  at corner top-right
        (0.66, 0.50),               # s3  post-corner, mid-descent
        (0.66, 0.12),               # tip — bottom
        (0.40, 0.32),               # a1  left arm
        (0.92, 0.32),               # a2  right arm
    )

    def __init__(self, color_hex: str, t: float = 0.0, **kwargs):
        super().__init__(**kwargs)
        self._color_hex = color_hex
        self._morph_anim = None
        self._t = t
        self.bind(pos=self._draw, size=self._draw, _t=self._draw)
        Clock.schedule_once(self._draw)

    def _interp_pts(self):
        t, u = self._t, 1.0 - self._t
        return [(u * cx + t * ex, u * cy + t * ey)
                for (cx, cy), (ex, ey)
                in zip(self._PTS_COLLAPSED, self._PTS_EXPANDED)]

    def _draw(self, *_):
        self.canvas.clear()
        if not self.width or not self.height:
            return
        pts = self._interp_pts()
        px = [(self.x + nx * self.width, self.y + ny * self.height)
              for nx, ny in pts]
        s0, s1, s2, s3, tip, a1, a2 = px
        with self.canvas:
            Color(*T.k(self._color_hex))
            Line(points=[s0[0], s0[1], s1[0], s1[1],
                         s2[0], s2[1], s3[0], s3[1], tip[0], tip[1]],
                 width=dp(1.8), cap="round", joint="round")
            Line(points=[tip[0], tip[1], a1[0], a1[1]], width=dp(1.8), cap="round")
            Line(points=[tip[0], tip[1], a2[0], a2[1]], width=dp(1.8), cap="round")

    def morph_to(self, target: float, duration: float = 0.26):
        if self._morph_anim:
            self._morph_anim.cancel(self)
        self._morph_anim = Animation(_t=target, duration=duration, t="out_quart")
        self._morph_anim.start(self)


class HookMorphArrow(Widget):
    # Rules-section arrow that keeps a fixed horizontal baseline, then
    # extends into a rounded downward hook.

    _t = NumericProperty(0.0)
    _LEG_SCALE = 0.58
    _RADIUS_RATIO = 0.10
    _ARC_STEPS = 18

    def __init__(self, color_hex: str, t: float = 0.0, **kwargs):
        super().__init__(**kwargs)
        self._color_hex = color_hex
        self._morph_anim = None
        self._t = t
        self.bind(pos=self._draw, size=self._draw, _t=self._draw)
        Clock.schedule_once(self._draw)

    def _build_path_points(self) -> tuple[list[tuple[float, float]], int]:
        leg_len = min(self.width, self.height) * self._LEG_SCALE
        radius = leg_len * self._RADIUS_RATIO
        start_x = self.x + (self.width - leg_len) * 0.5
        baseline_y = self.center_y
        vertical_x = start_x + leg_len
        bend_start_x = vertical_x - radius
        center_y = baseline_y - radius
        tip_y = baseline_y - leg_len
        pts = [
            (start_x, baseline_y),
            (bend_start_x, baseline_y),
        ]
        for i in range(1, self._ARC_STEPS + 1):
            theta = (math.pi / 2.0) * (1.0 - i / self._ARC_STEPS)
            px = bend_start_x + radius * math.cos(theta)
            py = center_y + radius * math.sin(theta)
            pts.append((px, py))
        pts.append((vertical_x, tip_y))
        return pts, 1

    @staticmethod
    def _cumulative_lengths(
        pts: list[tuple[float, float]]
    ) -> list[float]:
        lengths = [0.0]
        total = 0.0
        for (x0, y0), (x1, y1) in zip(pts, pts[1:]):
            total += math.hypot(x1 - x0, y1 - y0)
            lengths.append(total)
        return lengths

    @staticmethod
    def _truncate_path(
        pts: list[tuple[float, float]],
        lengths: list[float],
        target_len: float,
    ) -> tuple[list[tuple[float, float]], tuple[float, float]]:
        if len(pts) < 2:
            return pts[:], (1.0, 0.0)
        out = [pts[0]]
        for i in range(1, len(pts)):
            seg_start = lengths[i - 1]
            seg_end = lengths[i]
            x0, y0 = pts[i - 1]
            x1, y1 = pts[i]
            dx = x1 - x0
            dy = y1 - y0
            seg_len = seg_end - seg_start
            if target_len >= seg_end:
                out.append((x1, y1))
                continue
            if seg_len <= 0:
                return out, (1.0, 0.0)
            seg_t = max(0.0, min(1.0, (target_len - seg_start) / seg_len))
            out.append((x0 + dx * seg_t, y0 + dy * seg_t))
            return out, (dx, dy)
        dx = pts[-1][0] - pts[-2][0]
        dy = pts[-1][1] - pts[-2][1]
        return out, (dx, dy)

    @staticmethod
    def _rotate(vx: float, vy: float, angle: float) -> tuple[float, float]:
        cos_a = math.cos(angle)
        sin_a = math.sin(angle)
        return (vx * cos_a - vy * sin_a, vx * sin_a + vy * cos_a)

    def _draw(self, *_):
        self.canvas.clear()
        if not self.width or not self.height:
            return
        path_pts, bend_idx = self._build_path_points()
        lengths = self._cumulative_lengths(path_pts)
        initial_len = lengths[bend_idx]
        total_len = lengths[-1]
        visible_len = initial_len + (total_len - initial_len) * self._t
        visible_pts, tangent = self._truncate_path(path_pts, lengths, visible_len)
        flat_pts = [coord for pt in visible_pts for coord in pt]
        tip_x, tip_y = visible_pts[-1]
        tan_x, tan_y = tangent
        tan_len = math.hypot(tan_x, tan_y) or 1.0
        dir_x = tan_x / tan_len
        dir_y = tan_y / tan_len
        back_x = -dir_x
        back_y = -dir_y
        stroke_w = dp(2.0)
        precision = 24
        head_len = max(1.0, min(self.width, self.height) * 0.20)
        spread = math.radians(30.0)
        arm1_dx, arm1_dy = self._rotate(back_x, back_y, spread)
        arm2_dx, arm2_dy = self._rotate(back_x, back_y, -spread)
        a1 = (tip_x + arm1_dx * head_len, tip_y + arm1_dy * head_len)
        a2 = (tip_x + arm2_dx * head_len, tip_y + arm2_dy * head_len)
        with self.canvas:
            Color(*T.k(self._color_hex))
            Line(
                points=flat_pts,
                width=stroke_w,
                cap="round",
                joint="round",
                cap_precision=precision,
                joint_precision=precision,
            )
            Line(
                points=[a1[0], a1[1], tip_x, tip_y, a2[0], a2[1]],
                width=stroke_w,
                cap="round",
                joint="round",
                cap_precision=precision,
                joint_precision=precision,
            )

    def morph_to(self, target: float, duration: float = 0.28):
        if self._morph_anim:
            self._morph_anim.cancel(self)
        self._morph_anim = Animation(_t=target, duration=duration, t="in_out_cubic")
        self._morph_anim.start(self)


class MorphPickerCard(MDBoxLayout):
    """
    Modern picker row with current card styling and a morphing hook arrow.
    Exposes a public text property so callers don't need to reach into
    internal label widgets.
    """

    text = StringProperty("")

    def __init__(self, text: str, color_hex: str, on_press, **kwargs):
        kwargs.setdefault("orientation", "horizontal")
        kwargs.setdefault("size_hint_y", None)
        kwargs.setdefault("height", dp(56))
        kwargs.setdefault("padding", [dp(14), 0, dp(12), 0])
        kwargs.setdefault("spacing", dp(8))
        super().__init__(**kwargs)
        self._on_press = on_press
        self._accent_hex = color_hex
        self.text = text

        with self.canvas.before:
            self._bd_color = Color(*T.k(color_hex, 0.40))
            self._bd = RoundedRectangle(radius=[dp(6)])
            self._bg_color = Color(*T.k(T.BG_INSET))
            self._bg = RoundedRectangle(radius=[dp(5)])
        self.bind(pos=self._upd, size=self._upd, text=self._sync_text)

        self._lbl = MDLabel(
            text=text,
            bold=True,
            theme_text_color="Custom",
            text_color=T.k(color_hex),
            font_style="Button",
            halign="left",
            valign="middle",
        )
        self._lbl.bind(size=lambda inst, *_: setattr(inst, "text_size", inst.size))
        self.add_widget(self._lbl)

        arrow_slot = AnchorLayout(
            anchor_x="center",
            anchor_y="center",
            size_hint_x=None,
            width=dp(30),
        )
        self._arrow = HookMorphArrow(
            color_hex=color_hex,
            t=0.0,
            size_hint_x=None,
            width=dp(24),
            size_hint_y=None,
            height=dp(24),
        )
        arrow_slot.add_widget(self._arrow)
        self.add_widget(arrow_slot)

    def _sync_text(self, *_):
        self._lbl.text = self.text

    def _upd(self, *_):
        self._bd.pos = self.pos
        self._bd.size = self.size
        self._bg.pos = (self.x + 1, self.y + 1)
        self._bg.size = (max(0, self.width - 2), max(0, self.height - 2))

    def on_touch_down(self, touch):
        if self.collide_point(*touch.pos):
            if self._on_press:
                self._on_press(self)
            return True
        return super().on_touch_down(touch)

    def play_select_anim(self):
        self._arrow._t = 0.0
        self._arrow.morph_to(1.0)

    def reset_select_anim(self):
        self._arrow.morph_to(0.0)


class PickerButton(MorphPickerCard):
    """Backward-compatible alias for older picker code paths."""




# ────────────────────────────────────────────────────────────────────────────
# _DualFillLabel
# ONE canvas widget containing both page titles.
# Uses GL ScissorPush/ScissorPop (not StencilView) to clip the coloured render.
#
# Layout: [left_container][dot_gap][dot][dot_gap][right_container]
# Both containers have the same fixed pixel width (half the available space).
# Text is scaled to fit its container (clamped between MIN_FS and MAX_FS),
# then centered inside it.
#
# The active band has constant width == container_w and slides linearly from
# the left container to the right container as p goes 0 → 1, so the fill
# travels at a steady rate regardless of how wide each label's text is.
# ────────────────────────────────────────────────────────────────────────────

def _mix_rgba(c0, c1, t: float):
    t = max(0.0, min(1.0, t))
    return tuple(c0[i] + (c1[i] - c0[i]) * t for i in range(4))


class _DualFillLabel(Widget):
    _MAX_FS       = sp(12)
    _MIN_FS       = sp(7)
    _MAX_CTR_W    = int(dp(120))   # absolute cap so containers never grow absurdly wide

    def __init__(self, left_title: str, right_title: str,
                 left_hex: str, right_hex: str, **kwargs):
        kwargs.setdefault("size_hint_y", None)
        kwargs.setdefault("height", dp(18))
        super().__init__(**kwargs)
        self._lt  = left_title
        self._rt  = right_title
        self._lc  = T.k(left_hex)
        self._rc  = T.k(right_hex)
        self._p          = 0.0
        self._tex_l      = None
        self._tex_r      = None
        self._container_w = 0
        self.bind(pos=self._draw, size=self._draw)
        Clock.schedule_once(self._bake)

    def _bake(self, *_):
        """Bake both textures; container_w is driven by text content, not widget width."""
        # First pass: render at max font to measure natural widths
        raw = []
        for title in (self._lt, self._rt):
            cl = CoreLabel(text=title, font_size=self._MAX_FS, bold=True)
            cl.refresh()
            raw.append(cl.texture)

        # Container = widest label + small side padding, capped at absolute max
        natural_w  = max(raw[0].width, raw[1].width)
        container_w = min(natural_w + int(dp(6)), self._MAX_CTR_W)

        # Second pass: scale down only if natural width still exceeds container
        baked = []
        for title, tex in zip((self._lt, self._rt), raw):
            if tex.width > container_w:
                scaled_fs = max(self._MIN_FS,
                                self._MAX_FS * container_w / tex.width)
                cl = CoreLabel(text=title, font_size=scaled_fs, bold=True)
                cl.refresh()
                tex = cl.texture
            baked.append(tex)

        self._tex_l, self._tex_r = baked
        self._container_w = container_w
        self._draw()

    def set_progress(self, p: float):
        self._p = max(0.0, min(1.0, p))
        self._draw()

    def _draw_elements(self, tl, tr, tl_x, tl_y, tr_x, tr_y,
                       dot_x, dot_y, dot_d):
        Rectangle(texture=tl, pos=(tl_x, tl_y), size=tl.size)
        Ellipse(pos=(dot_x, dot_y), size=(dot_d, dot_d))
        Rectangle(texture=tr, pos=(tr_x, tr_y), size=tr.size)

    def _draw_clipped_region(self, region_x, region_y, region_w, region_h,
                             color_rgba, tl, tr, tl_x, tl_y, tr_x, tr_y,
                             dot_x, dot_y, dot_d):
        if region_w <= 0:
            return
        ScissorPush(
            x=int(region_x),
            y=int(region_y),
            width=int(region_w),
            height=int(region_h),
        )
        Color(*color_rgba)
        self._draw_elements(
            tl, tr, tl_x, tl_y, tr_x, tr_y,
            dot_x, dot_y, dot_d
        )
        ScissorPop()

    def _draw(self, *_):
        self.canvas.clear()
        if self.width <= 1 or self.height <= 1:
            return

        container_w = self._container_w
        if not self._tex_l or not self._tex_r or container_w <= 0:
            return

        x = int(self.x)
        y = int(self.y)
        w = int(self.width)
        h = int(self.height)

        dot_r    = int(dp(2.5))
        dot_d    = dot_r * 2
        dot_gap  = int(dp(6))
        text_pad = int(dp(7))

        mid_x = x + w // 2
        mid_y = y + h // 2
        dot_x = mid_x - dot_r
        dot_y = mid_y - dot_r

        # Containers sit adjacent to the dot — width is content-driven, not widget-driven.
        # Left container : right edge flush against dot gap, extends left by container_w
        # Right container: left edge flush against dot gap, extends right by container_w
        tl_container_x = dot_x - dot_gap - text_pad - container_w
        tr_container_x = dot_x + dot_d + dot_gap + text_pad

        tl = self._tex_l
        tr = self._tex_r

        # Inner-edge align: each label's edge nearest the dot is flush with
        # the container's inner boundary, so both sides sit the same pixel
        # distance from the dot regardless of how wide each label's text is.
        tl_x = tl_container_x + (container_w - tl.width)   # right-align in container
        tl_y = y + (h - tl.height) // 2
        tr_x = tr_container_x                               # left-align in container
        tr_y = y + (h - tr.height) // 2

        base_rgba   = T.k(T.TEXT_DIM, 0.55)
        active_rgba = _mix_rgba(self._lc, self._rc, self._p)

        # Constant-width band slides from left container start → right container start.
        # band_w == container_w always, so the fill rate is identical across both labels.
        p      = self._p
        band_x = tl_container_x + (tr_container_x - tl_container_x) * p
        band_w = container_w

        with self.canvas:
            # Base layer — everything dim/gray
            Color(*base_rgba)
            self._draw_elements(
                tl, tr, tl_x, tl_y, tr_x, tr_y,
                dot_x, dot_y, dot_d
            )

            # Active layer — single scissor window that slides across the strip
            self._draw_clipped_region(
                region_x=int(round(band_x)),
                region_y=y,
                region_w=int(round(band_w)),
                region_h=h,
                color_rgba=active_rgba,
                tl=tl, tr=tr,
                tl_x=tl_x, tl_y=tl_y,
                tr_x=tr_x, tr_y=tr_y,
                dot_x=dot_x,
                dot_y=dot_y, dot_d=dot_d
            )


# ────────────────────────────────────────────────────────────────────────────
# SwipePageIndicator
# ────────────────────────────────────────────────────────────────────────────

class SwipePageIndicator(MDBoxLayout):
    progress = NumericProperty(0.0)

    def __init__(self, left_title: str, right_title: str,
                 left_hex: str, right_hex: str | None = None,
                 bg_hex: str | None = None, **kwargs):
        kwargs.setdefault("size_hint_y", None)
        kwargs.setdefault("height", dp(34))
        kwargs.setdefault("spacing", 0)
        kwargs.setdefault("padding", [dp(10), dp(4), dp(10), dp(4)])
        super().__init__(orientation="vertical", **kwargs)
        self._lhex = left_hex
        self._rhex = right_hex or left_hex

        with self.canvas.before:
            Color(*T.k(bg_hex or left_hex, 0.14))
            self._bg = Rectangle()
        self.bind(pos=self._upd_bg, size=self._upd_bg, progress=self._sync)

        page_lbl = MDLabel(
            text="PAGE", bold=True, font_style="Caption",
            halign="center", theme_text_color="Custom",
            text_color=T.k(T.TEXT_DIM), size_hint_y=None, height=dp(10))
        page_lbl.font_size = "10sp"

        self._bar = _DualFillLabel(
            left_title, right_title,
            left_hex=self._lhex, right_hex=self._rhex,
            size_hint_y=None, height=dp(18))

        self.add_widget(page_lbl)
        self.add_widget(self._bar)
        Clock.schedule_once(self._sync)

    def _upd_bg(self, *_):
        self._bg.pos  = self.pos
        self._bg.size = self.size

    def set_progress(self, progress: float):
        self.progress = max(0.0, min(1.0, progress))

    def _sync(self, *_):
        self._bar.set_progress(self.progress)


# ────────────────────────────────────────────────────────────────────────────
# ExpandableSection
# Replaces MDExpansionPanel (version-sensitive API).
# Toggle button shows/hides a content widget by setting its height to 0.
# ────────────────────────────────────────────────────────────────────────────

class ExpandableSection(MDBoxLayout):
    """
    Collapsible rules section.
    Header: BG_INSET bar with accent left-bar and chevron.
    Content: DescriptionCard-style box (accent border + BG_INSET fill).
    Height is driven by _content.minimum_height binding so the parent
    ScrollView always lays out correctly — no adaptive_height toggling.
    """

    def __init__(self, title: str, accent_hex: str = T.BORDER,
                 start_open: bool = False,
                 header_fill_hex: str | None = None,
                 header_fill_alpha: float = 1.0,
                 **kwargs):
        kwargs.setdefault("orientation", "vertical")
        kwargs.setdefault("size_hint_y", None)
        kwargs.setdefault("adaptive_height", True)
        super().__init__(**kwargs)
        self._open   = start_open
        self._accent = accent_hex
        self._title  = title

        # ── Header row ────────────────────────────────────────────────────
        hdr_fill = header_fill_hex or T.BG_INSET

        hdr = BoxLayout(
            orientation="horizontal",
            size_hint_y=None,
            height=dp(42),
            padding=[dp(10), 0, dp(12), 0],
            spacing=dp(8),
        )
        with hdr.canvas.before:
            Color(*T.k(hdr_fill, header_fill_alpha))
            self._hdr_bg  = Rectangle()
            Color(*T.k(accent_hex))
            self._hdr_bar = Rectangle()
        hdr.bind(pos=self._upd_hdr, size=self._upd_hdr)

        self._toggle_lbl = MDLabel(
            text=title,
            theme_text_color="Custom",
            text_color=T.k(accent_hex),
            font_style="Button",
            bold=True,
            size_hint_x=1,
            halign="left",
            padding=[0, 0, 0, 0])
        hdr.add_widget(self._toggle_lbl)

        arrow_slot = AnchorLayout(
            anchor_x="center",
            anchor_y="center",
            size_hint_x=None,
            width=dp(34),
        )
        self._arrow = HookMorphArrow(
            color_hex=accent_hex,
            t=1.0 if start_open else 0.0,
            size_hint_x=None, width=dp(28),
            size_hint_y=None, height=dp(28))
        arrow_slot.add_widget(self._arrow)
        hdr.add_widget(arrow_slot)
        hdr.bind(on_touch_down=self._on_header_touch)
        self.add_widget(hdr)

        # ── Content wrapper — styled box ──────────────────────────────────
        # size_hint_y=None + explicit height driven by minimum_height binding.
        self._box = MDBoxLayout(
            orientation="vertical",
            size_hint_y=None,
            height=0,
            spacing=dp(0))
        with self._box.canvas.before:
            Color(*T.k(accent_hex, 0.30))
            self._bd = RoundedRectangle(radius=[dp(4)])
            Color(*T.k(T.BG_INSET))
            self._bg = RoundedRectangle(radius=[dp(3)])
        self._box.bind(pos=self._upd_box, size=self._upd_box)

        # Inner content MDBoxLayout — its minimum_height drives _box.height
        self._content = MDBoxLayout(
            orientation="vertical",
            size_hint_y=None,
            adaptive_height=True,
            padding=[dp(10), dp(10), dp(10), dp(10)],
            spacing=dp(6))
        self._box.add_widget(self._content)
        self.add_widget(self._box)

        if start_open:
            self._box.height  = self._content.minimum_height
            self._box.opacity = 1
            self._content.bind(minimum_height=self._sync_box_height)
        else:
            self._box.opacity = 0

    # ── Canvas updaters ───────────────────────────────────────────────────

    def _upd_hdr(self, w, *_):
        self._hdr_bg.pos   = w.pos
        self._hdr_bg.size  = w.size
        self._hdr_bar.pos  = w.pos
        self._hdr_bar.size = (dp(3), w.height)

    def _upd_box(self, w, *_):
        self._bd.pos  = w.pos
        self._bd.size = w.size
        self._bg.pos  = (w.x + 1, w.y + 1)
        self._bg.size = (max(0, w.width - 2), max(0, w.height - 2))

    # ── Height sync ───────────────────────────────────────────────────────

    def _sync_box_height(self, instance, value):
        self._box.height = value

    # ── Public API ────────────────────────────────────────────────────────

    def add_content(self, widget):
        self._content.add_widget(widget)

    def close(self):
        """Programmatically collapse the section without user interaction."""
        if self._open:
            self._content.unbind(minimum_height=self._sync_box_height)
            self._box.height  = 0
            self._box.opacity = 0
            self._open = False
            self._arrow.morph_to(0.0)

    # ── Toggle ────────────────────────────────────────────────────────────

    def _on_header_touch(self, widget, touch):
        if widget.collide_point(*touch.pos):
            self._open = not self._open
            self._arrow.morph_to(1.0 if self._open else 0.0)
            if self._open:
                self._box.height  = self._content.minimum_height
                self._box.opacity = 1
                self._content.bind(minimum_height=self._sync_box_height)
            else:
                self._content.unbind(minimum_height=self._sync_box_height)
                self._box.height  = 0
                self._box.opacity = 0
            return True
        return False


# ────────────────────────────────────────────────────────────────────────────
# Rules section renderer
# Parses rules text into styled heading + body labels inside an ExpandableSection.
# ────────────────────────────────────────────────────────────────────────────

def _is_rules_heading(line: str) -> bool:
    """True if every alphabetic character in the line is uppercase."""
    alpha = _re.sub(r'[^a-zA-Z]', '', line.strip())
    return bool(alpha) and alpha == alpha.upper()


def _is_separator(line: str) -> bool:
    """True if the line consists only of box-drawing / dash characters."""
    stripped = line.strip()
    return bool(stripped) and all(c in '─━—-─ ' for c in stripped)


def _is_step_heading(line: str) -> bool:
    """True if the line is a numbered encounter step like '1: Start the Encounter'."""
    return bool(_re.match(r'^\d+[:.]\s*\S', line.strip()))


def _accent_markup(text: str, accent_hex: str) -> str:
    """
    Apply Kivy color markup to key terms in body text:
      • ALL-CAPS single words of 4+ chars  (CONFRONT, AVOID, PASS, FAIL …)
      • Multi-word ALL-CAPS phrases         (FEAR SEVERITY, GAINING FEARS …)
      • Title-Case label: at any line start (Fear Severity:, Short-Term Insanity: …)
    Returns markup-tagged string ready for MDLabel(markup=True).
    """
    col = accent_hex.lstrip('#')

    # ALL-CAPS sequences: multi-word OR single word ≥4 chars
    text = _re.sub(
        r'\b(?:[A-Z]{2,}(?:[ \t]+[A-Z]{2,})+|[A-Z]{4,})\b',
        lambda m: f'[color=#{col}]{m.group(0)}[/color]',
        text,
    )

    # Title-Case label (optionally after "- " or spaces at line start):
    # e.g. "Fear Severity:", "Short-Term Insanity:", "Fear Desensitization:"
    text = _re.sub(
        r'(?m)(^[-\s]*)([A-Z][a-zA-Z\-]+(?:[ \t]+[A-Z][a-zA-Z\-]+)*:)',
        lambda m: m.group(1) + f'[color=#{col}]{m.group(2)}[/color]',
        text,
    )

    return text


def populate_rules_section(section: ExpandableSection, text: str, accent_hex: str):
    """
    Parse rules text and add styled widgets to an ExpandableSection.

    Paragraphs (split by blank lines) whose first line is ALL-CAPS are
    rendered as a coloured heading (accent_hex) followed by dim body text.
    Lines matching 'N: Title' are rendered as underlined yellow step headings.
    Pure separator lines (─────) are rendered as Divider widgets.
    Within body text, ALL-CAPS terms and Title-Case labels are coloured
    via Kivy markup.
    """
    col = accent_hex.lstrip('#')
    blocks = text.split('\n\n')
    for block in blocks:
        block = block.strip()
        if not block:
            continue

        # Separator block → render as a horizontal divider
        raw_lines = block.split('\n')
        if all(_is_separator(ln) or not ln.strip() for ln in raw_lines):
            section.add_content(Divider())
            continue

        lines = [ln for ln in raw_lines if not _is_separator(ln)]
        if not lines:
            continue

        first = lines[0].strip()

        if _is_step_heading(first):
            # Numbered step: underlined yellow label
            section.add_content(MDLabel(
                text=f'[color=#{col}][u]{first}[/u][/color]',
                theme_text_color="Custom",
                text_color=T.k(accent_hex),
                font_style="Subtitle2",
                bold=False,
                markup=True,
                size_hint_y=None,
                adaptive_height=True,
            ))
            body = '\n'.join(lines[1:]).strip()
            if body:
                section.add_content(MultilineLabel(
                    text=_accent_markup(body, accent_hex),
                    color_hex=T.TEXT_DIM,
                    markup=True))
        elif _is_rules_heading(first):
            # ALL-CAPS heading in tab accent colour
            section.add_content(MDLabel(
                text=first,
                theme_text_color="Custom",
                text_color=T.k(accent_hex),
                font_style="Subtitle2",
                bold=True,
                size_hint_y=None,
                adaptive_height=True,
            ))
            body = '\n'.join(lines[1:]).strip()
            if body:
                section.add_content(MultilineLabel(
                    text=_accent_markup(body, accent_hex),
                    color_hex=T.TEXT_DIM,
                    markup=True))
        else:
            section.add_content(MultilineLabel(
                text=_accent_markup('\n'.join(lines), accent_hex),
                color_hex=T.TEXT_DIM,
                markup=True))


# ────────────────────────────────────────────────────────────────────────────
# EventNotificationBanner
# Floating bottom notification overlay. Tap to navigate to the event source.
# ────────────────────────────────────────────────────────────────────────────

class EventNotificationBanner(BoxLayout):
    """
    Overlay notification banner shown at the bottom of the screen.
    Tap to switch to the relevant tab and highlight the changed item.
    Auto-dismisses after 4 seconds.
    """

    def __init__(self, message: str, tab_label: str, color_hex: str, on_tap_cb, **kwargs):
        from kivy.core.window import Window as _Win
        kwargs.setdefault("orientation", "horizontal")
        kwargs.setdefault("size_hint", (1, None))
        kwargs.setdefault("height", dp(60))
        kwargs.setdefault("spacing", 0)
        super().__init__(**kwargs)

        self._on_tap_cb = on_tap_cb
        self._token = None

        # Background + top border line
        with self.canvas.before:
            Color(*T.k(T.BG_CARD))
            self._bg = Rectangle()
            Color(*T.k(T.BORDER_LT, 0.55))
            self._top = Rectangle(size=(0, dp(1)))
        self.bind(pos=self._upd_bg, size=self._upd_bg)

        # Left accent bar
        accent_w = Widget(size_hint_x=None, width=dp(5))
        with accent_w.canvas:
            Color(*T.k(color_hex))
            self._ar = Rectangle()
        accent_w.bind(
            pos=lambda w, _: setattr(self._ar, 'pos', w.pos),
            size=lambda w, _: setattr(self._ar, 'size', w.size))
        self.add_widget(accent_w)

        # Text area
        tbox = MDBoxLayout(orientation="vertical",
                           padding=[dp(10), dp(6), dp(6), dp(6)],
                           spacing=dp(2))
        tab_lbl = MDLabel(
            text=tab_label,
            font_style="Caption", bold=True,
            theme_text_color="Custom", text_color=T.k(color_hex),
            size_hint_y=None, height=dp(18))
        msg_lbl = MDLabel(
            text=message,
            font_style="Body2",
            theme_text_color="Custom", text_color=T.k(T.TEXT),
            size_hint_y=None, height=dp(22))
        tbox.add_widget(tab_lbl)
        tbox.add_widget(msg_lbl)
        self.add_widget(tbox)

        # Arrow indicator
        arrow_lbl = MDLabel(
            text="→",
            font_style="H6", bold=True,
            halign="center",
            theme_text_color="Custom", text_color=T.k(color_hex, 0.7),
            size_hint_x=None, width=dp(36))
        self.add_widget(arrow_lbl)

        # Add to Window at bottom
        self.pos = (0, 0)
        self.width = _Win.width
        _Win.add_widget(self)

        self._token = Clock.schedule_once(self._dismiss, 4.0)

    def _upd_bg(self, *_):
        self._bg.pos   = self.pos
        self._bg.size  = self.size
        self._top.pos  = (self.x, self.y + self.height - dp(1))
        self._top.size = (self.width, dp(1))

    def _dismiss(self, *_):
        from kivy.core.window import Window as _Win
        if self.parent:
            _Win.remove_widget(self)

    def on_touch_down(self, touch):
        if self.collide_point(*touch.pos):
            if self._token:
                self._token.cancel()
                self._token = None
            self._dismiss()
            if self._on_tap_cb:
                self._on_tap_cb()
            return True
        return super().on_touch_down(touch)
