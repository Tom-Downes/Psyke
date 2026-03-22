"""
Sanity, Fear & Madness Tracker — KivyMD Android App  (V2)
Entry point: App class, global layout, header, sanity bar, madness banner.
4-tab layout: Fears / Sanity / Wounds / Spells
Back button cancels active encounters or dismisses dialogs.

Run on desktop: python main.py
Build for Android: buildozer android debug
"""
from __future__ import annotations

import os
import sys

# Use ANGLE (DirectX backend) when no proper OpenGL 2.0+ driver is available
# (e.g. RDP sessions, VMs, missing GPU drivers — "GDI Generic" renderer)
if sys.platform == "win32":
    os.environ.setdefault("KIVY_GL_BACKEND", "glew")
    from gl_preflight import ensure_compatible_opengl
    ensure_compatible_opengl()

from datetime import datetime

from kivy.app import App
from kivy.clock import Clock
from kivy.core.window import Window
from kivy.graphics import Color, Ellipse, Line, Rectangle
from kivy.metrics import dp
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.screenmanager import ScreenManager, Screen, NoTransition
from kivy.uix.scrollview import ScrollView
from kivy.uix.widget import Widget

_EXH_DESC = {
    0: "No Exhaustion",
    1: "Disadvantage: Ability Checks",
    2: "Speed Halved",
    3: "Disadvantage: Attacks & Saves",
    4: "HP Maximum Halved",
    5: "Speed = 0",
    6: "Incapacitated",
}

from kivymd.app import MDApp
from kivymd.uix.boxlayout import MDBoxLayout
from kivymd.uix.button import MDFlatButton, MDRaisedButton
from kivymd.uix.card import MDCard
from kivymd.uix.dialog import MDDialog
from kivymd.uix.label import MDLabel
from kivymd.uix.snackbar import MDSnackbar
from kivymd.uix.textfield import MDTextField

from models import (
    SanityState, FearManager, UndoStack, SaveManager,
    SANITY_BASE, clamp,
    WIS_MIN, WIS_MAX, CON_MIN, CON_MAX
)
from widgets import SanityBar, MadnessBanner, ExhaustionWidget
from tab_fears import FearsTab
from tab_sanity import SanityTab
from tab_wounds import WoundsTab
from tab_spells import SpellsTab
import theme as T

try:
    import build_info as BI
except Exception:
    class _BI:
        APP_VERSION = "unknown"
        BUILD_SHA = "unknown"
    BI = _BI()


# ═══════════════════════════════════════════════════════════════════════════
# SESSION LOG WIDGET
# ═══════════════════════════════════════════════════════════════════════════

class SessionLog(MDBoxLayout):
    """Scrollable session log panel used inside a dialog."""

    def __init__(self, **kwargs):
        super().__init__(orientation="vertical", spacing=dp(4),
                         padding=dp(8), **kwargs)
        self._entries: list[str] = []

        hdr = MDBoxLayout(size_hint_y=None, height=dp(36), spacing=dp(8))
        hdr.add_widget(MDLabel(
            text="SESSION LOG", bold=True,
            theme_text_color="Custom", text_color=T.k(T.BLUE),
            font_style="Button"))
        copy_btn = MDFlatButton(
            text="Copy All", size_hint_x=None, width=dp(80),
            theme_text_color="Custom", text_color=T.k(T.TEXT_DIM),
            on_release=self._copy_all)
        hdr.add_widget(Widget())
        hdr.add_widget(copy_btn)
        self.add_widget(hdr)

        self._log_sv = ScrollView(size_hint=(1, 1), do_scroll_x=False)
        self._log_box = MDBoxLayout(
            orientation="vertical", spacing=dp(2),
            size_hint_y=None, adaptive_height=True, padding=dp(4))
        self._log_sv.add_widget(self._log_box)
        self.add_widget(self._log_sv)

    def add_entry(self, msg: str):
        ts   = datetime.now().strftime("%H:%M")
        full = f"[{ts}] {msg}"
        self._entries.append(full)
        lbl = MDLabel(
            text=full,
            theme_text_color="Custom",
            text_color=self._color_for(msg),
            font_style="Caption",
            size_hint_y=None, adaptive_height=True)
        self._log_box.add_widget(lbl)
        Clock.schedule_once(lambda dt: setattr(self._log_sv, "scroll_y", 0))

    def _color_for(self, msg: str):
        m = msg.upper()
        if "ENCOUNTER" in m: return T.k(T.GOLD)
        if "WOUND" in m:     return T.k(T.BLOOD)
        if "MADNESS" in m or "THRESHOLD" in m: return T.k(T.PURPLE)
        if "RESTORATION" in m: return T.k(T.SILVER)
        if "PASS" in m:      return T.k(T.GREEN)
        if "FAIL" in m:      return T.k(T.RED)
        if "WARNING" in m:   return T.k(T.BLOOD_LT)
        return T.k(T.TEXT_DIM)

    def _copy_all(self, *_):
        from kivy.core.clipboard import Clipboard
        Clipboard.copy("\n".join(self._entries))
        MDSnackbar(
            MDLabel(text="Log copied to clipboard.",
                    theme_text_color="Custom", text_color=(1, 1, 1, 1)),
            md_bg_color=T.k(T.BG_CARD), duration=2
        ).open()


