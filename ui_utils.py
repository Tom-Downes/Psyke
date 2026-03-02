"""
Shared UI building blocks for FSM-Android.
Provides FSM-V4.3-style bordered cards, accent cards, dividers, list items
using correct Kivy layout patterns (no MDCard orientation anti-patterns).
"""
from __future__ import annotations

from kivy.graphics import Color, Line, Rectangle, RoundedRectangle
from kivy.metrics import dp
from kivy.properties import BooleanProperty, ListProperty, StringProperty
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.widget import Widget

from kivymd.uix.boxlayout import MDBoxLayout
from kivymd.uix.button import MDFlatButton, MDIconButton
from kivymd.uix.label import MDLabel

import theme as T


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
            Color(*T.k(T.BG_INSET))
            self._bg = Rectangle()
            Color(*T.k(accent_hex))
            self._bar = Rectangle()
        self.bind(pos=self._upd, size=self._upd)

    def _upd(self, *_):
        self._bg.pos  = self.pos
        self._bg.size = self.size
        self._bar.pos  = (self.x, self.y)
        self._bar.size = (dp(4), self.height)

    def set_accent(self, hex_color: str):
        self._ah = hex_color
        self.canvas.before.clear()
        with self.canvas.before:
            Color(*T.k(T.BG_INSET))
            self._bg = Rectangle()
            Color(*T.k(hex_color))
            self._bar = Rectangle()
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
            # Store Color instruction so we can update it cheaply
            self._bg_color = Color(*T.k(T.BG_INSET))
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
        self._persist         = persist
        self._bg_color.rgba   = T.k(T.BG_HOVER if selected else T.BG_INSET)
        self._upd()

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
            self._bg_color.rgba = T.k(T.BG_INSET)
        return super().on_touch_up(touch)


# ────────────────────────────────────────────────────────────────────────────
# ExpandableSection
# Replaces MDExpansionPanel (version-sensitive API).
# Toggle button shows/hides a content widget by setting its height to 0.
# ────────────────────────────────────────────────────────────────────────────

class ExpandableSection(MDBoxLayout):
    """
    Collapsible section with a toggle button row.
    Content is an MDBoxLayout(adaptive_height=True) that gets height=0 when collapsed.
    """

    def __init__(self, title: str, accent_hex: str = T.BORDER,
                 start_open: bool = False, **kwargs):
        kwargs.setdefault("orientation", "vertical")
        kwargs.setdefault("adaptive_height", True)
        super().__init__(**kwargs)
        self._open = start_open
        self._accent = accent_hex

        # Toggle header row
        hdr = BoxLayout(orientation="horizontal",
                        size_hint_y=None, height=dp(40))
        with hdr.canvas.before:
            Color(*T.k(T.BG_INSET))
            _r = Rectangle()
            def _upd_hdr(w, _):
                _r.pos = w.pos; _r.size = w.size
            hdr.bind(pos=_upd_hdr, size=_upd_hdr)

        self._toggle_lbl = MDLabel(
            text=("▼ " if start_open else "▶ ") + title,
            theme_text_color="Custom",
            text_color=T.k(accent_hex),
            font_style="Button",
            bold=True)
        hdr.add_widget(self._toggle_lbl)
        hdr.bind(on_touch_down=self._on_header_touch)
        self.add_widget(hdr)

        # Content container
        self._content = MDBoxLayout(
            orientation="vertical",
            adaptive_height=True,
            padding=[dp(8), dp(4), dp(8), dp(8)],
            spacing=dp(4))
        if not start_open:
            self._content.height   = 0
            self._content.size_hint_y = None
            self._content.opacity = 0
        self.add_widget(self._content)

    def add_content(self, widget):
        self._content.add_widget(widget)

    def _on_header_touch(self, widget, touch):
        if widget.collide_point(*touch.pos):
            self._open = not self._open
            prefix = "▼ " if self._open else "▶ "
            title = self._toggle_lbl.text[2:]
            self._toggle_lbl.text = prefix + title
            if self._open:
                self._content.size_hint_y = None
                self._content.adaptive_height = True
                self._content.opacity = 1
            else:
                self._content.size_hint_y = None
                self._content.height     = 0
                self._content.opacity    = 0
            return True
        return False
