"""
Tab 3: Wounds  (V4 — 4-stage fear-style encounter)

Two-page swipeable layout:
  Page 0 — Encounter & Wounds: encounter section, wound lists, rules
  Page 1 — Add Wound: minor/major picker, preview + Apply button

Encounter stages (left-side rail tabs):
  dc     — Wound DC calculated from damage taken (spin animation)
  save   — CON saving throw (dice spin + verdict buttons)
  sanity — Sanity dice roll (all non-pass5 outcomes)
  select — Wound type + effect preview + APPLY WOUND button
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
from kivy.properties import BooleanProperty as _BProp, NumericProperty as _NProp
from kivy.uix.anchorlayout import AnchorLayout
from kivy.uix.floatlayout import FloatLayout
from kivy.uix.scrollview import ScrollView
from kivy.uix.widget import Widget

from kivymd.uix.boxlayout import MDBoxLayout
from kivymd.uix.button import MDFlatButton, MDIconButton, MDRaisedButton
from kivymd.uix.label import MDLabel
from kivymd.uix.menu import MDDropdownMenu
from kivymd.uix.snackbar import MDSnackbar

from models import (
    WoundEncPhase, WoundEncounterState, WoundEntry,
    MINOR_WOUND_TABLE, MAJOR_WOUND_TABLE,
    roll_d, safe_int, roll_random_wound, clamp, WOUND_RULES_TEXT
)
from ui_utils import (
    BorderCard, Divider,
    SectionLabel, CaptionLabel,
    ExpandingEffectCard, ExpandableSection, PickerListItem,
    themed_field, SwipePageIndicator,
    populate_rules_section, FillSwipeTitle, HookMorphArrow,
)
import theme as T

from tab_fears import _EncTab, clip_children, EncounterListItem


# ─────────────────────────────────────────────────────────────────────────────
# WOUND-SPECIFIC ENC TAB
# ─────────────────────────────────────────────────────────────────────────────

class _WoundEncTab(_EncTab):
    """_EncTab variant for wound encounters — blood/purple colour scheme."""

    _STAGE_HEX = {
        "dc":     T.GOLD_DK,
        "save":   T.BLOOD,
        "sanity": T.PURPLE_LT,
        "wound":  T.BLOOD,
    }

    # Tab body colour: blood red instead of gold
    @property
    def _main_hex(self):    return T.BLOOD
    @property
    def _main_dk_hex(self): return T.BLOOD_DK
    @property
    def _main_lt_hex(self): return T.BLOOD_LT

    def _side_hex(self) -> str:
        return self._cap_hex or self._STAGE_HEX.get(self._tab_key, T.BLOOD)


# ─────────────────────────────────────────────────────────────────────────────
# ENCOUNTER WOUND CARD
# Active wound item for wounds that came from a wound encounter.
# Identical visual language to ExpandingEffectCard but with an extra level:
#   Level 0 — collapsed  : header (wound name + subheading) only.
#   Level 1 — desc open  : wound effect text + "ENCOUNTER DETAILS" button + hook arrow.
#   Level 2 — shell open : frozen encounter tabs appear seamlessly below button row.
# ─────────────────────────────────────────────────────────────────────────────

class EncounterWoundCard(MDBoxLayout):
    expand_t   = _NProp(0.0)
    open_state = _BProp(False)
    shell_open = _BProp(False)

    def __init__(self, title: str, subtitle: str, effect: str,
                 frozen_shell, accent_hex: str = T.WOUND_MIN, **kwargs):
        kwargs.setdefault("orientation", "vertical")
        kwargs.setdefault("size_hint_y", None)
        # Left=0 so tabs reach card edge; text areas add their own dp(14) indent.
        kwargs.setdefault("padding", [0, dp(6), dp(14), dp(6)])
        kwargs.setdefault("spacing", dp(2))
        super().__init__(**kwargs)

        self._frozen_shell = frozen_shell
        self._accent_hex   = accent_hex
        self._has_shell_toggle = frozen_shell is not None

        # ── Canvas ───────────────────────────────────────────────────────────
        with self.canvas.before:
            Color(*T.k(T.BORDER))
            self._outer        = RoundedRectangle(radius=[dp(10)])
            self._bg_color     = Color(*T.k(T.BG_CARD))
            self._inner        = RoundedRectangle(radius=[dp(9)])
            self._accent_color = Color(*T.k(accent_hex))
            self._bar          = RoundedRectangle(radius=[dp(9), 0, 0, dp(9)])

        # ── Header (always visible, tappable) ────────────────────────────────
        self._header = MDBoxLayout(
            orientation="horizontal",
            size_hint_y=None, adaptive_height=True,
            padding=[dp(14), 0, 0, 0])
        _text_col = MDBoxLayout(
            orientation="vertical", spacing=0,
            size_hint_y=None, adaptive_height=True)
        self._title_lbl = FillSwipeTitle(fill_rgba=list(T.k(accent_hex)))
        self._title_lbl.text = title
        self._subtitle_lbl = MDLabel(
            text=subtitle,
            theme_text_color="Custom", text_color=T.k(T.TEXT_DIM),
            font_style="Caption", size_hint_y=None, adaptive_height=True)
        _text_col.add_widget(self._title_lbl)
        _text_col.add_widget(self._subtitle_lbl)
        self._header.add_widget(_text_col)
        self.add_widget(self._header)

        # ── Description section ───────────────────────────────────────────────
        self._desc_sec = MDBoxLayout(
            orientation="vertical", spacing=dp(6),
            size_hint_y=None, height=0, opacity=0,
            padding=[dp(14), dp(4), 0, dp(4)])

        self._effect_lbl = MDLabel(
            text=effect or "No injury sustained.",
            theme_text_color="Custom", text_color=T.k(T.TEXT),
            font_style="Body2", size_hint_y=None, adaptive_height=True)
        self._effect_lbl.bind(
            width=lambda inst, v: setattr(inst, "text_size", (v, None)),
            texture_size=lambda inst, sz: setattr(
                inst, "height", max(dp(20), sz[1])),
            height=self._on_effect_height_change)
        self._desc_sec.add_widget(self._effect_lbl)

        self._btn_row = None
        self._detail_btn = None
        self._arrow_slot = None
        self._arrow = None
        if self._has_shell_toggle:
            # Button row: flat button + rules-style hook arrow
            self._btn_row = MDBoxLayout(
                orientation="horizontal",
                size_hint_y=None, height=dp(36), spacing=dp(4))
            self._detail_btn = MDFlatButton(
                text="ENCOUNTER DETAILS",
                theme_text_color="Custom", text_color=T.k(accent_hex),
                size_hint_x=None,
                size_hint_y=None, height=dp(36),
                on_release=self._on_detail_btn)
            self._arrow_slot = AnchorLayout(
                anchor_x="center",
                anchor_y="center",
                size_hint_x=None,
                width=dp(34),
            )
            self._arrow = HookMorphArrow(
                color_hex=accent_hex, t=0.0,
                size_hint_x=None, width=dp(28),
                size_hint_y=None, height=dp(28))
            self._arrow_slot.add_widget(self._arrow)
            self._btn_row.add_widget(self._detail_btn)
            self._btn_row.add_widget(self._arrow_slot)
            self._btn_row.add_widget(Widget())   # filler
            self._desc_sec.add_widget(self._btn_row)
        self.add_widget(self._desc_sec)

        # ── Shell section (no left indent — tabs start at card edge) ─────────
        self._shell_sec = MDBoxLayout(
            orientation="vertical",
            size_hint_y=None, height=0, opacity=0,
            padding=[0, 0, 0, dp(4)])
        clip_children(self._shell_sec)
        if frozen_shell is not None:
            self._shell_sec.add_widget(frozen_shell)
            frozen_shell.bind(height=self._on_shell_height_change)
        self.add_widget(self._shell_sec)

        self.bind(pos=self._redraw, size=self._redraw, expand_t=self._redraw)
        self.height = self._collapsed_h()

    # ── Touch ─────────────────────────────────────────────────────────────────

    def on_touch_down(self, touch):
        if not self.collide_point(*touch.pos):
            return super().on_touch_down(touch)

        # Only dispatch to controls that are visibly open. This prevents the
        # hidden encounter-details row or frozen shell from catching taps while
        # the card is still collapsed/opening.
        if self._shell_controls_ready() and self._shell_sec.collide_point(*touch.pos):
            if self._shell_sec.on_touch_down(touch):
                return True
        if self._has_shell_toggle and self._detail_controls_ready():
            if self._detail_btn.collide_point(*touch.pos):
                if self._detail_btn.on_touch_down(touch):
                    return True
            if self._arrow_slot.collide_point(*touch.pos):
                self._on_detail_btn()
                return True

        # Route through external tap callback (for selection tracking) if set,
        # otherwise fall back to internal toggle.
        if getattr(self, "_tap_cb", None):
            self._tap_cb()
        else:
            self._toggle_desc()
        return True

    # ── Geometry ─────────────────────────────────────────────────────────────

    def _collapsed_h(self) -> float:
        hdr = max(dp(32), getattr(self._header, "height", 0))
        return max(dp(56), self.padding[1] + self.padding[3] + hdr + self.spacing)

    def _desc_inner_h(self) -> float:
        p    = self._desc_sec.padding
        body = max(dp(20), self._effect_lbl.height)
        btn_h = dp(42) if self._has_shell_toggle else 0
        return p[1] + body + btn_h + p[3]

    def _shell_inner_h(self) -> float:
        if self._frozen_shell is None:
            return 0
        p = self._shell_sec.padding
        return p[1] + max(0, self._frozen_shell.height) + p[3]

    def _detail_controls_ready(self) -> bool:
        return (
            self._has_shell_toggle
            and
            self.open_state
            and self.expand_t >= 0.95
            and self._desc_sec.opacity >= 0.95
            and self._desc_sec.height >= dp(20)
        )

    def _shell_controls_ready(self) -> bool:
        return (
            self.shell_open
            and self._shell_sec.opacity >= 0.95
            and self._shell_sec.height >= dp(10)
        )

    # ── Open / close ──────────────────────────────────────────────────────────

    def _toggle_desc(self):
        if self.open_state:
            if self.shell_open:
                self._close_shell(on_complete=self._do_close_desc)
            else:
                self._do_close_desc()
        else:
            self._do_open_desc()

    def _do_open_desc(self):
        Animation.cancel_all(self, "height", "expand_t")
        Animation.cancel_all(self._desc_sec, "height")
        self.open_state = True
        desc_h = self._desc_inner_h()
        card_h = self._collapsed_h() + self.spacing + desc_h
        self._desc_sec.height = 0
        anim = Animation(height=card_h, expand_t=1.0,
                         duration=0.28, t="out_cubic")
        anim.bind(on_complete=lambda *_: Clock.schedule_once(self._sync_open_height))
        anim.start(self)
        Animation(height=desc_h, duration=0.28, t="out_cubic").start(self._desc_sec)

    def _do_close_desc(self, *_):
        Animation.cancel_all(self, "height", "expand_t")
        Animation.cancel_all(self._desc_sec, "height")
        self.open_state = False
        anim = Animation(height=self._collapsed_h(), expand_t=0.0,
                         duration=0.28, t="out_cubic")
        def _hide(*__):
            self._desc_sec.opacity = 0
            self._desc_sec.height  = 0
        anim.bind(on_complete=_hide)
        anim.start(self)
        Animation(height=0, duration=0.28, t="out_cubic").start(self._desc_sec)

    def _on_detail_btn(self, *_):
        if not self._detail_controls_ready():
            return
        if self.shell_open:
            self._close_shell()
        else:
            self._open_shell()

    def _open_shell(self):
        self.shell_open = True
        if self._arrow is not None:
            self._arrow.morph_to(1.0)
        self._shell_sec.opacity = 1.0
        shell = self._frozen_shell
        if shell and hasattr(shell, "_reset_tabs_to_rail"):
            shell._reset_tabs_to_rail()
        Clock.schedule_once(self._animate_shell_open, 0.05)

    def _animate_shell_open(self, dt=None):
        shell_h = self._shell_inner_h()
        if shell_h < dp(10):
            Clock.schedule_once(self._animate_shell_open, 0.05)
            return
        Animation.cancel_all(self, "height")
        Animation.cancel_all(self._shell_sec, "height")
        self._shell_sec.height = 0
        new_card_h = self.height + self.spacing + shell_h
        _shell = self._frozen_shell
        def _after_expand(*_):
            if _shell and hasattr(_shell, "_on_parent_open"):
                _shell._on_parent_open()
        anim = Animation(height=new_card_h, duration=0.28, t="out_cubic")
        anim.bind(on_complete=_after_expand)
        anim.start(self)
        Animation(height=shell_h, duration=0.28, t="out_cubic").start(self._shell_sec)

    def _close_shell(self, on_complete=None):
        self.shell_open = False
        if self._arrow is not None:
            self._arrow.morph_to(0.0)
        shell    = self._frozen_shell
        _snap_h  = self._shell_sec.height  # capture before any async delay

        def _do_card_shrink():
            Animation.cancel_all(self, "height")
            Animation.cancel_all(self._shell_sec, "height")
            target_h = max(self._collapsed_h(), self.height - _snap_h - self.spacing)
            def _done(*__):
                self._shell_sec.opacity = 0
                self._shell_sec.height  = 0
                if on_complete:
                    on_complete()
            anim = Animation(height=target_h, duration=0.28, t="out_cubic")
            anim.bind(on_complete=_done)
            anim.start(self)
            Animation(height=0, duration=0.28, t="out_cubic").start(self._shell_sec)

        if shell and hasattr(shell, "_on_parent_close"):
            shell._on_parent_close(on_done=_do_card_shrink)
        else:
            _do_card_shrink()

    def _on_shell_height_change(self, *_):
        if not self.shell_open:
            return
        shell_h = self._shell_inner_h()
        old_h   = self._shell_sec.height
        if abs(shell_h - old_h) > dp(2):
            Animation.cancel_all(self._shell_sec, "height")
            self._shell_sec.height = shell_h
            diff = shell_h - old_h
            Animation.cancel_all(self, "height")
            Animation(height=self.height + diff,
                      duration=0.18, t="out_cubic").start(self)

    def _on_effect_height_change(self, *_):
        if not self.open_state:
            return
        Clock.schedule_once(self._sync_open_height, 0)

    def _sync_open_height(self, *_):
        if not self.open_state:
            return
        desc_h = self._desc_inner_h()
        if abs(desc_h - self._desc_sec.height) > dp(2):
            self._desc_sec.height = desc_h
            if not self.shell_open:
                card_h = self._collapsed_h() + self.spacing + desc_h
                if abs(card_h - self.height) > dp(2):
                    Animation.cancel_all(self, "height")
                    Animation(height=card_h, duration=0.18, t="out_cubic").start(self)

    # ── set_open — duck-type ExpandingEffectCard for tap/open_wound helpers ──

    def set_open(self, open_state: bool, animate: bool = True):
        if open_state and not self.open_state:
            self._do_open_desc()
        elif not open_state and self.open_state:
            if self.shell_open:
                self._close_shell(on_complete=self._do_close_desc)
            else:
                self._do_close_desc()

    # ── Flash stroke (used by open_wound / highlight_last_wound) ─────────────

    def flash(self):
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
        _acc = list(T.k(self._accent_hex))
        with self.canvas.after:
            self._stroke_col  = Color(*_acc[:3], 1.0)
            self._stroke_line = Line(width=dp(2), cap="none", joint="miter")
        self._flash_evt = Clock.schedule_interval(self._tick_stroke, 1 / 60)

    def _tick_stroke(self, dt):
        SPEED = 2.0; HOLD = 0.25; FADE = 0.35
        self._flash_prog += dt
        total = 1.0 / SPEED + HOLD + FADE
        if self._flash_prog >= total:
            try:
                self.canvas.after.remove(self._stroke_col)
                self.canvas.after.remove(self._stroke_line)
            except Exception:
                pass
            self._flash_evt.cancel(); self._flash_evt = None; return
        draw_prog  = min(self._flash_prog * SPEED, 1.0)
        fade_start = 1.0 / SPEED + HOLD
        alpha = (max(0.0, 1.0 - (self._flash_prog - fade_start) / FADE)
                 if self._flash_prog >= fade_start else 1.0)
        _acc = list(T.k(self._accent_hex))
        self._stroke_col.rgba = (*_acc[:3], alpha)
        x = self.x + dp(1); y = self.y + dp(1)
        w = self.width - dp(2); h = self.height - dp(2)
        segs = [
            ((x,     y),     (x,     y+h), h),
            ((x,     y+h),   (x+w,   y+h), w),
            ((x+w,   y+h),   (x+w,   y),   h),
            ((x+w,   y),     (x,     y),   w),
        ]
        dist = draw_prog * 2 * (w + h)
        pts  = [x, y]; rem = dist
        for (x0, y0), (x1, y1), seg_len in segs:
            if rem <= 0: break
            if rem >= seg_len:
                pts += [x1, y1]; rem -= seg_len
            else:
                t2 = rem / seg_len
                pts += [x0 + t2*(x1-x0), y0 + t2*(y1-y0)]; break
        self._stroke_line.points = pts

    # ── Redraw ────────────────────────────────────────────────────────────────

    def _redraw(self, *_):
        t        = self.expand_t
        radius   = dp(10 + 2 * t)
        accent_w = dp(4 + 2 * t)

        self._bg_color.rgba     = T.k(T.BG_HOVER) if self.open_state else T.k(T.BG_CARD)
        self._accent_color.rgba = T.k(self._accent_hex)

        self._outer.pos    = self.pos;       self._outer.size   = self.size
        self._outer.radius = [radius]
        self._inner.pos    = (self.x+1, self.y+1)
        self._inner.size   = (max(0, self.width-2), max(0, self.height-2))
        self._inner.radius = [max(0, radius-1)]
        self._bar.pos      = (self.x+1, self.y+1)
        self._bar.size     = (accent_w, max(0, self.height-2))
        self._bar.radius   = [radius, 0, 0, radius]

        body_alpha = max(0.0, min(1.0, (t - 0.50) / 0.24))
        self._desc_sec.opacity = body_alpha

        mix    = max(0.0, min(1.0, (t - 0.18) / 0.24))
        dim    = T.k(T.TEXT_DIM)[:3]
        bright = T.k(T.TEXT_BRIGHT)[:3]
        col    = tuple(dim[i] + (bright[i] - dim[i]) * mix for i in range(3))
        self._subtitle_lbl.text_color = (*col, 1.0)
        self._subtitle_lbl.bold       = mix > 0.15
        self._title_lbl.fill_t        = max(0.0, min(1.0, (t - 0.12) / 0.46))


# ─────────────────────────────────────────────────────────────────────────────
# WOUNDS TAB
# ─────────────────────────────────────────────────────────────────────────────

class WoundsTab(MDBoxLayout):

    _TAB_SETTLE_DELAY           = 0.24
    _STAGE_BOX_EXPAND_DELAY     = 0.14
    _STAGE_CARD_REVEAL_DURATION = 0.34

    def __init__(self, **kwargs):
        kwargs.setdefault("orientation", "vertical")
        super().__init__(**kwargs)

        self._enc = WoundEncounterState()

        # ── Wound-list selection ──────────────────────────────────────────────
        self._sel_minor: WoundEntry | None = None
        self._active_minor_card: ExpandingEffectCard | None = None
        self._sel_major: WoundEntry | None = None
        self._active_major_card: ExpandingEffectCard | None = None
        self._minor_items: dict = {}
        self._major_items: dict = {}

        # ── Add-page state ────────────────────────────────────────────────────
        self._add_preview: dict = {}
        self._pending_wound: dict = {}

        # ── Page state ────────────────────────────────────────────────────────
        self._page = 0

        # ── Encounter tab system ──────────────────────────────────────────────
        self._enc_stage_tabs: dict[str, _WoundEncTab] = {}
        self._enc_active_stage: str | None = None
        self._enc_item: EncounterListItem | None = None
        self._wound_enc_items_box: MDBoxLayout | None = None
        self._current_enc_num: int = 0
        self._enc_height_sync_paused: bool = False
        self._enc_flow_shell: Widget | None = None
        self._enc_content: MDBoxLayout | None = None
        # Maps enc_num → completed EncounterListItem or reloaded EncounterWoundCard
        # so refresh() can skip enc-derived wounds already shown in the encounter history.
        self._enc_wound_items: dict = {}
        # enc_num of the currently open/selected completed encounter item
        self._sel_enc_num: int | None = None

        # Stage panel refs
        self._dc_stage_box   = None
        self._save_stage_box = None
        self._san_stage_box  = None
        self._wnd_stage_box  = None

        # DC-stage widgets
        self._enc_dc_num  = None
        self._dc_calc_lbl = None

        # Save-stage widgets
        self._enc_roll_num  = None
        self._roll_info_lbl = None
        self._outcome_lbl   = None

        # Sanity-stage widgets
        self._san_num_lbl  = None
        self._san_info_lbl = None

        # Wound-stage widgets
        self._wnd_type_lbl   = None
        self._wnd_name_lbl   = None
        self._wnd_effect_lbl = None
        self._wnd_sanity_lbl = None
        self._wnd_exh_lbl    = None

        # Roll info string
        self._enc_roll_info: str = ""

        # Pending wound (set in _on_wound_encounter, applied in _do_auto_complete)
        self._pending_outcome:      str  = ""
        self._pending_wound_desc:   str  = ""
        self._pending_wound_effect: str  = ""
        self._pending_wound_sev:    str  = ""
        self._pending_wound_roll:   int  = 0
        self._pending_sanity_loss:  int  = 0
        self._pending_san_rolls:    list = []

        # ── Build pages ───────────────────────────────────────────────────────
        self.add_widget(self._build_page_indicator())

        self._sv0 = ScrollView(do_scroll_x=False, size_hint=(None, None))
        p0 = MDBoxLayout(
            orientation="vertical",
            padding=dp(10), spacing=dp(8),
            size_hint_y=None, adaptive_height=True)
        p0.add_widget(self._build_encounter_section())
        p0.add_widget(self._build_rules_panel())
        self._sv0.add_widget(p0)

        self._sv1 = ScrollView(do_scroll_x=False, size_hint=(None, None))
        p1 = MDBoxLayout(
            orientation="vertical",
            padding=dp(10), spacing=dp(8),
            size_hint_y=None, adaptive_height=True)
        p1.add_widget(self._build_add_wound_card())
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

    @staticmethod
    def _wound_outcome_color(outcome: str) -> str:
        if outcome == "pass5":
            return T.GREEN
        if outcome == "pass":
            return T.WOUND_MIN
        if outcome == "fail":
            return T.BLOOD
        return T.BLOOD_DK

    @staticmethod
    def _wound_outcome_label(outcome: str) -> str:
        if outcome == "pass5":
            return "PASSED BY 5+"
        if outcome == "pass":
            return "PASSED"
        if outcome == "fail":
            return "FAILED"
        return "FAILED BY 5+"

    def _next_encounter_list_num(self) -> int:
        seen = [0]
        for w in self._app().state.wounds:
            rec = getattr(w, "enc_record", None) or {}
            enc_num = rec.get("enc_num")
            if isinstance(enc_num, int):
                seen.append(enc_num)
        self._current_enc_num = max(self._current_enc_num, max(seen))
        self._current_enc_num += 1
        return self._current_enc_num

    def _manual_wound_record(self, severity: str, desc: str, effect: str) -> dict:
        enc_num = self._next_encounter_list_num()
        return {
            "source": "manual_add",
            "enc_num": enc_num,
            "outcome": "pass" if severity == "minor" else "fail",
            "wound_desc": desc,
            "wound_sev": severity,
            "wound_effect": effect,
            "wound_roll": next(
                (r for r, d, _ in (
                    MINOR_WOUND_TABLE if severity == "minor" else MAJOR_WOUND_TABLE
                ) if d == desc),
                "?",
            ),
        }

    # ── Page indicator ────────────────────────────────────────────────────────

    def _build_page_indicator(self) -> MDBoxLayout:
        self._page_indicator = SwipePageIndicator(
            "Wounds", "Add Wound",
            left_hex=T.BLOOD, right_hex=T.BLOOD_LT, bg_hex=T.BLOOD)
        return self._page_indicator

    def _update_indicator(self, progress: float | None = None):
        self._page_indicator.set_progress(
            float(self._page) if progress is None else progress)

    def _reset_add_page(self):
        self._pending_wound.clear()
        for entry in self._add_preview.values():
            entry["picker"].show_placeholder(entry["default_text"], animate=False)

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
        if self._page == 1:
            self._reset_add_page()
        self._clear_wound_details()
        w = self._content_area.width
        target_base = -page * w
        new_page = page
        Animation.cancel_all(self._sv0)
        Animation.cancel_all(self._sv1)
        Animation.cancel_all(self._page_indicator, 'progress')
        anim0 = Animation(x=self._content_area.x + target_base,
                          duration=0.25, t='out_cubic')
        anim1 = Animation(x=self._content_area.x + target_base + w,
                          duration=0.25, t='out_cubic')
        Animation(progress=page, duration=0.25,
                  t='out_cubic').start(self._page_indicator)

        def on_done(*_):
            self._page = new_page
            self._update_indicator()

        anim0.bind(on_complete=on_done)
        anim0.start(self._sv0)
        anim1.start(self._sv1)

    def _animate_snap_back(self):
        w = self._content_area.width
        base = -self._page * w
        Animation.cancel_all(self._sv0)
        Animation.cancel_all(self._sv1)
        Animation.cancel_all(self._page_indicator, 'progress')
        anim0 = Animation(x=self._content_area.x + base, duration=0.2, t='out_cubic')
        anim1 = Animation(x=self._content_area.x + base + w, duration=0.2, t='out_cubic')
        Animation(progress=self._page, duration=0.2,
                  t='out_cubic').start(self._page_indicator)
        anim0.start(self._sv0)
        anim1.start(self._sv1)

    def _go_page(self, page: int):
        self._animate_to_page(page)

    # ── Swipe detection ───────────────────────────────────────────────────────

    def on_touch_down(self, touch):
        if self.collide_point(*touch.pos):
            touch.ud['wounds_swipe_start'] = (touch.x, touch.y)
            touch.ud['wounds_swiping'] = False
        return super().on_touch_down(touch)

    def on_touch_move(self, touch):
        if touch.grab_current is self:
            start = touch.ud.get('wounds_swipe_start')
            if start:
                dx = touch.x - start[0]
                w = self._content_area.width
                if self._page == 0:
                    offset = max(-w, min(0.0, dx))
                else:
                    offset = max(0.0, min(w, dx))
                self._update_sv_positions(offset)
            return True
        start = touch.ud.get('wounds_swipe_start')
        if (start and not touch.ud.get('wounds_swiping')
                and self.collide_point(*touch.pos)):
            dx = touch.x - start[0]
            dy = touch.y - start[1]
            if abs(dx) > dp(10) and abs(dx) > abs(dy) * 1.5:
                touch.ud['wounds_swiping'] = True
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
            start = touch.ud.get('wounds_swipe_start')
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

    # ── Build: Encounter Section ──────────────────────────────────────────────

    def _build_encounter_section(self) -> BorderCard:
        """
        Blood-themed encounter card.  Only asks for damage taken; DC is
        auto-calculated and shown as the first animated stage.
        Stages: DC → SAVE → SANITY (non-pass5) → SELECT
        """
        card = BorderCard(border_hex=T.BLOOD)
        card.add_widget(SectionLabel("WOUND ENCOUNTER", color_hex=T.BLOOD))

        # Damage input row with inline ENCOUNTER button
        field_row = MDBoxLayout(spacing=dp(8), size_hint_y=None, height=dp(52))
        self._dmg_field = themed_field(
            hint_text="Damage taken", text="0",
            accent_hex=T.BLOOD, input_filter="int", size_hint_x=1.0)
        self._wenc_btn = MDRaisedButton(
            text="ENCOUNTER",
            md_bg_color=T.k(T.BLOOD),
            size_hint_x=None, size_hint_y=None, height=dp(48),
            on_release=self._on_wound_encounter)
        field_row.add_widget(self._dmg_field)
        field_row.add_widget(self._wenc_btn)
        card.add_widget(field_row)

        # ── Encounter list header ─────────────────────────────────────────────
        enc_list_hdr = MDBoxLayout(size_hint_y=None, height=dp(32), spacing=dp(8))
        enc_list_hdr.add_widget(SectionLabel("ENCOUNTER LIST", color_hex=T.BLOOD))
        enc_list_hdr.add_widget(Widget())
        enc_list_hdr.add_widget(MDIconButton(
            icon="trash-can-outline",
            theme_icon_color="Custom", icon_color=T.k(T.RED),
            size_hint_x=None, width=dp(40),
            on_release=self._on_remove_enc))
        card.add_widget(enc_list_hdr)

        # Encounter history list (completed items live here after resolution)
        self._wound_enc_items_box = MDBoxLayout(
            orientation="vertical", adaptive_height=True, spacing=dp(4))
        card.add_widget(self._wound_enc_items_box)

        # Orphaned list boxes — populated by refresh() for selection tracking
        # but not attached to the card layout (not visible in this section).
        self._minor_list_box = MDBoxLayout(
            orientation="vertical", adaptive_height=True, spacing=dp(2))
        self._major_list_box = MDBoxLayout(
            orientation="vertical", adaptive_height=True, spacing=dp(2))

        # ── Flow shell ────────────────────────────────────────────────────────
        # Widget that reserves height in the card layout; tabs and _enc_content
        # are Widget children positioned at absolute screen coords.
        self._enc_flow_shell = Widget(size_hint_y=None, height=0, opacity=0)
        clip_children(self._enc_flow_shell)
        self._enc_flow_shell.bind(
            pos=lambda *_: self._sync_shell_layout(),
            size=lambda *_: self._sync_shell_layout(),
        )

        for key, label in (
            ("dc",     "DC"),
            ("save",   "SAVE"),
            ("sanity", "SANITY"),
            ("wound",  "WOUND"),
        ):
            tab = _WoundEncTab(key, label, self._open_encounter_stage)
            self._enc_stage_tabs[key] = tab
            self._enc_flow_shell.add_widget(tab)

        self._enc_content = MDBoxLayout(
            orientation="vertical", spacing=dp(6),
            padding=[0, dp(8), 0, dp(8)],
            size_hint=(None, None), height=0)
        self._enc_height_sync_paused = False
        self._enc_content.bind(
            minimum_height=lambda *_: self._on_enc_content_min_height())
        self._enc_flow_shell.add_widget(self._enc_content)

        # Critical: keep the live EncounterListItem height in sync with shell
        def _on_shell_height(shell, h):
            if self._enc_item and self._enc_item._mode == "live":
                self._enc_item.update_live_height()
        self._enc_flow_shell.bind(height=_on_shell_height)

        # Build stage panels
        self._build_dc_stage()
        self._build_save_stage()
        self._build_sanity_stage()
        self._build_wound_stage()

        return card

    # ── Stage panel factory ───────────────────────────────────────────────────

    def _mk_stage_panel(self, border_hex: str, min_height: int) -> MDBoxLayout:
        """Stencil-clipped panel that reveals horizontally from the rail."""
        panel = MDBoxLayout(
            orientation="vertical", spacing=dp(10),
            padding=[dp(14), dp(14), dp(14), dp(14)],
            size_hint_x=1, size_hint_y=None, adaptive_height=True,
        )
        panel._min_stage_height = dp(min_height)
        panel._stage_border_hex = border_hex
        panel._reveal_t   = 1.0
        panel._reveal_evt = None
        with panel.canvas.before:
            StencilPush()
            _clip = Rectangle()
            StencilUse()
            panel._stage_bd_col   = Color(*T.k(border_hex, 0.06))
            _bd  = RoundedRectangle(radius=[0, dp(12), dp(12), 0])
            panel._stage_bg_col   = Color(*T.k(border_hex, 0.018))
            _bg  = RoundedRectangle(radius=[0, dp(11), dp(11), 0])
            panel._stage_line_col = Color(*T.k(border_hex))
            _line = Line(width=dp(1.6), cap="none", joint="bevel")
        with panel.canvas.after:
            StencilUnUse()
            StencilPop()

        def _upd(w, *_, _bd=_bd, _bg=_bg, _line=_line, _clip=_clip):
            rt    = max(0.0, min(1.0, getattr(w, "_reveal_t", 1.0)))
            vis_w = max(0, w.width * rt)
            _clip.pos  = (w.x, w.y);   _clip.size  = (vis_w, w.height)
            _bd.pos    = w.pos;         _bd.size    = (vis_w, w.height)
            _bg.pos    = (w.x+1, w.y+1)
            _bg.size   = (max(0, vis_w-2), max(0, w.height-2))
            x, y, ww, hh = w.x, w.y, w.width, w.height
            rx = x + max(0, vis_w) - 1
            if vis_w > dp(20):
                _line.points = [
                    x+dp(4), y+hh-1, rx-dp(12), y+hh-1,
                    rx, y+hh-dp(12), rx, y+dp(12),
                    rx-dp(12), y, x+dp(4), y,
                ]
            else:
                _line.points = []

        panel._stage_upd = lambda: _upd(panel)
        panel.bind(pos=_upd, size=_upd)
        return panel

    def _set_stage_panel_color(self, panel, color_hex: str):
        panel._stage_border_hex = color_hex
        if hasattr(panel, "_stage_bd_col"):
            panel._stage_bd_col.rgba   = T.k(color_hex, 0.06)
        if hasattr(panel, "_stage_bg_col"):
            panel._stage_bg_col.rgba   = T.k(color_hex, 0.018)
        if hasattr(panel, "_stage_line_col"):
            panel._stage_line_col.rgba = T.k(color_hex)
        if hasattr(panel, "_stage_upd"):
            panel._stage_upd()

    # ── DC stage ──────────────────────────────────────────────────────────────

    def _build_dc_stage(self):
        box = self._mk_stage_panel(T.GOLD_DK, 90)

        num_row = MDBoxLayout(spacing=dp(6), size_hint_y=None, height=dp(56))
        prefix = MDLabel(
            text="Wound DC:",
            bold=True, theme_text_color="Custom", text_color=T.k(T.WHITE),
            font_style="H5", adaptive_width=True,
            size_hint=(None, None), height=dp(56), halign="left", valign="middle")
        self._enc_dc_num = MDLabel(
            text="--", bold=True, markup=True,
            theme_text_color="Custom", text_color=T.k(T.WHITE),
            font_style="H5", size_hint_x=1, size_hint_y=None, height=dp(56),
            halign="left", valign="middle")
        num_row.add_widget(prefix)
        num_row.add_widget(self._enc_dc_num)
        box.add_widget(num_row)

        self._dc_calc_lbl = MDLabel(
            text="", theme_text_color="Custom",
            text_color=T.k(T.TEXT_DIM), font_style="Caption",
            size_hint_y=None, height=dp(18), opacity=0)
        self._dc_calc_lbl.bind(
            width=lambda inst, v: setattr(inst, "text_size", (v, None)),
            texture_size=lambda inst, sz: setattr(inst, "height", max(dp(18), sz[1])),
        )
        box.add_widget(self._dc_calc_lbl)

        self._dc_stage_box = box

    # ── Save stage ────────────────────────────────────────────────────────────

    def _build_save_stage(self):
        box = self._mk_stage_panel(T.BLOOD, 100)

        num_row = MDBoxLayout(spacing=dp(6), size_hint_y=None, height=dp(56))
        prefix = MDLabel(
            text="CON Saving Throw:",
            bold=True, theme_text_color="Custom", text_color=T.k(T.WHITE),
            font_style="H5", adaptive_width=True,
            size_hint=(None, None), height=dp(56), halign="left", valign="middle")
        self._enc_roll_num = MDLabel(
            text="--", bold=True, markup=True,
            theme_text_color="Custom", text_color=T.k(T.WHITE),
            font_style="H5", size_hint_x=1, size_hint_y=None, height=dp(56),
            halign="left", valign="middle")
        num_row.add_widget(prefix)
        num_row.add_widget(self._enc_roll_num)
        box.add_widget(num_row)

        self._roll_info_lbl = MDLabel(
            text="", theme_text_color="Custom",
            text_color=T.k(T.TEXT_DIM), font_style="Caption",
            size_hint_y=None, height=dp(18), opacity=0)
        self._roll_info_lbl.bind(
            width=lambda inst, v: setattr(inst, "text_size", (v, None)),
            texture_size=lambda inst, sz: setattr(inst, "height", max(dp(18), sz[1])),
        )
        box.add_widget(self._roll_info_lbl)

        self._outcome_lbl = MDLabel(
            text="", bold=True,
            theme_text_color="Custom", text_color=T.k(T.WHITE),
            font_style="H5", size_hint_y=None, height=dp(44), opacity=0,
            halign="left", valign="middle")
        self._outcome_lbl.bind(size=lambda inst, *_: setattr(inst, "text_size", inst.size))
        box.add_widget(self._outcome_lbl)

        self._save_stage_box = box

    # ── Sanity stage ──────────────────────────────────────────────────────────

    def _build_sanity_stage(self):
        box = self._mk_stage_panel(T.PURPLE_LT, 100)

        san_row = MDBoxLayout(spacing=dp(6), size_hint_y=None, height=dp(56))
        san_prefix = MDLabel(
            text="Sanity Roll:",
            bold=True, theme_text_color="Custom", text_color=T.k(T.WHITE),
            font_style="H5", adaptive_width=True,
            size_hint=(None, None), height=dp(56), halign="left", valign="middle")
        self._san_num_lbl = MDLabel(
            text="--", bold=True, markup=True,
            theme_text_color="Custom", text_color=T.k(T.WHITE),
            font_style="H5", size_hint_x=1, size_hint_y=None, height=dp(56),
            halign="left", valign="middle")
        san_row.add_widget(san_prefix)
        san_row.add_widget(self._san_num_lbl)
        box.add_widget(san_row)

        self._san_info_lbl = MDLabel(
            text="", theme_text_color="Custom",
            text_color=T.k(T.TEXT_DIM), font_style="Caption",
            size_hint_y=None, height=dp(18), opacity=0)
        self._san_info_lbl.bind(
            width=lambda inst, v: setattr(inst, "text_size", (v, None)),
            texture_size=lambda inst, sz: setattr(inst, "height", max(dp(18), sz[1])),
        )
        box.add_widget(self._san_info_lbl)

        self._san_stage_box = box

    # ── Wound stage ───────────────────────────────────────────────────────────

    def _build_wound_stage(self):
        """Auto-populated wound result panel — no user input required."""
        box = self._mk_stage_panel(T.BLOOD, 120)

        self._wnd_type_lbl = MDLabel(
            text="", bold=True, markup=True,
            theme_text_color="Custom", text_color=T.k(T.TEXT_BRIGHT),
            font_style="Subtitle1", size_hint_y=None, adaptive_height=True,
            halign="left", valign="middle")
        self._wnd_type_lbl.bind(
            width=lambda inst, v: setattr(inst, "text_size", (v, None)),
            texture_size=lambda inst, sz: setattr(inst, "height", max(dp(26), sz[1])),
        )
        box.add_widget(self._wnd_type_lbl)

        self._wnd_name_lbl = MDLabel(
            text="", bold=True,
            theme_text_color="Custom", text_color=T.k(T.TEXT_BRIGHT),
            font_style="Body1", size_hint_y=None, adaptive_height=True, opacity=0)
        self._wnd_name_lbl.bind(
            width=lambda inst, v: setattr(inst, "text_size", (v, None)),
            texture_size=lambda inst, sz: setattr(inst, "height", max(dp(22), sz[1])),
        )
        box.add_widget(self._wnd_name_lbl)

        self._wnd_effect_lbl = MDLabel(
            text="", markup=True,
            theme_text_color="Custom", text_color=T.k(T.TEXT_DIM),
            font_style="Body2", size_hint_y=None, adaptive_height=True)
        self._wnd_effect_lbl.bind(
            width=lambda inst, v: setattr(inst, "text_size", (v, None)),
            texture_size=lambda inst, sz: setattr(inst, "height", max(dp(24), sz[1])),
        )
        box.add_widget(self._wnd_effect_lbl)

        self._wnd_sanity_lbl = MDLabel(
            text="", markup=True,
            theme_text_color="Custom", text_color=T.k(T.PURPLE_LT),
            font_style="Caption", size_hint_y=None, height=dp(18), opacity=0)
        self._wnd_sanity_lbl.bind(
            width=lambda inst, v: setattr(inst, "text_size", (v, None)),
            texture_size=lambda inst, sz: setattr(inst, "height", max(dp(18), sz[1])),
        )
        box.add_widget(self._wnd_sanity_lbl)

        self._wnd_exh_lbl = MDLabel(
            text="", markup=True,
            theme_text_color="Custom", text_color=T.k(T.GOLD_LT),
            font_style="Caption", size_hint_y=None, height=dp(18), opacity=0)
        self._wnd_exh_lbl.bind(
            width=lambda inst, v: setattr(inst, "text_size", (v, None)),
            texture_size=lambda inst, sz: setattr(inst, "height", max(dp(18), sz[1])),
        )
        box.add_widget(self._wnd_exh_lbl)

        self._wnd_stage_box = box

    # ── Build: Active Wounds Card (kept for reference; no longer added to layout) ─
    # Minor/major list boxes and their header are now inside _build_encounter_section.
    def _build_active_wounds_card(self) -> BorderCard:
        return BorderCard(border_hex=T.BLOOD)

    # ── Build: Add Wound Card (Page 1) ────────────────────────────────────────

    def _build_add_wound_card(self) -> BorderCard:
        card = BorderCard(border_hex=T.BLOOD)
        card.add_widget(SectionLabel("ADD WOUND", color_hex=T.BLOOD))

        rows = [
            ("MINOR WOUND", "1d4 Sanity loss", T.WOUND_MIN, "minor"),
            ("MAJOR WOUND", "2d4 Sanity loss", T.BLOOD, "major"),
        ]
        for i, (title, subtitle, color, severity) in enumerate(rows):
            default_text = f"Pick a {title.lower()}"

            row_box = MDBoxLayout(
                orientation="vertical",
                adaptive_height=True,
                spacing=dp(6))
            tr = MDBoxLayout(size_hint_y=None, height=dp(22), spacing=dp(8))
            tr.add_widget(MDLabel(
                text=title, bold=True, font_style="Caption",
                theme_text_color="Custom", text_color=T.k(color)))
            tr.add_widget(MDLabel(
                text=f"({subtitle})", font_style="Overline",
                theme_text_color="Custom", text_color=T.k(T.TEXT_DIM)))
            row_box.add_widget(tr)

            picker = PickerListItem(
                on_tap=lambda wid, s=severity: self._open_wound_menu(s, wid),
                accent_hex=color,
            )
            picker.title_text = default_text
            picker.is_placeholder = True
            control_row = MDBoxLayout(
                orientation="horizontal",
                size_hint_y=None,
                spacing=dp(8),
            )
            control_row.bind(minimum_height=lambda inst, val: setattr(inst, "height", val))
            control_row.add_widget(picker)
            apply_slot = AnchorLayout(
                anchor_x="right",
                anchor_y="center",
                size_hint_x=None,
                size_hint_y=None,
                width=dp(88),
            )
            picker.bind(height=lambda inst, val, slot=apply_slot: setattr(slot, "height", val))
            apply_slot.height = picker.height
            apply_slot.add_widget(MDRaisedButton(
                text="APPLY",
                md_bg_color=T.k(color),
                size_hint_y=None, height=dp(44),
                size_hint_x=None, width=dp(80),
                on_release=lambda *_, s=severity: self._apply_wound(s)))
            control_row.add_widget(apply_slot)
            row_box.add_widget(control_row)
            card.add_widget(row_box)
            self._add_preview[severity] = {
                "picker": picker,
                "default_text": default_text,
            }

            if i < len(rows) - 1:
                card.add_widget(Divider(color_hex=T.BORDER))

        return card

    def _open_wound_menu(self, severity: str, anchor):
        table = MINOR_WOUND_TABLE if severity == "minor" else MAJOR_WOUND_TABLE
        items = [
            {
                "text": f"{roll}. {desc}",
                "viewclass": "OneLineListItem",
                "on_release": (
                    lambda r=roll, d=desc, e=effect, s=severity:
                    self._on_wound_select(s, r, d, e)
                ),
            }
            for roll, desc, effect in table
        ]
        menu = MDDropdownMenu(caller=anchor, items=items,
                              width_mult=4, max_height=dp(300))
        menu.open()
        setattr(self, f"_menu_{severity}", menu)

    def _on_wound_select(self, severity: str, roll, desc: str, effect: str):
        m = getattr(self, f"_menu_{severity}", None)
        if m: m.dismiss()
        for s, pair in self._add_preview.items():
            if s != severity:
                pair["picker"].show_placeholder(pair["default_text"], animate=True)
                self._pending_wound.pop(s, None)
        self._pending_wound[severity] = (roll, desc, effect)
        pair = self._add_preview.get(severity)
        if pair:
            summary = self._wound_roll_preview_text(severity, roll)
            pair["picker"].title_text = desc
            pair["picker"].subtitle_text = summary
            pair["picker"].detail_body = effect
            pair["picker"].is_placeholder = False
            pair["picker"].set_open(True, animate=True)

    def _apply_wound(self, severity: str):
        pending = self._pending_wound.pop(severity, None)
        if not pending:
            return
        roll, desc, effect = pending
        pair = self._add_preview.get(severity)
        if pair:
            pair["picker"].show_placeholder(pair["default_text"], animate=False)
        self._add_wound(severity, desc, effect)

    def _build_rules_panel(self) -> BorderCard:
        wrapper = BorderCard(border_hex=T.BLOOD)
        sec = ExpandableSection("WOUND RULES", accent_hex=T.BLOOD_LT)
        populate_rules_section(sec, WOUND_RULES_TEXT, T.BLOOD_LT)
        wrapper.add_widget(sec)
        return wrapper

    def _wound_roll_preview_text(self, severity: str, roll) -> str:
        label = "Minor Wound" if severity == "minor" else "Major Wound"
        sanity_loss = "1d4 Sanity Loss" if severity == "minor" else "2d4 Sanity Loss"
        return f"{label} | Roll: {roll} | {sanity_loss}"

    # ── Internal helpers ──────────────────────────────────────────────────────

    def _app(self): return App.get_running_app()

    def _push_undo(self):
        app = self._app(); app.undo_stack.push(app.state, app.fm)

    def _save(self):
        app = self._app()
        app.save_manager.save(app.state, app.fm, app.char_name, app.enc_history)

    def _log(self, msg):
        app = self._app(); app.enc_history.append(msg)
        if hasattr(app, "session_log"): app.session_log.add_entry(msg)

    def _snack(self, msg, color=T.BG_CARD):
        MDSnackbar(
            MDLabel(text=msg, theme_text_color="Custom", text_color=(1, 1, 1, 1)),
            md_bg_color=T.k(color), duration=2.5
        ).open()

    def _sync_panel_height(self, panel):
        panel.height = panel.minimum_height

    def _expand_panel(self, detail: MDBoxLayout):
        detail.size_hint_y = None
        detail.opacity     = 1
        Clock.schedule_once(lambda dt, d=detail: self._sync_panel_height(d))

    def _collapse_panel(self, detail: MDBoxLayout):
        detail.size_hint_y = None
        detail.height      = 0
        detail.opacity     = 0

    def _kind_label(self, kind: str) -> str:
        return {"short": "Short-Term", "long": "Long-Term",
                "indefinite": "Indefinite"}.get(kind, "Unknown")

    def _kind_color(self, kind: str) -> str:
        return {"short": T.M_SHORT, "long": T.M_LONG,
                "indefinite": T.M_INDEF}.get(kind, T.PURPLE_LT)

    def _threshold_suffix_for_notif(self, threshs, pre_kind_counts) -> str:
        suffix = ""
        for _, kind in threshs:
            if kind == "zero":
                continue
            c = self._kind_color(kind)
            if pre_kind_counts.get(kind, 0) > 0 and kind != "indefinite":
                suffix = (f" [color={c}][font=Symbols]\u2192[/font]"
                          f" Cured {self._kind_label(kind)} Insanity[/color]")
            elif pre_kind_counts.get(kind, 0) > 0 and kind == "indefinite":
                continue
            else:
                suffix = (f" [color={c}][font=Symbols]\u2192[/font]"
                          f" {self._kind_label(kind)} Insanity[/color]")
        return suffix

    def _handle_thresholds(self, threshs):
        app = self._app()
        sanity_tab = app._sanity_tab
        extra_actions = []
        deferred_notifications = []
        for label, kind in threshs:
            if kind == "zero":
                self._log(f"WARNING: {label}")
                deferred_notifications.append(
                    lambda lbl=label: app.notify_event(lbl, "sanity", T.BLOOD)
                )
                continue
            color = self._kind_color(kind)
            existing = [m for m in reversed(app.state.madnesses) if m.kind == kind]
            if existing and kind != "indefinite":
                cured = existing[0]
                app.state.madnesses.remove(cured)
                cured_name = cured.name if cured.name else cured.kind_label
                self._log(f"THRESHOLD re-crossed (wound): {label} - cured {cured_name}")
            elif existing and kind == "indefinite":
                self._log(f"THRESHOLD re-crossed (wound): {label}")
            else:
                m = app.state.add_madness(kind)
                self._log(
                    f"THRESHOLD (wound): {label} > {m.kind_label} insanity: "
                    f"[{m.roll_range}] {m.name}"
                )
                extra_actions.append(
                    ("INSANITY >", "sanity",
                     lambda ee=m: sanity_tab.open_madness(ee))
                )
                deferred_notifications.append(
                    lambda entry=m, c=color: app.notify_event(
                        f"{entry.kind_label} Insanity: {entry.name}",
                        "sanity", c,
                        action_cb=lambda ee=entry: sanity_tab.open_madness(ee)
                    )
                )
        return extra_actions, deferred_notifications

    def _clear_wound_details(self):
        if self._active_minor_card:
            self._active_minor_card.set_open(False, animate=False)
            self._active_minor_card = None
        if self._active_major_card:
            self._active_major_card.set_open(False, animate=False)
            self._active_major_card = None
        self._sel_minor = None
        self._sel_major = None

    # ── Encounter tab layout & animation helpers ──────────────────────────────

    def _stage_history_keys(self):
        return [k for k in ("dc", "save", "sanity", "wound")
                if self._enc_stage_tabs.get(k) and self._enc_stage_tabs[k]._shown]

    def _enc_stage_child(self, key: str):
        return {
            "dc":     self._dc_stage_box,
            "save":   self._save_stage_box,
            "sanity": self._san_stage_box,
            "wound":  self._wnd_stage_box,
        }[key]

    def _tab_stack_y(self, idx: int) -> float:
        s       = self._enc_flow_shell
        history = self._stage_history_keys()
        n       = max(1, len(history))
        active  = self._enc_active_stage if self._enc_active_stage in history else None
        aidx    = history.index(active) if active else -1
        ch      = max(0, self._enc_content.height)
        gap     = dp(8) if aidx >= 0 else 0
        rail_h  = _EncTab._TOP_PAD + n*_EncTab._TAB_H + (n-1)*_EncTab._TAB_GAP
        h       = max(s.height, rail_h + (ch + gap if aidx >= 0 else 0))
        extra   = ch + gap if aidx >= 0 and idx > aidx else 0
        local_y = h - _EncTab._TOP_PAD - (idx+1)*_EncTab._TAB_H - idx*_EncTab._TAB_GAP - extra
        return s.y + local_y

    def _tab_spawn_y(self, tab: _WoundEncTab) -> float:
        s = self._enc_flow_shell
        return s.y + s.height + tab.height

    def _sync_shell_layout(self, *_):
        s = self._enc_flow_shell
        if s is None:
            return
        content_w = max(0, s.width - EncounterListItem._CONTENT_RIGHT_INSET)
        history   = self._stage_history_keys()
        n         = len(history)
        content_h = max(0, self._enc_content.minimum_height)
        active    = self._enc_active_stage if self._enc_active_stage in history else None
        aidx      = history.index(active) if active else -1
        gap       = dp(8) if aidx >= 0 else 0
        tabs_h    = (_EncTab._TOP_PAD + n*_EncTab._TAB_H + (n-1)*_EncTab._TAB_GAP) if n else 0
        shell_h   = tabs_h + (gap + content_h if aidx >= 0 else 0)
        self._enc_flow_shell.height = max(shell_h, tabs_h)
        self._enc_content.width     = content_w
        self._enc_content.height    = content_h
        if aidx >= 0:
            tabs_above = (_EncTab._TOP_PAD
                          + aidx*(_EncTab._TAB_H + _EncTab._TAB_GAP) + _EncTab._TAB_H)
            self._enc_content.y = s.y + shell_h - tabs_above - gap - content_h
            self._enc_content.x = s.x + dp(1)
        self._layout_stage_tabs(animated=False)

    def _on_enc_content_min_height(self):
        if self._enc_height_sync_paused:
            return
        self._sync_shell_height()

    def _sync_shell_height(self, *_, animate_tabs: bool = False):
        h_content = self._enc_content.minimum_height
        active    = self._enc_active_stage
        if active:
            h_content = max(h_content, getattr(
                self._enc_stage_child(active), "_min_stage_height", 0))
        n      = len(self._stage_history_keys())
        tabs_h = (_EncTab._TOP_PAD + n*_EncTab._TAB_H + (n-1)*_EncTab._TAB_GAP) if n else 0
        gap    = dp(8) if active else 0
        h      = tabs_h + gap + h_content
        self._enc_content.height    = h_content
        self._enc_flow_shell.height = h
        self._layout_stage_tabs(animated=animate_tabs)

    def _layout_stage_tabs(self, animated: bool = False):
        s = self._enc_flow_shell
        for idx, key in enumerate(self._stage_history_keys()):
            tab = self._enc_stage_tabs[key]
            tx  = s.x
            ty  = self._tab_stack_y(idx)
            if animated:
                if tab._appear_pending:
                    tab._appear_pending = False
                    tab.x = tx; tab.y = ty
                    tab.appear(rail_x=s.x)
                else:
                    Animation.cancel_all(tab, "x", "y")
                    Animation(x=tx, y=ty, duration=0.22, t="in_out_cubic").start(tab)
            else:
                tab.x = tx; tab.y = ty

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
            tab.opacity         = 0
            tab._shown          = False
            tab._appear_pending = False
            tab._tab_state      = None
            tab._dim_pending    = False
            tab._commit_done    = False
            tab._side_live      = False
            tab._clear_stroke_art()
            tab._stroke_col.a           = 0
            tab._side_divider_rect.size = (0, 0)
            tab._side_divider_col.a     = 0
            tab._side_rect.size         = (0, 0)
            tab._side_line.points       = []
            tab._side_col.a             = 0
            tab.x = self._enc_flow_shell.x
            tab.y = self._tab_spawn_y(tab)
            tab._fill_col.rgba          = (0, 0, 0, 0)
            tab._accent_col.rgba        = (0, 0, 0, 0)
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
                tab.set_state("current"); tab.opacity = 1.0
            elif key == active:
                tab.set_state("active"); tab.opacity = 1.0
            else:
                tab.set_state("done_new"); tab.opacity = 1.0
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
        tab = self._enc_stage_tabs.get(key)
        if tab is None or not tab._shown:
            if on_complete: on_complete()
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
        panel.opacity   = 1.0
        if hasattr(panel, "_stage_upd"): panel._stage_upd()
        start_t = Clock.get_boottime()

        def _tick(dt):
            prog  = min(1.0, (Clock.get_boottime() - start_t) / max(0.001, duration))
            eased = 1.0 - pow(1.0 - prog, 3)
            panel._reveal_t = eased; panel.opacity = 1.0
            if hasattr(panel, "_stage_upd"): panel._stage_upd()
            if prog >= 1.0:
                panel._reveal_t = 1.0; panel._reveal_evt = None; return False
            return True

        panel._reveal_evt = Clock.schedule_interval(_tick, 1/60)

    def _animate_stage_retract(self, panel, duration: float = 0.26, on_complete=None):
        if getattr(panel, "_reveal_evt", None):
            panel._reveal_evt.cancel()
            panel._reveal_evt = None
        start_t        = Clock.get_boottime()
        start_reveal_t = max(0.0, min(1.0, getattr(panel, "_reveal_t", 1.0)))

        def _tick(dt):
            prog  = min(1.0, (Clock.get_boottime() - start_t) / max(0.001, duration))
            eased = pow(prog, 3)
            panel._reveal_t = start_reveal_t * (1.0 - eased)
            panel.opacity   = 1.0
            if hasattr(panel, "_stage_upd"): panel._stage_upd()
            if prog >= 1.0:
                panel._reveal_t = 0.0; panel.opacity = 1.0
                if hasattr(panel, "_stage_upd"): panel._stage_upd()
                panel._reveal_evt = None
                if on_complete: on_complete()
                return False
            return True

        panel._reveal_evt = Clock.schedule_interval(_tick, 1/60)

    def _open_encounter_stage(self, key: str, animate: bool = True):
        panels = {
            "dc":     self._dc_stage_box,
            "save":   self._save_stage_box,
            "sanity": self._san_stage_box,
            "wound":  self._wnd_stage_box,
        }
        target = panels[key]

        if not animate:
            for k, child in panels.items():
                if k != key and child.parent is self._enc_content:
                    self._enc_content.remove_widget(child)
            if target.parent is not self._enc_content:
                target._reveal_t = 1.0; target.opacity = 1
                if hasattr(target, "_stage_upd"): target._stage_upd()
                self._enc_content.add_widget(target)
            self._enc_active_stage = key
            self._refresh_tab_highlights()
            Clock.schedule_once(lambda dt: self._sync_shell_height(), 0)
            return

        old_panel = next(
            (child for k, child in panels.items()
             if k != key and child.parent is self._enc_content), None)

        def _do_swap(*_):
            self._enc_height_sync_paused = False
            if old_panel is not None and old_panel.parent is self._enc_content:
                self._enc_content.remove_widget(old_panel)
                old_panel.opacity = 1.0
            if target.parent is not self._enc_content:
                target._reveal_t = 0.0; target.opacity = 1.0
                if hasattr(target, "_stage_upd"): target._stage_upd()
                self._enc_content.add_widget(target)
            self._enc_active_stage = key
            self._refresh_tab_highlights(layout_tabs=False)
            Clock.schedule_once(lambda dt: self._sync_shell_height(animate_tabs=True), 0)
            Clock.schedule_once(
                lambda dt: self._animate_stage_reveal(target),
                self._STAGE_BOX_EXPAND_DELAY)

        if old_panel is not None:
            self._enc_height_sync_paused = True
            self._animate_stage_retract(old_panel, on_complete=_do_swap)
        else:
            _do_swap()

    def _reset_enc_ui(self):
        self._set_stage_panel_color(self._dc_stage_box,   T.GOLD_DK)
        self._set_stage_panel_color(self._save_stage_box, T.BLOOD)
        self._set_stage_panel_color(self._san_stage_box,  T.PURPLE_LT)
        self._set_stage_panel_color(self._wnd_stage_box,  T.BLOOD)

        self._enc_dc_num.text       = "--"
        self._enc_dc_num.text_color = T.k(T.WHITE)
        self._dc_calc_lbl.text      = ""
        self._dc_calc_lbl.opacity   = 0

        self._enc_roll_num.text       = "--"
        self._enc_roll_num.text_color = T.k(T.WHITE)
        self._roll_info_lbl.text      = ""
        self._roll_info_lbl.opacity   = 0
        self._outcome_lbl.text        = ""
        self._outcome_lbl.height      = dp(44)
        self._outcome_lbl.opacity     = 0

        self._san_num_lbl.text       = "--"
        self._san_num_lbl.text_color = T.k(T.WHITE)
        self._san_info_lbl.text      = ""
        self._san_info_lbl.opacity   = 0

        self._wnd_type_lbl.text      = ""
        self._wnd_name_lbl.text      = ""
        self._wnd_name_lbl.opacity   = 0
        self._wnd_effect_lbl.text    = ""
        self._wnd_sanity_lbl.text    = ""
        self._wnd_sanity_lbl.opacity = 0
        self._wnd_exh_lbl.text       = ""
        self._wnd_exh_lbl.opacity    = 0

        self._enc_active_stage = None
        for key in self._enc_stage_tabs:
            self._enc_stage_tabs[key]._cap_hex = None
        for key in self._enc_stage_tabs:
            self._set_stage_available(key, False)

    def _show_roll_panel(self, on_ready=None):
        shell = self._enc_flow_shell
        shell.height  = 0
        shell.opacity = 0
        self._enc_content.height = 0
        self._reset_enc_ui()

        def _do_anim(dt):
            if on_ready: on_ready()
            self._sync_shell_height()
            Animation(opacity=1, duration=0.22, t="out_quart").start(shell)

        Clock.schedule_once(_do_anim, 0)

    # ── Spinning-number animation ─────────────────────────────────────────────

    def _spin_number(self, lbl, target: int, max_val: int, on_land):
        intervals = [0.022]*12 + [0.065]*5 + [0.17]*4
        n_frames  = len(intervals)
        td        = ((target - 1) % max_val) + 1
        s0        = (td - 1 - n_frames) % max_val
        sv        = s0 + 1
        t         = 0.0
        for i, iv in enumerate(intervals):
            t += iv
            num = ((sv - 1 + i) % max_val) + 1
            Clock.schedule_once(
                (lambda n: lambda dt: setattr(lbl, "text", str(n)))(num), t)
        Clock.schedule_once(on_land, t + 0.30)
        return t

    def _enc_timestamp(self) -> str:
        from datetime import datetime
        now  = datetime.now()
        hour = now.hour % 12 or 12
        ampm = "am" if now.hour < 12 else "pm"
        return f"{hour}:{now.minute:02d}{ampm}"

    # ── Encounter: auto-flow DC → SAVE → SANITY → WOUND ─────────────────────

    def _on_wound_encounter(self, *_):
        app = self._app()

        if self._enc.phase != WoundEncPhase.IDLE:
            self._snack("Encounter already active.", T.BORDER); return

        try:
            dmg = safe_int(self._dmg_field.text or "0", lo=0)
        except Exception:
            self._snack("Enter valid damage.", T.BORDER); return

        actual_dc = max(10, dmg // 2)
        con_mod   = app.state.con_mod
        if getattr(app, 'con_adv', False):
            rolls    = roll_d(20, 2)
            d20      = max(rolls)
            roll_str = f"D20 Adv({rolls[0]},{rolls[1]})\u2192{d20}"
        else:
            d20      = roll_d(20)[0]
            roll_str = f"D20({d20})"
        con_save = d20 + con_mod

        # Auto-determine outcome
        margin = con_save - actual_dc
        if margin >= 5:
            outcome = "pass5"
        elif margin >= 0:
            outcome = "pass"
        elif margin > -5:
            outcome = "fail"
        else:
            outcome = "fail5"

        is_pass5 = outcome == "pass5"
        is_fail5 = outcome == "fail5"
        is_pass  = outcome == "pass"

        # Roll wound and sanity upfront (except pass5)
        if not is_pass5:
            wound_sev = "minor" if is_pass else "major"
            wound_roll, wound_desc, wound_effect = roll_random_wound(wound_sev)
            n_dice     = 1 if is_pass else 2
            san_rolls  = roll_d(4, n_dice)
            san_loss   = sum(san_rolls)
        else:
            wound_sev  = ""
            wound_roll = 0
            wound_desc = ""
            wound_effect = ""
            san_rolls  = []
            san_loss   = 0

        # Store pending state for _do_auto_complete
        self._pending_outcome      = outcome
        self._pending_wound_desc   = wound_desc
        self._pending_wound_effect = wound_effect
        self._pending_wound_sev    = wound_sev
        self._pending_wound_roll   = wound_roll
        self._pending_sanity_loss  = san_loss
        self._pending_san_rolls    = san_rolls

        self._enc.dc           = actual_dc
        self._enc.damage_taken = dmg
        self._enc.roll_total   = con_save
        self._enc.con_mod_used = con_mod
        self._enc.phase        = WoundEncPhase.AWAITING_SAVE

        self._current_enc_num += 1
        self._log("=== WOUND ENCOUNTER ===")
        self._log(f"Damage: {dmg}  |  DC: {actual_dc}")
        self._log(f"CON Save: {roll_str} + {con_mod:+d} = {con_save} vs DC {actual_dc}")
        self._log(f"Outcome: {outcome.upper()}")

        self._wenc_btn.disabled = True
        passed_roll = con_save >= actual_dc

        self._enc_roll_info = (
            f"CON Save: {roll_str} + CON({con_mod:+d}) = {con_save}  VS  DC {actual_dc}"
        )

        # Live EncounterListItem (blood-red rail for wound encounters)
        new_item = EncounterListItem(accent_hex=T.BLOOD)
        new_item._on_open_cb = self._collapse_other_wound_enc
        self._wound_enc_items_box.add_widget(
            new_item, index=len(self._wound_enc_items_box.children))
        new_item.start_live(
            "WOUND ENCOUNTER", 1,
            self._enc_flow_shell,
            subtitle=f"Encounter {self._current_enc_num}  |  {self._enc_timestamp()}",
        )
        self._enc_item = new_item

        _spin_intervals = [0.022]*12 + [0.065]*5 + [0.17]*4
        _spin_t    = sum(_spin_intervals)
        _sweep_dur = _spin_t + 0.30 + 0.30 + 0.22

        def _on_ready():
            # ── Stage 1: DC ───────────────────────────────────────────────────
            self._set_stage_available("dc", True, refresh_highlights=False)
            self._open_encounter_stage("dc", animate=True)

            def _start_dc_spin(dt):
                dc_max = max(30, actual_dc + 5)

                def _dc_land(dt2):
                    self._enc_dc_num.text = str(actual_dc)
                    base_sz = self._enc_dc_num.font_size
                    (Animation(font_size=base_sz*1.22, duration=0.06, t="out_quad") +
                     Animation(font_size=base_sz, duration=0.20,
                               t="out_back")).start(self._enc_dc_num)
                    self._dc_calc_lbl.text = (
                        f"Damage {dmg} \u00f7 2 = {dmg // 2}  (min. 10)"
                    )
                    Animation(opacity=1, duration=0.18,
                              t="out_quad").start(self._dc_calc_lbl)
                    Clock.schedule_once(lambda dt: self._sync_shell_height(), 0.02)

                def _after_dc_commit():
                    # ── Stage 2: SAVE ─────────────────────────────────────────
                    def _open_save(dt):
                        self._set_stage_available("save", True, refresh_highlights=False)
                        self._open_encounter_stage("save", animate=True)
                        save_after_land_delay = 0.84

                        # ── Wrap-around: fire play_tab_commit as soon as the
                        # tab is fully extended (appear = 0.32 s). Size the
                        # total duration so the top stroke reaches the corner
                        # when the save result lands, then let the remaining
                        # side+bottom path finish at that same speed before the
                        # next stage advances.
                        # Start the standard sweep late enough that the top edge
                        # lands exactly on the save-result reveal.
                        def _begin_wrap(dt_bw):
                            nonlocal save_after_land_delay
                            top_w = max(dp(1), _EncTab._TAB_W - _EncTab._RAIL_W)
                            total_path = top_w + _EncTab._TAB_H + top_w
                            # Phase 1 lasts from tab-extend to save-result land.
                            land_time = self._TAB_SETTLE_DELAY + _spin_t + 0.30
                            normal_trace_dur = _sweep_dur * 0.65
                            normal_post_top_dur = normal_trace_dur * (
                                (total_path - top_w) / total_path
                            )
                            top_phase_dur = max(0.02, land_time - 0.32)
                            trace_dur = top_phase_dur + normal_post_top_dur
                            save_after_land_delay = max(0.02, trace_dur - top_phase_dur)
                            self._play_tab_commit(
                                "save",
                                total_duration=trace_dur,
                                trace_duration=trace_dur,
                                top_phase_duration=top_phase_dur,
                                on_complete=None)
                        Clock.schedule_once(_begin_wrap, 0.32)

                        def _start_save_spin(dt2):
                            def _save_land(dt3):
                                self._enc_roll_num.text = str(con_save)
                                base_sz   = self._enc_roll_num.font_size
                                final_col = T.k(self._wound_outcome_color(outcome))
                                (Animation(font_size=base_sz*1.22, duration=0.06,
                                           t="out_quad") +
                                 Animation(font_size=base_sz, duration=0.20,
                                           t="out_back")).start(self._enc_roll_num)
                                Animation(text_color=final_col, duration=0.25,
                                          t="out_quad").start(self._enc_roll_num)
                                self._roll_info_lbl.text = self._enc_roll_info
                                Animation(opacity=1, duration=0.18,
                                          t="out_quad").start(self._roll_info_lbl)
                                Clock.schedule_once(
                                    lambda dt: self._sync_shell_height(), 0.02)

                                # The wrap animation was sized so Phase 1 ends exactly
                                # at spin-land — just update the cap colour so the next
                                # tick uses the outcome colour for the side-tab, then
                                # schedule stage advancement at the same 0.84 s window.
                                # Phase 1 ends at save-result land. Update the cap
                                # colour and reveal the verdict at that same moment
                                # so the side-tab colour doesn't telegraph the result
                                # ahead of the text, then wait for the remaining
                                # side+bottom path before advancing.
                                stab = self._enc_stage_tabs["save"]
                                stab._cap_hex    = self._wound_outcome_color(outcome)
                                stab._commit_cb  = None  # stage advances via Clock below

                                def _show_outcome(dt4):
                                    self._outcome_lbl.text = self._wound_outcome_label(outcome)
                                    self._outcome_lbl.text_color = T.k(
                                        self._wound_outcome_color(outcome))
                                    Animation(opacity=1, duration=0.22,
                                              t="out_cubic").start(self._outcome_lbl)
                                    Clock.schedule_once(
                                        lambda dt: self._sync_shell_height(), 0.02)

                                Clock.schedule_once(_show_outcome, 0)
                                Clock.schedule_once(
                                    lambda dt4: _after_save_commit(),
                                    save_after_land_delay + 0.02)

                            def _after_save_commit():
                                if is_pass5:
                                    # pass5 — no wound/sanity; complete directly
                                    Clock.schedule_once(
                                        lambda dt: self._do_auto_complete(), 0.80)
                                else:
                                    # ── Stage 3: SANITY ───────────────────────
                                    Clock.schedule_once(_start_sanity, 0.10)

                            self._spin_number(self._enc_roll_num, con_save, 20, _save_land)

                        Clock.schedule_once(_start_save_spin, self._TAB_SETTLE_DELAY)

                    Clock.schedule_once(_open_save, 0.10)

                self._play_tab_commit("dc", total_duration=_sweep_dur,
                                      on_complete=_after_dc_commit)
                self._spin_number(self._enc_dc_num, actual_dc, dc_max, _dc_land)

            Clock.schedule_once(_start_dc_spin, self._TAB_SETTLE_DELAY)

            # ── Stage 3: SANITY (non-pass5) ───────────────────────────────────
            _san_sweep = _spin_t + 0.30 + 0.22 + 0.25
            san_total  = san_loss
            san_str    = "+".join(map(str, san_rolls)) if san_rolls else str(san_loss)
            _max_val   = max(4, len(san_rolls) * 4)

            def _start_sanity(dt=None):
                self._san_num_lbl.text       = "--"
                self._san_num_lbl.text_color = T.k(T.WHITE)
                self._san_info_lbl.text      = ""
                self._san_info_lbl.opacity   = 0

                self._set_stage_available("sanity", True, refresh_highlights=False)
                self._open_encounter_stage("sanity", animate=True)

                def _san_land(dt2):
                    self._san_num_lbl.text = str(san_total)
                    base_sz = self._san_num_lbl.font_size
                    (Animation(font_size=base_sz*1.22, duration=0.06, t="out_quad") +
                     Animation(font_size=base_sz, duration=0.20,
                               t="out_back")).start(self._san_num_lbl)
                    Animation(text_color=T.k(T.PURPLE_LT), duration=0.25,
                              t="out_quad").start(self._san_num_lbl)
                    san_info = (f"Sanity: {len(san_rolls)}d4"
                                f" ({san_str}) = {san_total}")
                    self._san_info_lbl.text = san_info
                    Animation(opacity=1, duration=0.18,
                              t="out_quad").start(self._san_info_lbl)
                    Clock.schedule_once(lambda dt: self._sync_shell_height(), 0.02)

                def _start_san_commit(dt2):
                    self._play_tab_commit(
                        "sanity", total_duration=_san_sweep,
                        on_complete=lambda: Clock.schedule_once(_start_wound, 0.30))
                    self._spin_number(
                        self._san_num_lbl, san_total, _max_val, _san_land)

                Clock.schedule_once(_start_san_commit, self._TAB_SETTLE_DELAY)

            # ── Stage 4: WOUND ────────────────────────────────────────────────
            # Match the DC stage timing so the wound card reveal, tab settle,
            # and wrap-around cadence feel identical to the first stage.
            _wnd_sweep = _sweep_dur

            def _start_wound(dt=None):
                self._populate_wound_stage(outcome, wound_desc, wound_effect,
                                           wound_roll, san_rolls, san_loss)
                self._set_stage_available("wound", True, refresh_highlights=False)
                self._open_encounter_stage("wound", animate=True)

                def _after_reveal(dt2):
                    self._play_tab_commit(
                        "wound", total_duration=_wnd_sweep,
                        on_complete=lambda: Clock.schedule_once(
                            lambda dt3: self._do_auto_complete(), 0.10))

                Clock.schedule_once(_after_reveal, self._TAB_SETTLE_DELAY)

        self._show_roll_panel(on_ready=_on_ready)

    def _collapse_other_wound_enc(self, keep_item=None):
        if not self._wound_enc_items_box:
            return True
        for item in list(self._wound_enc_items_box.children):
            if item is keep_item:
                continue
            if isinstance(item, EncounterListItem):
                if item._mode == "live":
                    continue
                if item.open_state:
                    item.set_open(False, animate=True)
            elif isinstance(item, EncounterWoundCard):
                if item.open_state:
                    item.set_open(False, animate=True)
        return True

    # ── Wound stage population helper ────────────────────────────────────────

    def _populate_wound_stage(self, outcome, wound_desc, wound_effect,
                              wound_roll, san_rolls, san_loss):
        is_pass5 = outcome == "pass5"
        is_fail5 = outcome == "fail5"
        is_pass  = outcome == "pass"

        wnd_color = T.GREEN if is_pass5 else T.WOUND_MIN if is_pass else T.BLOOD
        self._enc_stage_tabs["wound"]._cap_hex = wnd_color
        self._set_stage_panel_color(self._wnd_stage_box, wnd_color)

        if is_pass5:
            self._wnd_type_lbl.text    = f"[color={T.GREEN}]No Wound[/color]"
            self._wnd_name_lbl.opacity = 0
            self._wnd_effect_lbl.text  = (
                "CON save passed by 5 or more \u2014 no injury sustained.")
            self._wnd_sanity_lbl.opacity = 0
            self._wnd_exh_lbl.opacity    = 0
        elif is_pass:
            san_str = "+".join(map(str, san_rolls))
            self._wnd_type_lbl.text      = (
                f"[color={T.WOUND_MIN}]Minor Wound | Roll: {wound_roll}[/color]")
            self._wnd_name_lbl.text      = wound_desc
            self._wnd_name_lbl.opacity   = 1
            self._wnd_effect_lbl.text    = f"[color={T.TEXT_DIM}]{wound_effect}[/color]"
            self._wnd_sanity_lbl.text    = (
                f"Sanity Loss: 1d4 ({san_str}) = {san_loss}")
            self._wnd_sanity_lbl.opacity = 1
            self._wnd_exh_lbl.opacity    = 0
        else:
            san_str   = "+".join(map(str, san_rolls))
            sev_label = "Major Wound" + (" + Exhaustion" if is_fail5 else "")
            self._wnd_type_lbl.text      = (
                f"[color={T.BLOOD}]{sev_label} | Roll: {wound_roll}[/color]")
            self._wnd_name_lbl.text      = wound_desc
            self._wnd_name_lbl.opacity   = 1
            self._wnd_effect_lbl.text    = f"[color={T.TEXT_DIM}]{wound_effect}[/color]"
            self._wnd_sanity_lbl.text    = (
                f"Sanity Loss: 2d4 ({san_str}) = {san_loss}")
            self._wnd_sanity_lbl.opacity = 1
            self._wnd_exh_lbl.text    = (
                f"[color={T.GOLD_LT}]+1 Exhaustion[/color]" if is_fail5 else "")
            self._wnd_exh_lbl.opacity = 1 if is_fail5 else 0

    # ── Auto-complete: apply all state changes after WOUND tab commits ────────

    def _do_auto_complete(self):
        """Apply state changes and complete the encounter (fully automated)."""
        app = self._app()
        self._push_undo()

        outcome      = self._pending_outcome
        wound_desc   = self._pending_wound_desc
        wound_effect = self._pending_wound_effect
        wound_sev    = self._pending_wound_sev
        wound_roll   = self._pending_wound_roll
        sanity_loss  = self._pending_sanity_loss
        san_rolls    = self._pending_san_rolls
        is_fail5     = outcome == "fail5"
        is_pass5     = outcome == "pass5"

        # Apply wound to state
        wound_entry = None
        if not is_pass5:
            wound_entry = app.state.add_wound(wound_desc, wound_effect, wound_sev)

        # Apply exhaustion
        if is_fail5:
            app.state.exhaustion = int(clamp(app.state.exhaustion + 1, 0, 6))
        _exh = app.state.exhaustion

        # Apply sanity loss
        old_sanity = app.state.current_sanity
        pre_madness_kinds = [m.kind for m in app.state.madnesses]
        threshs    = app.state.apply_loss(sanity_loss) if sanity_loss > 0 else []
        new_sanity = app.state.current_sanity
        pct = (int(new_sanity / app.state.max_sanity * 100)
               if app.state.max_sanity else 0)
        pre_counts = {k: pre_madness_kinds.count(k)
                      for k in ("short", "long", "indefinite")}
        threshold_actions, deferred_notifs = self._handle_thresholds(threshs)
        thresh_suffix = self._threshold_suffix_for_notif(threshs, pre_counts)

        # Attach encounter record to wound entry so refresh() builds the right card
        if wound_entry is not None:
            wound_entry.enc_record = {
                "outcome":      outcome,
                "wound_desc":   wound_desc,
                "wound_sev":    wound_sev,
                "wound_effect": wound_effect,
                "wound_roll":   wound_roll,
                "dc":           self._enc.dc,
                "con_save":     self._enc.roll_total,
                "con_mod":      self._enc.con_mod_used,
                "damage_taken": self._enc.damage_taken,
                "sanity_loss":  sanity_loss,
                "san_rolls":    list(san_rolls),
                "enc_num":      self._current_enc_num,
            }

        # Log
        if is_pass5:
            self._log("Wound Encounter: PASS by 5+ - no wound")
        elif outcome == "pass":
            self._log(
                f"Wound Encounter: PASS - Minor Wound: {wound_desc} "
                f"(Roll {wound_roll}) | Sanity -{sanity_loss}")
        elif not is_fail5:
            self._log(
                f"Wound Encounter: FAIL - Major Wound: {wound_desc} "
                f"(Roll {wound_roll}) | Sanity -{sanity_loss}")
        else:
            self._log(
                f"Wound Encounter: FAIL by 5+ - Major Wound: {wound_desc} "
                f"(Roll {wound_roll}) + Exhaustion | Sanity -{sanity_loss}")

        self._save()

        result_color = (T.GREEN if is_pass5 else
                        T.WOUND_MIN if outcome == "pass" else T.BLOOD)
        _we = wound_entry

        def _fire_notifications():
            if is_pass5:
                app.notify_event(
                    "No Wound \u2014 CON save passed by 5+", "wounds", T.GREEN)
                return
            app.notify_event(
                f"{'Minor' if outcome == 'pass' else 'Major'} Wound: "
                f"[color={result_color}]{wound_desc}[/color]",
                "wounds", result_color,
                action_cb=lambda ee=_we, sv=wound_sev: self.open_wound(ee, sv)
            )
            if sanity_loss > 0:
                app.notify_event(
                    f"Sanity: [color={T.PURPLE_LT}]{old_sanity} - {sanity_loss}"
                    f" = {new_sanity} ({pct}%)[/color]{thresh_suffix}",
                    "wounds", result_color,
                    action_cb=lambda ee=_we, sv=wound_sev: self.open_wound(ee, sv),
                    extra_actions=threshold_actions
                )
            for cb in deferred_notifs:
                cb()
            if is_fail5:
                app.notify_exhaustion(_exh)

        def _do_complete(dt=None):
            app.refresh_all(after_sanity=_fire_notifications)
            Clock.schedule_once(
                lambda _: self._complete_encounter(outcome, wound_desc, wound_sev),
                0.60)

        Clock.schedule_once(_do_complete, 0.20)

    def _complete_encounter(self, outcome: str, wound_desc: str, wound_sev: str):
        app      = self._app()
        is_pass5 = outcome == "pass5"

        # ── Remove the live EncounterListItem; a completed EncounterWoundCard ──
        # will be placed in the encounter list instead.
        item           = self._enc_item
        self._enc_item = None

        if is_pass5:
            # No wound — silently remove the live item; nothing stays in the list.
            if item is not None and item.parent is self._wound_enc_items_box:
                self._wound_enc_items_box.remove_widget(item)
        else:
            # Retrieve enc_record attached in _do_auto_complete
            wound_entry = next(
                (w for w in app.state.wounds
                 if w.description == wound_desc
                 and getattr(w, "enc_record", None)
                 and w.enc_record.get("enc_num") == self._current_enc_num),
                None)
            record = (wound_entry.enc_record if wound_entry and wound_entry.enc_record
                      else {
                          "outcome":      outcome,
                          "wound_desc":   wound_desc,
                          "wound_sev":    wound_sev,
                          "wound_effect": self._pending_wound_effect,
                          "wound_roll":   self._pending_wound_roll,
                          "dc":           self._enc.dc,
                          "con_save":     self._enc.roll_total,
                          "con_mod":      self._enc.con_mod_used,
                          "damage_taken": self._enc.damage_taken,
                          "sanity_loss":  self._pending_sanity_loss,
                          "san_rolls":    list(self._pending_san_rolls),
                          "enc_num":      self._current_enc_num,
                      })
            frozen  = self._build_frozen_wound_enc_shell(record)
            enc_num = record.get("enc_num", self._current_enc_num)
            # Remove the live EncounterListItem; replace with an EncounterWoundCard
            if item is not None and item.parent is self._wound_enc_items_box:
                self._wound_enc_items_box.remove_widget(item)
            sev_label    = "Minor Wound" if wound_sev == "minor" else "Major Wound"
            card_subtitle = (
                f"{sev_label} | Wound Table Roll: {self._pending_wound_roll}"
                f" | Sanity Loss: {self._pending_sanity_loss}")
            _accent = T.WOUND_MIN if wound_sev == "minor" else T.BLOOD
            card = EncounterWoundCard(
                title=wound_desc,
                subtitle=card_subtitle,
                effect=(wound_entry.effect if wound_entry else self._pending_wound_effect),
                frozen_shell=frozen,
                accent_hex=_accent)
            _we  = wound_entry
            _sev = wound_sev
            _en  = enc_num
            if wound_sev == "minor":
                card._tap_cb = lambda c=card, e=_we: self._on_minor_tap(c, e)
            else:
                card._tap_cb = lambda c=card, e=_we: self._on_major_tap(c, e)
            def _on_enc_open(inst, val, we=_we, sev=_sev, en=_en, c=card):
                if val:
                    self._sel_enc_num = en
                    if sev == "minor":
                        self._sel_minor         = we
                        self._active_minor_card = c
                    else:
                        self._sel_major         = we
                        self._active_major_card = c
                else:
                    if self._sel_enc_num == en:
                        self._sel_enc_num = None
                    if sev == "minor" and self._sel_minor is we:
                        self._sel_minor         = None
                        self._active_minor_card = None
                    elif sev == "major" and self._sel_major is we:
                        self._sel_major         = None
                        self._active_major_card = None
            card.bind(open_state=_on_enc_open)
            self._wound_enc_items_box.add_widget(
                card, index=len(self._wound_enc_items_box.children))
            self._enc_wound_items[enc_num] = card

        # ── Reset encounter state ─────────────────────────────────────────────
        self._enc.reset()
        for panel in (self._dc_stage_box, self._save_stage_box,
                      self._san_stage_box, self._wnd_stage_box):
            if panel.parent is self._enc_content:
                self._enc_content.remove_widget(panel)
        self._enc_content.height     = 0
        self._enc_flow_shell.height  = 0
        self._enc_flow_shell.opacity = 0
        self._wenc_btn.disabled = False
        self._refresh()
        app.refresh_all()

    def _end_enc(self):
        """Quick reset without completing (emergency abort)."""
        self._enc.reset()
        for panel in (self._dc_stage_box, self._save_stage_box,
                      self._san_stage_box, self._wnd_stage_box):
            if panel.parent is self._enc_content:
                self._enc_content.remove_widget(panel)
        self._enc_content.height     = 0
        self._enc_flow_shell.height  = 0
        self._enc_flow_shell.opacity = 0
        self._reset_enc_ui()

    def reset_view(self):
        """Clear transient wound UI so the app can return to a clean startup state."""
        self._pending_wound.clear()
        self._reset_add_page()
        self._sel_minor = None
        self._sel_major = None
        self._active_minor_card = None
        self._active_major_card = None
        self._sel_enc_num = None
        self._enc_wound_items.clear()
        self._current_enc_num = 0
        if self._wound_enc_items_box is not None:
            self._wound_enc_items_box.clear_widgets()
        if self._enc_item is not None and self._enc_item.parent is not None:
            self._enc_item.parent.remove_widget(self._enc_item)
        self._enc_item = None
        self._enc.reset()
        for panel in (self._dc_stage_box, self._save_stage_box,
                      self._san_stage_box, self._wnd_stage_box):
            if panel.parent is self._enc_content:
                self._enc_content.remove_widget(panel)
        if self._enc_content is not None:
            self._enc_content.height = 0
        if self._enc_flow_shell is not None:
            self._enc_flow_shell.height = 0
            self._enc_flow_shell.opacity = 0
        self._reset_enc_ui()
        self._refresh()

    # ── Frozen encounter shell (completed-state read-only replay) ─────────────

    def _build_frozen_wound_enc_shell(self, record: dict):
        """Read-only replay of a completed wound encounter with clickable tabs."""
        outcome      = record.get("outcome", "pass5")
        is_fail      = outcome in ("fail", "fail5")
        is_fail5     = outcome == "fail5"
        is_pass5     = outcome == "pass5"
        con_save     = record.get("con_save", 0)
        dc           = record.get("dc", 10)
        con_mod      = record.get("con_mod", 0)
        dmg          = record.get("damage_taken", 0)
        wound_desc   = record.get("wound_desc", "")
        wound_sev    = record.get("wound_sev", "")
        sanity_loss  = record.get("sanity_loss", 0)
        san_rolls    = record.get("san_rolls", [])

        stages = ["dc", "save"]
        if not is_pass5:
            stages.append("sanity")
        if not is_pass5:
            stages.append("wound")

        LABELS = {"dc": "DC", "save": "SAVE", "sanity": "SANITY", "wound": "WOUND"}

        shell = Widget(size_hint_y=None, height=0)
        clip_children(shell)

        content = MDBoxLayout(
            orientation="vertical", spacing=dp(6),
            padding=[0, dp(8), 0, dp(8)],
            size_hint=(None, None), height=0)
        shell.add_widget(content)

        # Panel factory
        def _mk_card(border_hex, min_h=80):
            box = MDBoxLayout(
                orientation="vertical", spacing=dp(8),
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
                rt = max(0.0, min(1.0, getattr(w, "_reveal_t", 1.0)))
                vis_w = max(0, w.width * rt)
                _clip.pos = (w.x, w.y); _clip.size = (vis_w, w.height)
                _bd.pos = w.pos;        _bd.size = (vis_w, w.height)
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

        def _lbl(text, color=T.TEXT, style="Body1", bold=False, h=None, markup=False):
            kw = dict(text=text, bold=bold, markup=markup,
                      theme_text_color="Custom", text_color=T.k(color),
                      font_style=style, size_hint_y=None,
                      halign="left", valign="middle")
            if h:
                kw["height"] = dp(h)
            else:
                kw["adaptive_height"] = True
            w = MDLabel(**kw)
            w.bind(width=lambda inst, v: setattr(inst, "text_size", (v, None)))
            return w

        # DC panel
        dc_panel = _mk_card(T.GOLD_DK, 80)
        dc_panel.add_widget(_lbl(
            f"Wound DC: [color={T.GOLD_LT}]{dc}[/color]",
            color=T.TEXT_BRIGHT, style="H5", bold=True, h=56, markup=True))
        dc_panel.add_widget(_lbl(
            f"Damage {dmg} \u00f7 2 = {dmg // 2}  (min. 10)",
            color=T.TEXT_DIM, style="Caption"))

        # Save panel
        save_col = self._wound_outcome_color(outcome)
        save_panel = _mk_card(T.BLOOD, 100)
        save_panel.add_widget(_lbl(
            f"CON Saving Throw: [color={save_col}]{con_save}[/color]",
            color=T.TEXT_BRIGHT, style="H5", bold=True, h=56, markup=True))
        save_panel.add_widget(_lbl(
            f"CON({con_mod:+d})  VS  DC {dc}",
            color=T.TEXT_DIM, style="Caption"))
        _save_verdict = self._wound_outcome_label(outcome)
        save_panel.add_widget(_lbl(
            f"[b][color={save_col}]{_save_verdict}[/color][/b]",
            style="H5", h=44, markup=True))

        # Sanity panel (all non-pass5)
        san_panel = None
        if not is_pass5:
            san_panel = _mk_card(T.PURPLE_LT, 80)
            san_str = "+".join(map(str, san_rolls)) if san_rolls else str(sanity_loss)
            n_dice  = len(san_rolls) if san_rolls else (1 if outcome == "pass" else 2)
            san_panel.add_widget(_lbl(
                f"[b]Sanity Roll: [color={T.PURPLE_LT}]{sanity_loss}[/color][/b]",
                style="H5", h=56, markup=True))
            san_panel.add_widget(_lbl(
                f"{n_dice}d4 ({san_str}) = {sanity_loss}",
                color=T.TEXT_DIM, style="Caption"))

        # Wound panel
        wnd_color = (T.GREEN if is_pass5 else
                     T.WOUND_MIN if outcome == "pass" else T.BLOOD)
        wnd_panel = None
        if not is_pass5:
            wnd_roll = record.get("wound_roll", "?")
            wnd_panel = _mk_card(wnd_color, 80)
            sev_label = "Minor Wound" if outcome == "pass" else "Major Wound"
            if is_fail5: sev_label += " + Exhaustion"
            wnd_panel.add_widget(_lbl(
                f"[color={wnd_color}]{sev_label} | Roll: {wnd_roll}[/color]"
                f"  [color={T.TEXT_BRIGHT}]{wound_desc}[/color]",
                style="Subtitle1", bold=True, h=28, markup=True))
            if wound_desc:
                table = MINOR_WOUND_TABLE if outcome == "pass" else MAJOR_WOUND_TABLE
                effect = next(
                    (e for _, d, e in table if d == wound_desc),
                    record.get("wound_effect", ""))
                if effect:
                    wnd_panel.add_widget(_lbl(effect, color=T.TEXT_DIM))
            if is_fail5:
                wnd_panel.add_widget(_lbl(
                    f"[color={T.GOLD_LT}]+1 Exhaustion[/color]",
                    markup=True, style="Caption", h=18))

        panels = {"dc": dc_panel, "save": save_panel}
        if san_panel:
            panels["sanity"] = san_panel
        if wnd_panel:
            panels["wound"] = wnd_panel

        # Tabs
        tabs       = {}
        active_key = [None]
        # Save tab cap colour matches the live encounter's outcome-based colour.
        _save_cap = self._wound_outcome_color(outcome)
        cap_colors = {
            "dc":     T.GOLD_DK,
            "save":   _save_cap,
            "sanity": T.PURPLE_LT,
            "wound":  wnd_color,
        }

        def _refresh_hl(active):
            for k in stages:
                t = tabs[k]
                t._dim_pending = False
                t._commit_evt  = None
                t._commit_done = True
                t._side_live   = True
                t.set_state("active" if k == active else "done_new")
                t.opacity = 1.0
                t._upd_canvas()

        def _anim_reveal(panel, duration=0.24):
            if panel is None: return
            if getattr(panel, "_reveal_evt", None):
                panel._reveal_evt.cancel(); panel._reveal_evt = None
            panel._reveal_t = 0.0; panel.opacity = 1.0
            if hasattr(panel, "_stage_upd"): panel._stage_upd()
            start_t = Clock.get_boottime()
            def _tick(dt):
                prog = min(1.0, (Clock.get_boottime()-start_t)/max(0.001, duration))
                panel._reveal_t = 1.0 - pow(1.0-prog, 3); panel.opacity = 1.0
                if hasattr(panel, "_stage_upd"): panel._stage_upd()
                if prog >= 1.0:
                    panel._reveal_t = 1.0; panel._reveal_evt = None; return False
                return True
            panel._reveal_evt = Clock.schedule_interval(_tick, 1/60)

        def _anim_retract(panel, duration=0.10, on_complete=None):
            if panel is None:
                if on_complete: on_complete(); return
            if getattr(panel, "_reveal_evt", None):
                panel._reveal_evt.cancel(); panel._reveal_evt = None
            start_t  = Clock.get_boottime()
            start_rt = max(0.0, min(1.0, getattr(panel, "_reveal_t", 1.0)))
            def _tick(dt):
                prog = min(1.0, (Clock.get_boottime()-start_t)/max(0.001, duration))
                panel._reveal_t = start_rt*(1.0-pow(prog,3)); panel.opacity = 1.0
                if hasattr(panel, "_stage_upd"): panel._stage_upd()
                if prog >= 1.0:
                    panel._reveal_t = 0.0; panel.opacity = 1.0
                    if hasattr(panel, "_stage_upd"): panel._stage_upd()
                    panel._reveal_evt = None
                    if on_complete: on_complete(); return False
                return True
            panel._reveal_evt = Clock.schedule_interval(_tick, 1/60)

        def _do_layout(active, animate_tabs=False):
            n = len(stages)
            content_w = max(0, shell.width - EncounterListItem._CONTENT_RIGHT_INSET)
            tabs_h = _EncTab._TOP_PAD + n*_EncTab._TAB_H + (n-1)*_EncTab._TAB_GAP
            if active is None:
                shell.height = tabs_h
                content.width = content_w; content.height = 0; content.opacity = 0
                for i, k in enumerate(stages):
                    t = tabs[k]
                    local_y = (tabs_h - _EncTab._TOP_PAD
                               - (i+1)*_EncTab._TAB_H - i*_EncTab._TAB_GAP)
                    if animate_tabs:
                        Animation.cancel_all(t, "x", "y")
                        Animation(x=shell.x, y=shell.y+local_y,
                                  duration=0.22, t="in_out_cubic").start(t)
                    else:
                        t.pos = (shell.x, shell.y+local_y)
                    t.size = (_EncTab._TAB_W, _EncTab._TAB_H)
                return
            panel = panels.get(active)
            content_h = max(dp(80),
                            getattr(panel, "minimum_height", 0) if panel else 0,
                            getattr(panel, "_min_stage_height", 0) if panel else 0)
            gap = dp(8)
            shell_h = tabs_h + gap + content_h
            shell.height = shell_h
            aidx = stages.index(active)
            tabs_above = (_EncTab._TOP_PAD
                          + aidx*(_EncTab._TAB_H+_EncTab._TAB_GAP) + _EncTab._TAB_H)
            content.x = shell.x + dp(1)
            content.y = shell.y + shell_h - tabs_above - gap - content_h
            content.width = content_w; content.height = content_h
            for i, k in enumerate(stages):
                t = tabs[k]
                extra = (content_h+gap) if i > aidx else 0
                local_y = (shell_h - _EncTab._TOP_PAD
                           - (i+1)*_EncTab._TAB_H - i*_EncTab._TAB_GAP - extra)
                tgt_x = shell.x; tgt_y = shell.y + local_y
                if animate_tabs:
                    Animation.cancel_all(t, "x", "y")
                    Animation(x=tgt_x, y=tgt_y,
                              duration=0.22, t="in_out_cubic").start(t)
                else:
                    t.pos = (tgt_x, tgt_y)
                t.size = (_EncTab._TAB_W, _EncTab._TAB_H)

        def _close_tab(animate=True):
            old = content.children[0] if content.children else None
            active_key[0] = None
            def _do_clear():
                content.clear_widgets(); content.opacity = 0
                _refresh_hl(None)
                Clock.schedule_once(lambda dt: _do_layout(None, animate_tabs=animate))
            if animate and old is not None:
                _anim_retract(old, on_complete=_do_clear)
            else:
                if old is not None:
                    old._reveal_t = 0.0; old.opacity = 1.0
                    if hasattr(old, "_stage_upd"): old._stage_upd()
                _do_clear()

        def _open_tab(key, animate=True):
            if active_key[0] == key and content.children:
                _close_tab(animate=animate); return
            old = content.children[0] if content.children else None
            active_key[0] = key
            def _do_swap():
                content.clear_widgets()
                p = panels.get(key)
                if p:
                    p._reveal_t = 0.0 if animate else 1.0
                    p.opacity = 1.0
                    if hasattr(p, "_stage_upd"): p._stage_upd()
                    content.add_widget(p)
                _refresh_hl(key)
                def _layout_then_reveal(dt):
                    _do_layout(key, animate_tabs=animate)
                    content.opacity = 1.0
                    if p is None: return
                    if animate: _anim_reveal(p)
                    else:
                        p._reveal_t = 1.0
                        if hasattr(p, "_stage_upd"): p._stage_upd()
                Clock.schedule_once(_layout_then_reveal)
            if animate and old is not None:
                _anim_retract(old, on_complete=_do_swap)
            else:
                _do_swap()

        def _animate_tabs_from_rail():
            def _start(_dt):
                _do_layout(active_key[0])
                for k in stages:
                    t = tabs[k]
                    Animation.cancel_all(t, "x", "width")
                    tx = t.x; tw = t.width
                    t.x = shell.x; t.width = _EncTab._RAIL_W
                    t._upd_canvas()
                    Animation(x=tx, width=tw, duration=0.24, t="out_cubic").start(t)
            Clock.schedule_once(_start, 0)

        shell.bind(
            pos=lambda *_: _do_layout(active_key[0]),
            size=lambda *_: _do_layout(active_key[0]))

        for key in stages:
            tab = _WoundEncTab(key, LABELS[key], _open_tab)
            tab._shown   = True
            tab._cap_hex = cap_colors.get(key)
            tab.opacity  = 1
            tabs[key] = tab
            shell.add_widget(tab)

        _refresh_hl(None)
        def _do_parent_close(on_done=None):
            """Animate tabs back into the rail, then call on_done (card shrink)."""
            content.clear_widgets()
            content.opacity = 0
            active_key[0] = None
            _refresh_hl(None)
            for k in stages:
                t = tabs[k]
                Animation.cancel_all(t, "width")
                Animation(width=_EncTab._RAIL_W, duration=0.24,
                          t="in_out_cubic").start(t)
            if on_done:
                Clock.schedule_once(lambda dt: on_done(), 0.28)

        def _reset_tabs_to_rail():
            """Snap all tabs back to rail width (no animation) — call before
            the card expands so tabs don't flash at full width mid-reveal."""
            for k in stages:
                t = tabs[k]
                Animation.cancel_all(t, "x", "width")
                t.width = _EncTab._RAIL_W
                t._upd_canvas()

        shell._on_parent_open  = _animate_tabs_from_rail
        shell._on_parent_close = _do_parent_close
        shell._reset_tabs_to_rail = _reset_tabs_to_rail
        return shell

    # ── Public refresh ────────────────────────────────────────────────────────

    def _refresh(self):
        self.refresh()

    def refresh(self):
        app    = self._app()
        minors = app.state.minor_wounds
        majors = app.state.major_wounds

        self._current_enc_num = max(
            [self._current_enc_num] + [
                rec.get("enc_num", 0)
                for rec in (
                    (getattr(w, "enc_record", None) or {}) for w in app.state.wounds
                )
                if isinstance(rec.get("enc_num", 0), int)
            ]
        )

        prev_minor = self._sel_minor
        prev_major = self._sel_major

        # Preserve enc-derived cards that are open (they live in
        # _wound_enc_items_box and persist across refreshes).
        _keep_minor_enc = isinstance(self._active_minor_card,
                                     (EncounterListItem, EncounterWoundCard))
        _keep_major_enc = isinstance(self._active_major_card,
                                     (EncounterListItem, EncounterWoundCard))

        # ── Minor wounds ───────────────────────────���──────────────────────────
        self._minor_list_box.clear_widgets()
        self._minor_items.clear()
        if not _keep_minor_enc:
            self._active_minor_card = None
        if not minors:
            self._sel_minor = None
        else:
            for i, w in enumerate(minors):
                if w.enc_record:
                    enc_num = w.enc_record.get("enc_num", -1)
                    # Already shown as a completed EncounterListItem this session,
                    # or there is a live encounter currently active — skip.
                    if enc_num in self._enc_wound_items or self._enc_item is not None:
                        continue
                    # Reload case: wound came from a previous session.  Build an
                    # EncounterWoundCard in the encounter history box.
                    rec = w.enc_record
                    if rec.get("source") == "manual_add":
                        subtitle = "Minor Wound | Added manually"
                        frozen = None
                    else:
                        _roll    = next((r for r, d, _ in MINOR_WOUND_TABLE
                                         if d == w.description), "?")
                        san_loss = rec.get("sanity_loss", 0)
                        wnd_roll = rec.get("wound_roll", _roll)
                        subtitle = (f"Minor Wound | Wound Table Roll: {wnd_roll}"
                                    f" | Sanity Loss: {san_loss}")
                        frozen   = self._build_frozen_wound_enc_shell(rec)
                    card = EncounterWoundCard(
                        title=w.description,
                        subtitle=subtitle,
                        effect=w.effect or w.description,
                        frozen_shell=frozen,
                        accent_hex=T.WOUND_MIN)
                    card._tap_cb = lambda c=card, e=w: self._on_minor_tap(c, e)
                    _en = enc_num
                    def _minor_enc_open(inst, val, en=_en, we=w):
                        if val:
                            self._sel_enc_num = en
                        elif self._sel_enc_num == en:
                            self._sel_enc_num = None
                    card.bind(open_state=_minor_enc_open)
                    self._wound_enc_items_box.add_widget(card)
                    self._enc_wound_items[enc_num] = card
                    if w is prev_minor:
                        card._do_open_desc()
                        self._active_minor_card = card
                        self._sel_minor = w
                else:
                    _roll = next((r for r, d, _ in MINOR_WOUND_TABLE
                                  if d == w.description), "?")
                    card = ExpandingEffectCard(
                        on_tap=lambda wid, entry=w: self._on_minor_tap(wid, entry))
                    card.title_text    = w.description
                    card.subtitle_text = f"Minor Wound | Roll: {_roll} | 1d4 Sanity Loss"
                    card.detail_body   = w.effect
                    card.accent_rgba   = list(T.k(T.WOUND_MIN))
                    self._minor_list_box.add_widget(card)
                    self._minor_items[i] = card
                    if w is prev_minor:
                        card.set_open(True, animate=False)
                        self._active_minor_card = card

        # ── Major wounds ──────────────────────────────────────────────────────
        self._major_list_box.clear_widgets()
        self._major_items.clear()
        if not _keep_major_enc:
            self._active_major_card = None
        if not majors:
            self._sel_major = None
        else:
            for i, w in enumerate(majors):
                if w.enc_record:
                    enc_num = w.enc_record.get("enc_num", -1)
                    if enc_num in self._enc_wound_items or self._enc_item is not None:
                        continue
                    rec = w.enc_record
                    if rec.get("source") == "manual_add":
                        subtitle = "Major Wound | Added manually"
                        frozen = None
                    else:
                        _roll    = next((r for r, d, _ in MAJOR_WOUND_TABLE
                                         if d == w.description), "?")
                        san_loss = rec.get("sanity_loss", 0)
                        wnd_roll = rec.get("wound_roll", _roll)
                        subtitle = (f"Major Wound | Wound Table Roll: {wnd_roll}"
                                    f" | Sanity Loss: {san_loss}")
                        frozen   = self._build_frozen_wound_enc_shell(rec)
                    card = EncounterWoundCard(
                        title=w.description,
                        subtitle=subtitle,
                        effect=w.effect or w.description,
                        frozen_shell=frozen,
                        accent_hex=T.BLOOD)
                    card._tap_cb = lambda c=card, e=w: self._on_major_tap(c, e)
                    _en = enc_num
                    def _major_enc_open(inst, val, en=_en):
                        if val:
                            self._sel_enc_num = en
                        elif self._sel_enc_num == en:
                            self._sel_enc_num = None
                    card.bind(open_state=_major_enc_open)
                    self._wound_enc_items_box.add_widget(card)
                    self._enc_wound_items[enc_num] = card
                    if w is prev_major:
                        card._do_open_desc()
                        self._active_major_card = card
                        self._sel_major = w
                else:
                    _roll = next((r for r, d, _ in MAJOR_WOUND_TABLE
                                  if d == w.description), "?")
                    card = ExpandingEffectCard(
                        on_tap=lambda wid, entry=w: self._on_major_tap(wid, entry))
                    card.title_text    = w.description
                    card.subtitle_text = f"Major Wound | Roll: {_roll} | 2d4 Sanity Loss"
                    card.detail_body   = w.effect
                    card.accent_rgba   = list(T.k(T.BLOOD))
                    self._major_list_box.add_widget(card)
                    self._major_items[i] = card
                    if w is prev_major:
                        card.set_open(True, animate=False)
                        self._active_major_card = card

    def highlight_last_wound(self, severity: str):
        # For encounter-derived wounds the card lives in _wound_enc_items_box.
        # Check _enc_wound_items first (keyed by enc_num, most recent = highest).
        app   = self._app()
        wound_list = (app.state.minor_wounds if severity == "minor"
                      else app.state.major_wounds)
        for w in reversed(wound_list):
            enc_num = (w.enc_record or {}).get("enc_num", -1) if getattr(
                w, "enc_record", None) else -1
            if enc_num in self._enc_wound_items:
                widget = self._enc_wound_items[enc_num]
                if widget:
                    widget.flash()
                return
        # Fall back to non-enc wound list items
        items = self._minor_items if severity == "minor" else self._major_items
        if not items:
            return
        last_idx = max(items.keys())
        item = items.get(last_idx)
        if item:
            item.flash()

    # ── Active list interactions ───────────────────────────────────────────────

    def _on_minor_tap(self, card: ExpandingEffectCard, entry: WoundEntry):
        if self._active_minor_card is card:
            card.set_open(False)
            self._active_minor_card = None
            self._sel_minor = None
            return
        if self._active_major_card:
            self._active_major_card.set_open(False)
            self._active_major_card = None
            self._sel_major = None
        if self._active_minor_card:
            self._active_minor_card.set_open(False)
        card.set_open(True)
        self._active_minor_card = card
        self._sel_minor         = entry

    def _on_major_tap(self, card: ExpandingEffectCard, entry: WoundEntry):
        if self._active_major_card is card:
            card.set_open(False)
            self._active_major_card = None
            self._sel_major = None
            return
        if self._active_minor_card:
            self._active_minor_card.set_open(False)
            self._active_minor_card = None
            self._sel_minor = None
        if self._active_major_card:
            self._active_major_card.set_open(False)
        card.set_open(True)
        self._active_major_card = card
        self._sel_major         = entry

    def open_wound(self, entry, severity: str):
        self._go_page(0)
        app = self._app()
        # Check enc-wound items first (encounter-derived wounds in the history box)
        enc_num = (entry.enc_record or {}).get("enc_num", -1) if getattr(
            entry, "enc_record", None) else -1
        if enc_num in self._enc_wound_items:
            widget = self._enc_wound_items[enc_num]
            if widget:
                widget.flash()
            return
        # Fall back to minor/major list items
        wound_list = (app.state.minor_wounds if severity == "minor"
                      else app.state.major_wounds)
        items = self._minor_items if severity == "minor" else self._major_items
        for i, w in enumerate(wound_list):
            if w is entry:
                card = items.get(i)
                if card:
                    active = (self._active_minor_card if severity == "minor"
                              else self._active_major_card)
                    if active is not card:
                        if severity == "minor":
                            self._on_minor_tap(card, entry)
                        else:
                            self._on_major_tap(card, entry)
                    card.flash()
                return

    # ── Remove wound ──────────────────────────────────────────────────────────

    def _on_remove_wound(self, *_):
        if self._sel_minor:
            self._on_remove_minor()
        elif self._sel_major:
            self._on_remove_major()
        else:
            self._snack("Select a wound first.", T.BORDER)

    def _on_remove_minor(self, *_):
        if not self._sel_minor:
            self._snack("Select a minor wound first.", T.BORDER); return
        app = self._app()
        w = self._sel_minor
        if w not in app.state.wounds:
            self._sel_minor = None; self._active_minor_card = None; return
        self._push_undo()
        app.state.wounds.remove(w)
        self._log(f"Minor wound removed: {w.description}")
        self._sel_minor = None; self._active_minor_card = None
        # Clean up enc-wound history widget if this wound came from an encounter
        enc_num = (w.enc_record or {}).get("enc_num", -1) if getattr(
            w, "enc_record", None) else -1
        if enc_num >= 0 and enc_num in self._enc_wound_items:
            widget = self._enc_wound_items.pop(enc_num)
            if widget is not None and widget.parent is self._wound_enc_items_box:
                self._wound_enc_items_box.remove_widget(widget)
        self.refresh(); app.refresh_all(); self._save()

    def _on_remove_major(self, *_):
        if not self._sel_major:
            self._snack("Select a major wound first.", T.BORDER); return
        app = self._app()
        w = self._sel_major
        if w not in app.state.wounds:
            self._sel_major = None; self._active_major_card = None; return
        self._push_undo()
        app.state.wounds.remove(w)
        self._log(f"Major wound removed: {w.description}")
        self._sel_major = None; self._active_major_card = None
        # Clean up enc-wound history widget if this wound came from an encounter
        enc_num = (w.enc_record or {}).get("enc_num", -1) if getattr(
            w, "enc_record", None) else -1
        if enc_num >= 0 and enc_num in self._enc_wound_items:
            widget = self._enc_wound_items.pop(enc_num)
            if widget is not None and widget.parent is self._wound_enc_items_box:
                self._wound_enc_items_box.remove_widget(widget)
        self.refresh(); app.refresh_all(); self._save()

    # ── Remove encounter (from Encounter List trash button) ───────────────────

    def _on_remove_enc(self, *_):
        enc_num = self._sel_enc_num
        if enc_num is None:
            self._snack("Select an encounter first.", T.BORDER); return
        app = self._app()
        # Find any wound tied to this encounter and remove it from state
        wound = next(
            (w for w in list(app.state.wounds)
             if getattr(w, "enc_record", None)
             and w.enc_record.get("enc_num") == enc_num),
            None)
        if wound is not None:
            self._push_undo()
            app.state.wounds.remove(wound)
            self._log(f"Encounter {enc_num} removed: {wound.description}")
            # Clear wound selection refs
            if self._sel_minor is wound:
                self._sel_minor = None; self._active_minor_card = None
            if self._sel_major is wound:
                self._sel_major = None; self._active_major_card = None
        # Remove the encounter UI widget
        widget = self._enc_wound_items.pop(enc_num, None)
        if widget is not None and widget.parent is self._wound_enc_items_box:
            self._wound_enc_items_box.remove_widget(widget)
        self._sel_enc_num = None
        if wound is not None:
            self.refresh(); app.refresh_all(); self._save()

    # ── Add wound (manual) ────────────────────────────────────────────────────

    def _add_wound(self, severity: str, desc: str = "", effect: str = ""):
        app = self._app()
        self._push_undo()
        if not desc:
            _, desc, effect = roll_random_wound(severity)
        elif not effect:
            effect = "Custom wound."
        entry = app.state.add_wound(desc, effect, severity)
        entry.enc_record = self._manual_wound_record(severity, desc, effect)
        self._log(f"{severity.title()} wound added to encounter list: {desc}")
        self.refresh()
        app.refresh_all()
        self._save()
        color = T.WOUND_MIN if severity == "minor" else T.BLOOD
        Clock.schedule_once(
            lambda _, e=entry, s=severity, c=color: app.notify_event(
                f"{s.title()} Wound: [color={c}]{desc}[/color]",
                "wounds", c,
                action_cb=lambda _e=e, _s=s: self.open_wound(_e, _s)
            ), 0.15)