# ═══════════════════════════════════════════════════════════════════════════
# STAT DIALOG
# ═══════════════════════════════════════════════════════════════════════════

class StatDialog:
    """Reusable dialog for editing WIS or CON score."""

    def __init__(self, title: str, current: int, on_confirm):
        self._field = MDTextField(
            hint_text="Score (1–30)",
            text=str(current),
            input_filter="int",
            mode="rectangle",
            line_color_normal=T.k(T.BORDER),
            line_color_focus=T.k(T.GOLD_LT),
            hint_text_color_focus=T.k(T.GOLD_LT),
        )
        self._field.text_color_focus = T.k(T.TEXT_BRIGHT)
        self._field.foreground_color = T.k(T.TEXT_BRIGHT)
        self._dlg = MDDialog(
            title=title,
            type="custom",
            content_cls=self._field,
            buttons=[
                MDFlatButton(text="Cancel", on_release=self._close),
                MDRaisedButton(
                    text="Set",
                    md_bg_color=T.k(T.PURPLE),
                    on_release=lambda *_: self._confirm(on_confirm)),
            ]
        )

    def open(self): self._dlg.open()
    def _close(self, *_): self._dlg.dismiss()

    def _confirm(self, cb):
        try:
            val = int(clamp(int(self._field.text.strip()), 1, 30))
            cb(val)
        except Exception:
            pass
        self._dlg.dismiss()


# ═══════════════════════════════════════════════════════════════════════════
# HEADER CARD
# ═══════════════════════════════════════════════════════════════════════════

class _AdvBtn(BoxLayout):
    """Tappable ADV toggle — sits on canvas above stat chips."""

    def __init__(self, color_hex: str, on_toggle, **kwargs):
        kwargs.setdefault("size_hint_x", None)
        kwargs.setdefault("width", dp(92))
        super().__init__(**kwargs)
        self._active    = False
        self._color     = color_hex
        self._on_toggle = on_toggle
        self._lbl = MDLabel(
            text="ADV",
            font_style="Caption", bold=False,
            theme_text_color="Custom", text_color=T.k(T.TEXT_DIM, 0.45),
            halign="center")
        self.add_widget(self._lbl)

    def on_touch_down(self, touch):
        if self.collide_point(*touch.pos):
            self._active = not self._active
            self._lbl.bold       = self._active
            self._lbl.text_color = (T.k(self._color) if self._active
                                    else T.k(T.TEXT_DIM, 0.45))
            self._on_toggle(self._active)
            return True
        return super().on_touch_down(touch)


class _StatChip(BoxLayout):
    """
    Vertical stat badge for WIS / CON.

    Two-section layout:
      Top  — stat name (Caption) + large score number
      Bot  — modifier centred in a tinted panel

    Tap anywhere to open the edit dialog.
    """

    def __init__(self, label: str, color_hex: str, on_tap, **kwargs):
        kwargs.setdefault("orientation", "vertical")
        kwargs.setdefault("size_hint_x", None)
        kwargs.setdefault("width", dp(92))
        kwargs.setdefault("padding", [dp(4), dp(4), dp(4), dp(4)])
        kwargs.setdefault("spacing", dp(2))
        super().__init__(**kwargs)
        self._color  = color_hex
        self._on_tap = on_tap
        self._bot_h  = dp(20)

        with self.canvas.before:
            Color(*T.k(color_hex, 0.6))
            self._bd = Rectangle()
            Color(*T.k(T.BG_INSET))
            self._bg = Rectangle()
            Color(*T.k(color_hex, 0.13))
            self._bot_bg = Rectangle()
            Color(*T.k(color_hex, 0.5))
            self._sep = Rectangle()
        self.bind(pos=self._upd, size=self._upd)

        # ── Top section ───────────────────────────────────────────────────────
        top = MDBoxLayout(orientation="vertical", spacing=dp(0))

        self._label_lbl = MDLabel(
            text=label,
            font_style="Caption", bold=True,
            theme_text_color="Custom", text_color=T.k(color_hex),
            halign="center", size_hint_y=None, height=dp(14))

        self._score_lbl = MDLabel(
            text="10",
            bold=True, font_size="22sp",
            theme_text_color="Custom", text_color=T.k(color_hex),
            halign="center", size_hint_y=None, height=dp(28))

        top.add_widget(self._label_lbl)
        top.add_widget(self._score_lbl)

        # ── Bottom section — modifier centred ─────────────────────────────────
        bot = MDBoxLayout(
            size_hint_y=None, height=self._bot_h,
            padding=[dp(4), dp(0), dp(4), dp(0)])

        self._mod_lbl = MDLabel(
            text="+0",
            bold=True, font_size="15sp",
            theme_text_color="Custom", text_color=T.k(color_hex),
            halign="center")

        bot.add_widget(self._mod_lbl)

        self.add_widget(top)
        self.add_widget(bot)

    def _upd(self, *_):
        self._bd.pos  = self.pos
        self._bd.size = self.size
        self._bg.pos  = (self.x + 1, self.y + 1)
        self._bg.size = (max(0, self.width - 2), max(0, self.height - 2))
        tint_h = dp(4) + self._bot_h
        self._bot_bg.pos  = (self.x + 1, self.y + 1)
        self._bot_bg.size = (max(0, self.width - 2), max(0, tint_h - 1))
        self._sep.pos  = (self.x + 1, self.y + tint_h)
        self._sep.size = (max(0, self.width - 2), dp(1))

    def update(self, score: int, mod: int):
        self._score_lbl.text = str(score)
        self._mod_lbl.text   = f"{mod:+d}"

    def on_touch_down(self, touch):
        if self.collide_point(*touch.pos):
            self._on_tap()
            return True
        return super().on_touch_down(touch)


