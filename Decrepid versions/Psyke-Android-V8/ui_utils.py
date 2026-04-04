"""
Shared UI building blocks for FSM-Android.
Provides FSM-V4.3-style bordered cards, accent cards, dividers, list items
using correct Kivy layout patterns (no MDCard orientation anti-patterns).
"""
from __future__ import annotations

import re as _re
from kivy.clock import Clock
from kivy.core.text import Label as CoreLabel
from kivy.graphics import Color, Ellipse, Line, Rectangle, RoundedRectangle, ScissorPush, ScissorPop
from kivy.metrics import dp, sp
from kivy.properties import BooleanProperty, ListProperty, NumericProperty, StringProperty
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

    def __init__(self, title: str, color_hex: str = T.BORDER, **kwargs):
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
        self._title_lbl = MDLabel(
            text=title, bold=True,
            theme_text_color="Custom", text_color=T.k(color_hex),
            font_style="Caption",
            size_hint_y=None, height=dp(20))
        self.add_widget(self._title_lbl)

    def _upd(self, *_):
        self._bd.pos  = self.pos
        self._bd.size = self.size
        self._bg.pos  = (self.x + 1, self.y + 1)
        self._bg.size = (max(0, self.width - 2), max(0, self.height - 2))

    def set_title(self, title: str, color_hex: str = None):
        """Update the title text and optionally redraw with a new color."""
        self._title_lbl.text = title
        if color_hex and color_hex != self._ch:
            self._ch = color_hex
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
# PickerButton
# A bordered selector-style button (looks like a dropdown, not an action button).
# ────────────────────────────────────────────────────────────────────────────

class PickerButton(BoxLayout):
    """
    Dropdown-style picker button with colored border + dark background.
    Visually distinct from MDRaisedButton action buttons.
    Calls on_press(self) when tapped so MDDropdownMenu can use it as caller.
    """

    def __init__(self, text: str, color_hex: str, on_press, **kwargs):
        kwargs.setdefault("size_hint_y", None)
        kwargs.setdefault("height", dp(48))
        kwargs.setdefault("orientation", "horizontal")
        super().__init__(**kwargs)
        self._on_press = on_press
        with self.canvas.before:
            Color(*T.k(color_hex, 0.30))
            self._bd = RoundedRectangle(radius=[dp(4)])
            Color(*T.k(T.BG_INSET))
            self._bg = RoundedRectangle(radius=[dp(3)])
        self.bind(pos=self._upd, size=self._upd)

        inner = MDBoxLayout(padding=[dp(12), 0, dp(10), 0], spacing=dp(4))
        self._lbl = MDLabel(
            text=text, bold=True,
            theme_text_color="Custom", text_color=T.k(color_hex),
            font_style="Button", halign="left")
        self._arrow = MDLabel(
            text="v",
            theme_text_color="Custom", text_color=T.k(color_hex, 0.55),
            font_style="Caption", halign="right",
            size_hint_x=None, width=dp(20))
        inner.add_widget(self._lbl)
        inner.add_widget(self._arrow)
        self.add_widget(inner)

    def _upd(self, *_):
        self._bd.pos  = self.pos
        self._bd.size = self.size
        self._bg.pos  = (self.x + 1, self.y + 1)
        self._bg.size = (max(0, self.width - 2), max(0, self.height - 2))

    def on_touch_down(self, touch):
        if self.collide_point(*touch.pos):
            self._on_press(self)
            return True
        return super().on_touch_down(touch)


# ────────────────────────────────────────────────────────────────────────────
# PageDot
# Canvas-drawn colored circle for page indicators (avoids Unicode glyph issues).
# ────────────────────────────────────────────────────────────────────────────

class PageDot(Widget):
    """Small canvas-drawn circle for swipe page indicators. Call set_color() to update."""

    def __init__(self, color_hex: str = T.BORDER, **kwargs):
        kwargs.setdefault("size_hint_x", None)
        kwargs.setdefault("width", dp(14))
        super().__init__(**kwargs)
        self._ch = color_hex
        self.bind(pos=self._draw, size=self._draw)
        Clock.schedule_once(self._draw)

    def set_color(self, hex_color: str):
        self._ch = hex_color
        self._draw()

    def _draw(self, *_):
        self.canvas.clear()
        d = min(self.width, self.height) * 0.55
        x = self.x + (self.width  - d) / 2
        y = self.y + (self.height - d) / 2
        with self.canvas:
            Color(*T.k(self._ch))
            Ellipse(pos=(x, y), size=(d, d))


# ────────────────────────────────────────────────────────────────────────────
# DualMaskIndicator
# Swipe-driven page indicator. Both labels share one progress value (0.0–1.0).
#
# At any progress p:
#   left label:  dim on [0 .. p*w],   active on [p*w .. w]   (drains left→right)
#   right label: active on [0 .. p*w], dim on  [p*w .. w]   (fills left→right)
#
# This gives the "continuous liquid wipe across one strip" feel:
# at p=0.5 both labels simultaneously show half dim / half active.
# ────────────────────────────────────────────────────────────────────────────