class _SanityChip(BoxLayout):
    """Sanity chip: base+WIS=MAX equation, current/max value, and percentage."""

    def __init__(self, **kwargs):
        kwargs.setdefault("orientation", "vertical")
        kwargs.setdefault("size_hint_x", None)
        kwargs.setdefault("width", dp(82))
        kwargs.setdefault("spacing", dp(2))
        kwargs.setdefault("padding", [dp(2), dp(4), dp(2), dp(4)])
        super().__init__(**kwargs)

        with self.canvas.before:
            Color(*T.k(T.PURPLE, 0.7))
            self._bd = Rectangle()
            Color(*T.k(T.BG_CARD))
            self._bg = Rectangle()
        self.bind(pos=self._upd, size=self._upd)

        # Formula row: SANITY_BASE + WIS = MAX
        self._eq_lbl = MDLabel(
            text=f"{SANITY_BASE}+10=20",
            font_style="Caption",
            theme_text_color="Custom", text_color=T.k(T.TEXT_DIM),
            halign="center",
            size_hint_y=None, height=dp(15))
        # Current / Max
        self._value_lbl = MDLabel(
            text="20/20",
            bold=True, font_size="20sp",
            theme_text_color="Custom", text_color=T.k(T.PURPLE_LT),
            halign="center",
            size_hint_y=None, height=dp(26))
        # Percentage in purple
        self._pct_lbl = MDLabel(
            text="100%",
            bold=True, font_size="14sp",
            theme_text_color="Custom", text_color=T.k(T.PURPLE),
            halign="center",
            size_hint_y=None, height=dp(18))
        self.add_widget(self._eq_lbl)
        self.add_widget(self._value_lbl)
        self.add_widget(self._pct_lbl)

    def _upd(self, *_):
        self._bd.pos  = self.pos
        self._bd.size = self.size
        self._bg.pos  = (self.x + 1, self.y + 1)
        self._bg.size = (max(0, self.width - 2), max(0, self.height - 2))

    def update(self, current: int, max_san: int, pct: float,
               _madness_stage=None, wis_score: int = None):
        if wis_score is not None:
            self._eq_lbl.text = f"{SANITY_BASE}+{wis_score}={max_san}"
        self._value_lbl.text = f"{current}/{max_san}"
        self._pct_lbl.text   = f"{pct:.0f}%"


class _HopePortrait(BoxLayout):
    """
    Campfire hope toggle — no image picker, campfire icon only.
    Unlit campfire = no hope; lit campfire = hope active.
    Tap to toggle.
    """

    def __init__(self, on_toggle, on_image_picked=None, **kwargs):  # noqa: on_image_picked unused by design
        kwargs.setdefault("orientation", "vertical")
        kwargs.setdefault("size_hint_x", None)
        kwargs.setdefault("width", dp(56))
        kwargs.setdefault("spacing", dp(2))
        super().__init__(**kwargs)
        self._active    = False
        self._on_toggle = on_toggle

        self._port = Widget(size_hint_y=1)
        self._port.bind(pos=self._redraw, size=self._redraw)
        Clock.schedule_once(self._redraw)

        self._lbl = MDLabel(
            text="HOPE", font_style="Caption", bold=False,
            theme_text_color="Custom", text_color=T.k(T.TEXT_DIM),
            halign="center", size_hint_y=None, height=dp(14))

        self.add_widget(self._port)
        self.add_widget(self._lbl)

    def _accent(self):
        return T.BLOOD_LT if self._active else T.BORDER_LT

    def _redraw(self, *_):
        w = self._port
        d  = max(min(w.width, w.height) - dp(2), dp(10))
        bw = dp(3) if self._active else dp(2)
        x  = w.x + (w.width  - d) / 2
        y  = w.y + (w.height - d) / 2
        c  = self._accent()
        w.canvas.clear()
        with w.canvas:
            # Outer border ring
            Color(*T.k(c))
            Ellipse(pos=(x, y), size=(d, d))
            # Inner dark fill
            id_ = d - bw * 2
            ix, iy = x + bw, y + bw
            Color(*T.k(T.BG_INSET))
            Ellipse(pos=(ix, iy), size=(id_, id_))
            # Campfire icon
            cx = ix + id_ / 2
            if self._active:
                # ── Lit campfire ──────────────────────────────────────────
                # Stone ring drop-shadow
                Color(0.0, 0.0, 0.0, 0.55)
                Ellipse(pos=(cx - id_*0.29, iy + id_*0.03),
                        size=(id_*0.58, id_*0.14))
                # Stone ring
                Color(*T.k(T.BORDER_LT, 0.92))
                Ellipse(pos=(cx - id_*0.27, iy + id_*0.06),
                        size=(id_*0.54, id_*0.13))
                # Hot ember bed inside ring
                Color(0.72, 0.24, 0.04, 0.65)
                Ellipse(pos=(cx - id_*0.18, iy + id_*0.08),
                        size=(id_*0.36, id_*0.07))
                # Logs (behind flame base)
                Color(0.36, 0.18, 0.06, 1.0)
                Line(points=[ix + id_*0.18, iy + id_*0.14,
                             ix + id_*0.70, iy + id_*0.46], width=dp(2.5))
                Line(points=[ix + id_*0.82, iy + id_*0.14,
                             ix + id_*0.30, iy + id_*0.46], width=dp(2.5))
                # Outer heat bloom (diffuse red-orange halo)
                Color(0.78, 0.20, 0.04, 0.20)
                Ellipse(pos=(cx - id_*0.30, iy + id_*0.20),
                        size=(id_*0.60, id_*0.66))
                # Main flame — orange body
                Color(0.87, 0.42, 0.07, 0.90)
                Ellipse(pos=(cx - id_*0.19, iy + id_*0.24),
                        size=(id_*0.38, id_*0.55))
                # Mid flame — gold-orange
                Color(*T.k(T.GOLD, 0.96))
                Ellipse(pos=(cx - id_*0.12, iy + id_*0.34),
                        size=(id_*0.24, id_*0.40))
                # Inner flame — bright gold
                Color(*T.k(T.GOLD_LT, 1.0))
                Ellipse(pos=(cx - id_*0.07, iy + id_*0.46),
                        size=(id_*0.14, id_*0.24))
                # Hot tip — near white
                Color(1.0, 0.97, 0.76, 0.88)
                Ellipse(pos=(cx - id_*0.025, iy + id_*0.61),
                        size=(id_*0.05, id_*0.08))
            else:
                # ── Unlit campfire ────────────────────────────────────────
                # Stone ring drop-shadow
                Color(0.0, 0.0, 0.0, 0.40)
                Ellipse(pos=(cx - id_*0.29, iy + id_*0.03),
                        size=(id_*0.58, id_*0.14))
                # Stone ring
                Color(*T.k(T.BORDER, 0.68))
                Ellipse(pos=(cx - id_*0.27, iy + id_*0.06),
                        size=(id_*0.54, id_*0.13))
                # Cold ash inside ring
                Color(0.24, 0.26, 0.28, 0.55)
                Ellipse(pos=(cx - id_*0.18, iy + id_*0.08),
                        size=(id_*0.36, id_*0.07))
                # Logs (cold, grey-brown)
                Color(*T.k(T.TEXT_DIM, 0.72))
                Line(points=[ix + id_*0.18, iy + id_*0.14,
                             ix + id_*0.70, iy + id_*0.46], width=dp(2.5))
                Line(points=[ix + id_*0.82, iy + id_*0.14,
                             ix + id_*0.30, iy + id_*0.46], width=dp(2.5))
                # Smoke wisps (thin bezier curves)
                Color(0.42, 0.44, 0.46, 0.30)
                Line(bezier=[cx, iy + id_*0.50,
                             cx + id_*0.06, iy + id_*0.60,
                             cx - id_*0.04, iy + id_*0.70,
                             cx + id_*0.02, iy + id_*0.80],
                     width=dp(1.0))
                Color(0.42, 0.44, 0.46, 0.18)
                Line(bezier=[cx - id_*0.05, iy + id_*0.52,
                             cx - id_*0.10, iy + id_*0.63,
                             cx - id_*0.03, iy + id_*0.73,
                             cx - id_*0.08, iy + id_*0.82],
                     width=dp(1.0))

    def set_state(self, active: bool, img_path: str = ""):  # noqa: img_path unused by design
        self._active = active
        self._lbl.text_color = T.k(T.BLOOD_LT if active else T.TEXT_DIM)
        self._lbl.bold       = active
        self._redraw()

    def on_touch_down(self, touch):
        if self.collide_point(*touch.pos):
            self._active = not self._active
            self._lbl.text_color = T.k(T.BLOOD_LT if self._active else T.TEXT_DIM)
            self._lbl.bold       = self._active
            self._redraw()
            self._on_toggle(self._active)
            return True
        return super().on_touch_down(touch)