class DualMaskIndicator(Widget):
    """
    Gesture-driven dual-mask page indicator.

    Set `progress` (0.0–1.0) from a swipe to animate in real time.
    Set `active_color` to the tab's accent color as a Kivy RGBA list.
    """

    progress     = NumericProperty(0.0)
    left_title   = StringProperty("")
    right_title  = StringProperty("")
    active_color = ListProperty([1.0, 1.0, 1.0, 1.0])

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._left_tex  = None
        self._right_tex = None
        self.bind(
            pos=self._redraw,
            size=self._redraw,
            progress=self._redraw,
            left_title=self._bake,
            right_title=self._bake,
            active_color=self._redraw,
        )
        Clock.schedule_once(self._bake, 0)

    def _bake(self, *_):
        for text, attr in (
            (self.left_title,  "_left_tex"),
            (self.right_title, "_right_tex"),
        ):
            lbl = CoreLabel(text=text, font_size=sp(13), bold=True)
            lbl.refresh()
            setattr(self, attr, lbl.texture)
        self._redraw()

    def _redraw(self, *_):
        self.canvas.clear()
        if not self._left_tex or not self._right_tex or self.width <= 1 or self.height <= 1:
            return

        p  = min(1.0, max(0.0, float(self.progress)))
        x  = int(self.x)
        y  = int(self.y)
        w  = int(self.width)
        h  = int(self.height)

        dot_r   = int(dp(4))
        dot_d   = dot_r * 2
        gap     = int(dp(8))    # travel range from each side of the centre gutter
        lbl_gap = int(dp(6))    # space between dot edge and label edge

        cx = x + w // 2
        cy = y + h // 2

        dot_start_x = cx - gap - dot_d
        dot_end_x   = cx + gap
        dy  = cy - dot_r

        lt  = self._left_tex
        rt  = self._right_tex

        lx  = dot_start_x - lbl_gap - lt.width
        rx  = dot_end_x + dot_d + lbl_gap
        lty = y + (h - lt.height) // 2
        rty = y + (h - rt.height) // 2

        lw  = int(lt.width)
        rw  = int(rt.width)

        dim = T.k(T.TEXT_DIM, 0.65)
        ac  = self.active_color

        with self.canvas:
            # 0. Subtle tinted background strip
            Color(*ac[:3], 0.10)
            Rectangle(pos=(x, y), size=(w, h))

            # 1. Full dim base — labels only
            Color(*dim)
            Rectangle(texture=lt, pos=(lx, lty), size=lt.size)
            Rectangle(texture=rt, pos=(rx, rty), size=rt.size)

            # 2. Left label — active on RIGHT portion: [p*lw .. lw]
            la_x = int(round(lx + p * lw))
            la_w = int(round((lx + lw) - la_x))
            if la_w > 0:
                ScissorPush(x=la_x, y=y, width=la_w, height=h)
                Color(*ac)
                Rectangle(texture=lt, pos=(lx, lty), size=lt.size)
                ScissorPop()

            # 3. Right label — active on LEFT portion: [0 .. p*rw]
            ra_w = int(round(p * rw))
            if ra_w > 0:
                ScissorPush(x=rx, y=y, width=ra_w, height=h)
                Color(*ac)
                Rectangle(texture=rt, pos=(rx, rty), size=rt.size)
                ScissorPop()

            # 4. Single travelling dot — independent from the text masks.
            dot_x = dot_start_x + (dot_end_x - dot_start_x) * p
            glow_pad = dp(2)
            Color(*ac[:3], 0.18)
            Ellipse(
                pos=(dot_x - glow_pad, dy - glow_pad),
                size=(dot_d + glow_pad * 2, dot_d + glow_pad * 2),
            )
            Color(*ac)
            Ellipse(pos=(dot_x, dy), size=(dot_d, dot_d))


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

        hdr = BoxLayout(orientation="horizontal",
                        size_hint_y=None, height=dp(42))
        with hdr.canvas.before:
            Color(*T.k(hdr_fill, header_fill_alpha))
            self._hdr_bg  = Rectangle()
            Color(*T.k(accent_hex))
            self._hdr_bar = Rectangle()
        hdr.bind(pos=self._upd_hdr, size=self._upd_hdr)

        self._toggle_lbl = MDLabel(
            text=("v  " if start_open else ">  ") + title,
            theme_text_color="Custom",
            text_color=T.k(accent_hex),
            font_style="Button",
            bold=True,
            padding=[dp(12), 0])
        hdr.add_widget(self._toggle_lbl)
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
            self._toggle_lbl.text = ">  " + self._title

    # ── Toggle ────────────────────────────────────────────────────────────

    def _on_header_touch(self, widget, touch):
        if widget.collide_point(*touch.pos):
            self._open = not self._open
            self._toggle_lbl.text = (
                ("v  " if self._open else ">  ") + self._title)
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