class HeaderCard(BoxLayout):
    """
    Persistent header: character name, hope portrait, sanity chip,
    ADV toggles, WIS/CON stat chips, exhaustion pips.
    """

    def __init__(self, **kwargs):
        kwargs.setdefault("orientation", "vertical")
        kwargs.setdefault("size_hint_y", None)
        kwargs.setdefault("height", dp(182))
        kwargs.setdefault("spacing", dp(2))
        kwargs.setdefault("padding", [dp(8), dp(10), dp(8), dp(4)])
        super().__init__(**kwargs)

        with self.canvas.before:
            Color(*T.k(T.BG_CARD))
            self._bg = Rectangle()
        self.bind(pos=self._upd_bg, size=self._upd_bg)
        self._build()

    def _upd_bg(self, *_):
        self._bg.pos  = self.pos
        self._bg.size = self.size

    def _build(self):
        # Row 1 — character name + exhaustion (72dp)
        row1 = MDBoxLayout(size_hint_y=None, height=dp(72), spacing=dp(6))
        self._name_field = MDTextField(
            hint_text="Character Name.",
            text="",
            mode="rectangle",
            line_color_normal=T.k(T.BORDER),
            line_color_focus=(1, 1, 1, 0.85),
            hint_text_color_focus=(1, 1, 1, 0.55),
            font_size="14sp")
        self._name_field.text_color_focus = T.k(T.TEXT_BRIGHT)
        self._name_field.foreground_color = T.k(T.TEXT_BRIGHT)
        self._name_field.bind(text=self._on_name_change)
        row1.add_widget(self._name_field)

        # Exhaustion: title + pips + description, right side of row1
        exh_side = BoxLayout(orientation="vertical", spacing=dp(2),
                             size_hint_x=None, width=dp(162))
        self._exh_widget = ExhaustionWidget(size_hint_y=None, height=dp(44))
        self._exh_widget.set_change_callback(self._on_exhaustion_change)

        exh_desc_box = BoxLayout(orientation="vertical", size_hint_y=None, height=dp(26))
        from kivy.graphics import Color as _C, Rectangle as _R
        with exh_desc_box.canvas.before:
            _C(*T.k(T.BORDER, 0.5))
            _desc_bd = _R()
            _C(*T.k(T.BG_INSET))
            _desc_bg = _R()
        def _upd_desc(w, *_):
            _desc_bd.pos = w.pos; _desc_bd.size = w.size
            _desc_bg.pos = (w.x + 1, w.y + 1)
            _desc_bg.size = (max(0, w.width - 2), max(0, w.height - 2))
        exh_desc_box.bind(pos=_upd_desc, size=_upd_desc)

        self._exh_desc_lbl = MDLabel(
            text="No Exhaustion",
            theme_text_color="Custom", text_color=T.k(T.TEXT_DIM),
            font_size="7sp", halign="center", valign="middle",
            shorten=True, shorten_from="right")
        def _fit_exh_desc(lbl, *_):
            lbl.text_size = (max(0, lbl.width - dp(6)), None)
        self._exh_desc_lbl.bind(size=_fit_exh_desc)
        exh_desc_box.add_widget(self._exh_desc_lbl)

        exh_side.add_widget(self._exh_widget)
        exh_side.add_widget(exh_desc_box)
        row1.add_widget(exh_side)
        self.add_widget(row1)

        # ADV row — CON ADV (red, left) | WIS ADV (purple, right) | spacer (20dp)
        adv_row = MDBoxLayout(size_hint_y=None, height=dp(20), spacing=dp(6))
        self._con_adv = _AdvBtn(
            T.BLOOD,
            on_toggle=lambda v: setattr(App.get_running_app(), 'con_adv', v),
            size_hint_y=None, height=dp(20))
        self._wis_adv = _AdvBtn(
            T.PURPLE,
            on_toggle=lambda v: setattr(App.get_running_app(), 'wis_adv', v),
            size_hint_y=None, height=dp(20))
        adv_row.add_widget(self._con_adv)
        adv_row.add_widget(self._wis_adv)
        adv_row.add_widget(Widget())
        self.add_widget(adv_row)

        # Row 2 — CON chip (red) | WIS chip (purple, next to sanity) | Sanity + Hope (72dp)
        row2 = MDBoxLayout(size_hint_y=None, height=dp(72), spacing=dp(6))
        self._con_chip = _StatChip("CON", T.BLOOD, self._on_edit_con,
                                   size_hint_y=None, height=dp(72))
        self._wis_chip = _StatChip("WIS", T.PURPLE, self._on_edit_wis,
                                   size_hint_y=None, height=dp(72))
        row2.add_widget(self._con_chip)
        row2.add_widget(self._wis_chip)

        # Sanity chip first, then Hope campfire (sanity sits next to WIS)
        hope_san = MDBoxLayout(spacing=dp(4))
        self._san_chip = _SanityChip(size_hint_y=1)
        self._hope_portrait = _HopePortrait(
            on_toggle=self._on_hope_toggle,
            on_image_picked=self._on_hope_image,
            size_hint_x=None, width=dp(54), size_hint_y=1)
        hope_san.add_widget(self._san_chip)
        hope_san.add_widget(self._hope_portrait)
        row2.add_widget(hope_san)
        self.add_widget(row2)

    def refresh(self, state: SanityState):
        self._wis_chip.update(state.wis_score, state.wis_mod)
        self._con_chip.update(state.con_score, state.con_mod)
        self._exh_widget.level = state.exhaustion
        self._exh_desc_lbl.text = _EXH_DESC.get(state.exhaustion, "")
        self._san_chip.update(state.current_sanity, state.max_sanity,
                              state.percent * 100, state.madness, state.wis_score)
        self._hope_portrait.set_state(state.hope,
                                      getattr(state, "hope_img_path", ""))

    def _on_hope_toggle(self, active: bool):
        app = App.get_running_app()
        app.state.hope = active
        app.save_manager.save(app.state, app.fm, app.char_name, app.enc_history)

    def _on_hope_image(self, path: str):
        app = App.get_running_app()
        app.state.hope_img_path = path
        app.save_manager.save(app.state, app.fm, app.char_name, app.enc_history)

    def _on_name_change(self, inst, val):
        App.get_running_app().char_name = val.strip()

    def _on_edit_wis(self, *_):
        app = App.get_running_app()
        def confirm(val):
            app.undo_stack.push(app.state, app.fm)
            app.state.wis_score   = val
            app.state.max_sanity  = SANITY_BASE + val
            app.state.current_sanity = min(app.state.current_sanity, app.state.max_sanity)
            app.state.rebuild_thresholds()
            app.refresh_all()
            app.save_manager.save(app.state, app.fm, app.char_name, app.enc_history)
        StatDialog("Edit WIS Score", app.state.wis_score, confirm).open()

    def _on_edit_con(self, *_):
        app = App.get_running_app()
        def confirm(val):
            app.undo_stack.push(app.state, app.fm)
            app.state.con_score = val
            app.refresh_all()
            app.save_manager.save(app.state, app.fm, app.char_name, app.enc_history)
        StatDialog("Edit CON Score", app.state.con_score, confirm).open()

    def _on_exhaustion_change(self, level: int):
        app = App.get_running_app()
        app.undo_stack.push(app.state, app.fm)
        app.state.exhaustion = level
        self._exh_desc_lbl.text = _EXH_DESC.get(level, "")
        app.save_manager.save(app.state, app.fm, app.char_name, app.enc_history)



# ═══════════════════════════════════════════════════════════════════════════
# TAB BUTTON
# ═══════════════════════════════════════════════════════════════════════════

class _TabBtn(BoxLayout):
    """Single tab button in the custom tab bar."""

    def __init__(self, label_text: str, active_color: str, on_tap, **kwargs):
        super().__init__(orientation="vertical", **kwargs)
        self._active_color = active_color
        self._on_tap = on_tap
        self._active = False

        self._lbl = MDLabel(
            text=label_text,
            halign="center",
            theme_text_color="Custom",
            text_color=T.k(T.TEXT_DIM),
            font_style="Button",
            bold=False)
        self.add_widget(self._lbl)
        self.bind(pos=self._draw, size=self._draw)
        Clock.schedule_once(self._draw)

    def set_active(self, active: bool):
        self._active = active
        self._lbl.text_color = T.k(self._active_color if active else T.TEXT_DIM)
        self._lbl.bold = active
        self._draw()

    def _draw(self, *_):
        self.canvas.before.clear()
        with self.canvas.before:
            if self._active:
                Color(*T.k(self._active_color, 0.14))
                Rectangle(pos=self.pos, size=self.size)
                Color(*T.k(self._active_color))
                Rectangle(pos=(self.x, self.y), size=(self.width, dp(3)))

    def on_touch_down(self, touch):
        if self.collide_point(*touch.pos):
            self._on_tap()
            return True
        return super().on_touch_down(touch)


# ═══════════════════════════════════════════════════════════════════════════
# MAIN APP
# ═══════════════════════════════════════════════════════════════════════════

class SFMApp(MDApp):
    title = "Psyke"
    icon  = "icon.png"

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.state         = SanityState()
        self.fm            = FearManager()
        self.undo_stack    = UndoStack()
        self.enc_history:  list[str] = []
        self.char_name     = ""
        self.save_manager: SaveManager | None = None
        self._sep_color    = T.GOLD
        self._sep_widget:  Widget | None = None
        self._active_dialog: MDDialog | None = None
        self.wis_adv       = False   # Advantage on WIS saves (fear encounters)
        self.con_adv       = False   # Advantage on CON saves (wound encounters)

    # ── Build ──────────────────────────────────────────────────────────────────

    def build(self):
        self.theme_cls.theme_style     = T.KIVY_STYLE
        self.theme_cls.primary_palette = T.KIVY_PRIMARY
        self.theme_cls.accent_palette  = T.KIVY_ACCENT

        self.save_manager = SaveManager(user_data_dir=self.user_data_dir)

        # Back button (Android hardware / ESC)
        Window.bind(on_keyboard=self._on_keyboard)

        root = BoxLayout(orientation="vertical")

        # Persistent header
        self._header = HeaderCard(size_hint_y=None, height=dp(182))
        root.add_widget(self._header)

        # Sanity bar
        self._san_bar = SanityBar(size_hint_y=None, height=dp(44))
        root.add_widget(self._san_bar)

        # Madness banner — kept for compat but zero height (removed per request)
        self._mad_banner = MadnessBanner(size_hint_y=None, height=0)
        # (not added to root — fully hidden)

        # Tab bar — 4 tabs
        tab_bar = BoxLayout(orientation="horizontal",
                            size_hint_y=None, height=dp(40))
        self._tab_btns: dict[str, _TabBtn] = {}
        for name, label, color in [
            ("fears",  "Fears",  T.GOLD),
            ("sanity", "Sanity", T.PURPLE),
            ("wounds", "Wounds", T.BLOOD),
            ("spells", "Spells", T.SILVER),
        ]:
            btn = _TabBtn(label, color, on_tap=lambda n=name: self._switch_tab(n))
            self._tab_btns[name] = btn
            tab_bar.add_widget(btn)
        root.add_widget(tab_bar)

        # Separator line
        self._sep_widget = Widget(size_hint_y=None, height=dp(2))
        self._sep_widget.bind(pos=self._draw_sep, size=self._draw_sep)
        root.add_widget(self._sep_widget)

        # ScreenManager
        self._sm = ScreenManager(transition=NoTransition())

        s1 = Screen(name="fears")
        self._fears_tab = FearsTab()
        s1.add_widget(self._fears_tab)
        self._sm.add_widget(s1)

        s2 = Screen(name="sanity")
        self._sanity_tab = SanityTab()
        s2.add_widget(self._sanity_tab)
        self._sm.add_widget(s2)

        s3 = Screen(name="wounds")
        self._wounds_tab = WoundsTab()
        s3.add_widget(self._wounds_tab)
        self._sm.add_widget(s3)

        s4 = Screen(name="spells")
        self._spells_tab = SpellsTab()
        s4.add_widget(self._spells_tab)
        self._sm.add_widget(s4)

        root.add_widget(self._sm)

        self.session_log = SessionLog()
        self._switch_tab("fears")
        Clock.schedule_once(lambda dt: self._load())

        return root

    # ── Back button / ESC ──────────────────────────────────────────────────────

    def _on_keyboard(self, window, key, *args):
        if key == 27:  # ESC / Android back
            # Dismiss open dialog first
            if self._active_dialog:
                try: self._active_dialog.dismiss()
                except Exception: pass
                self._active_dialog = None
                return True
            # Cancel active fear encounter
            if hasattr(self, "_fears_tab") and self._fears_tab._enc.active:
                self._fears_tab.cancel_encounter()
                return True
            # Otherwise let Android handle (minimise / back to launcher)
            return False
        return False

    # ── Tab switching ──────────────────────────────────────────────────────────

    def _switch_tab(self, name: str):
        self._sm.current = name
        colors = {"fears": T.GOLD, "sanity": T.PURPLE,
                  "wounds": T.BLOOD, "spells": T.SILVER}
        for n, btn in self._tab_btns.items():
            btn.set_active(n == name)
        self._sep_color = colors.get(name, T.BORDER)
        self._draw_sep()

    def _draw_sep(self, *_):
        if not self._sep_widget: return
        w = self._sep_widget
        w.canvas.clear()
        with w.canvas:
            Color(*T.k(self._sep_color))
            Rectangle(pos=w.pos, size=w.size)

    # ── Load / Save ────────────────────────────────────────────────────────────

    def _load(self, *_):
        data = self.save_manager.load()
        if not data:
            self.refresh_all()
            return
        self.state.wis_score      = data.get("wis", 10)
        self.state.con_score      = data.get("con", 10)
        self.state.max_sanity     = SANITY_BASE + self.state.wis_score
        self.state.current_sanity = data.get("cur", self.state.max_sanity)
        self.state.exhaustion     = data.get("exh", 0)
        self.state.hope           = data.get("hope", False)
        self.state.hope_img_path  = data.get("hope_img", "")
        self.state.rebuild_thresholds()
        self.state.wounds    = []
        self.state.madnesses = []
        from models import WoundEntry, MadnessEntry
        for w in data.get("wounds", []):
            self.state.wounds.append(WoundEntry.from_dict(w))
        for m in data.get("madnesses", []):
            self.state.madnesses.append(MadnessEntry.from_dict(m))
        self.fm.restore(data.get("fears", data))   # handle old flat format
        self.char_name = data.get("char_name", "")
        self._header._name_field.text = self.char_name
        self.enc_history = list(data.get("enc_history", []))
        for entry in self.enc_history:
            self.session_log.add_entry(entry)
        self.refresh_all()

    # ── Global refresh ─────────────────────────────────────────────────────────

    def refresh_all(self):
        st  = self.state
        pct = st.percent * 100

        self._san_bar.set_stage(st.madness)
        self._san_bar.set_pct(pct)
        self._mad_banner.set_stage(st.madness)
        self._header.refresh(st)

        self._fears_tab.refresh()
        self._sanity_tab.refresh()
        self._wounds_tab.refresh()
        self._spells_tab.refresh()

    def notify_event(self, message: str, tab_name: str, color_hex: str,
                     action_cb=None, extra_actions=None):
        """Show a floating notification card with optional action buttons.

        action_cb:     primary callback; shows '[ VIEW > ]', switches to tab_name.
        extra_actions: list of (label, tab_name, cb) for additional buttons.
        Replaces any existing notification card immediately.
        """
        # Remove any existing notification card
        for ch in list(Window.parent.children):
            if getattr(ch, '_notify_card', False):
                Window.parent.remove_widget(ch)

        has_btns = bool(action_cb or extra_actions)

        card = MDCard(
            orientation="vertical",
            md_bg_color=T.k(color_hex),
            radius=[dp(6)],
            elevation=6,
            padding=[dp(14), dp(10), dp(8), dp(10)],
            spacing=dp(4),
            size_hint_x=0.92,
            size_hint_y=None,
            adaptive_height=True,
            pos_hint={"center_x": 0.5},
            y=dp(12),
        )
        card._notify_card = True

        card.add_widget(MDLabel(
            text=message,
            theme_text_color="Custom",
            text_color=(1, 1, 1, 1),
            adaptive_height=True,
        ))

        if has_btns:
            btn_row = MDBoxLayout(spacing=dp(4), adaptive_height=True)
            btn_row.add_widget(Widget())

            def _make_btn(label, btab, bcb):
                def _do(*_):
                    if card.parent:
                        card.parent.remove_widget(card)
                    self._switch_tab(btab)
                    if bcb:
                        Clock.schedule_once(lambda _: bcb(), 0.2)
                return MDFlatButton(
                    text=label,
                    theme_text_color="Custom",
                    text_color=T.k(T.GOLD_LT),
                    font_style="Button",
                    on_release=_do,
                )

            if action_cb:
                btn_row.add_widget(_make_btn("[ VIEW > ]", tab_name, action_cb))
            for ex_label, ex_tab, ex_cb in (extra_actions or []):
                btn_row.add_widget(_make_btn(ex_label, ex_tab, ex_cb))
            card.add_widget(btn_row)

        Window.parent.add_widget(card)
        duration = 6.0 if has_btns else 3.5
        Clock.schedule_once(
            lambda _: card.parent.remove_widget(card) if card.parent else None,
            duration)

    def notify_exhaustion(self, new_level: int):
        """Flash the exhaustion pip for the new level in the header."""
        self._header._exh_widget.flash_pip(new_level)

    # ── Action handlers ────────────────────────────────────────────────────────

    def _on_undo(self, *_):
        if not self.undo_stack.can_undo:
            MDSnackbar(
                MDLabel(text="Nothing to undo.",
                        theme_text_color="Custom", text_color=(1, 1, 1, 1)),
                md_bg_color=T.k(T.BORDER), duration=1.5
            ).open()
            return
        snap_st, snap_fm = self.undo_stack.pop()
        self.state.restore(snap_st)
        self.fm.restore(snap_fm)
        self.refresh_all()
        self.save_manager.save(self.state, self.fm, self.char_name, self.enc_history)

    def _on_show_log(self, *_):
        dlg = MDDialog(
            title="Session Log",
            type="custom",
            content_cls=self.session_log,
            size_hint=(0.95, 0.8),
            buttons=[MDFlatButton(text="Close",
                                  on_release=lambda *a: dlg.dismiss())]
        )
        self._active_dialog = dlg
        dlg.bind(on_dismiss=lambda *_: setattr(self, "_active_dialog", None))
        dlg.open()


# ═══════════════════════════════════════════════════════════════════════════
# ENTRY POINT
# ═══════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    SFMApp().run()
