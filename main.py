"""
Sanity, Fear & Madness Tracker — KivyMD Android App  (V2)
Entry point: App class, global layout, header, sanity bar, madness banner.
4-tab layout: Fears / Sanity / Wounds / Spells
Back button cancels active encounters or dismisses dialogs.

Run on desktop: python main.py
Build for Android: buildozer android debug
"""
from __future__ import annotations

import time
from datetime import datetime

from kivy.app import App
from kivy.clock import Clock
from kivy.core.window import Window
from kivy.graphics import Color, Rectangle
from kivy.metrics import dp
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.screenmanager import ScreenManager, Screen, NoTransition
from kivy.uix.scrollview import ScrollView
from kivy.uix.widget import Widget

from kivymd.app import MDApp
from kivymd.uix.boxlayout import MDBoxLayout
from kivymd.uix.button import MDFlatButton, MDIconButton, MDRaisedButton
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
            mode="rectangle"
        )
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

class HeaderCard(BoxLayout):
    """
    Compact persistent header: character name, WIS/CON chips,
    exhaustion pips, session timer, undo + log buttons.
    2 rows, total 88dp.
    """

    def __init__(self, **kwargs):
        kwargs.setdefault("orientation", "vertical")
        kwargs.setdefault("size_hint_y", None)
        kwargs.setdefault("height", dp(88))
        kwargs.setdefault("spacing", dp(4))
        kwargs.setdefault("padding", [dp(8), dp(4), dp(8), dp(4)])
        super().__init__(**kwargs)
        self._timer_start = time.time()

        with self.canvas.before:
            Color(*T.k(T.BG_CARD))
            self._bg = Rectangle()
        self.bind(pos=self._upd_bg, size=self._upd_bg)
        self._build()
        Clock.schedule_interval(self._tick_timer, 1)

    def _upd_bg(self, *_):
        self._bg.pos  = self.pos
        self._bg.size = self.size

    def _build(self):
        # Row 1: name field + log + undo (44dp)
        row1 = MDBoxLayout(size_hint_y=None, height=dp(44), spacing=dp(4))
        self._name_field = MDTextField(
            hint_text="Character Name",
            text="Unnamed Adventurer",
            mode="rectangle",
            line_color_normal=T.k(T.BORDER))
        self._name_field.bind(text=self._on_name_change)
        row1.add_widget(self._name_field)

        self._log_btn = MDIconButton(
            icon="notebook-outline",
            theme_icon_color="Custom", icon_color=T.k(T.TEXT_DIM),
            size_hint_x=None, width=dp(40),
            on_release=self._on_show_log)
        self._undo_btn = MDIconButton(
            icon="undo",
            theme_icon_color="Custom", icon_color=T.k(T.TEXT_DIM),
            size_hint_x=None, width=dp(40),
            on_release=self._on_undo_pressed)
        row1.add_widget(self._log_btn)
        row1.add_widget(self._undo_btn)
        self.add_widget(row1)

        # Row 2: WIS + CON + exhaustion pips + timer (30dp)
        row2 = MDBoxLayout(size_hint_y=None, height=dp(30), spacing=dp(4))
        self._wis_btn = MDFlatButton(
            text="WIS 10  +0",
            theme_text_color="Custom", text_color=T.k(T.GOLD),
            size_hint_x=None, width=dp(90),
            on_release=self._on_edit_wis)
        self._con_btn = MDFlatButton(
            text="CON 10  +0",
            theme_text_color="Custom", text_color=T.k(T.BLUE),
            size_hint_x=None, width=dp(90),
            on_release=self._on_edit_con)
        self._exh_widget = ExhaustionWidget(size_hint_x=1, height=dp(30))
        self._exh_widget.set_change_callback(self._on_exhaustion_change)
        self._timer_lbl = MDLabel(
            text="00:00",
            theme_text_color="Custom", text_color=T.k(T.TEXT_DIM),
            font_style="Caption", halign="right",
            size_hint_x=None, width=dp(48))
        row2.add_widget(self._wis_btn)
        row2.add_widget(self._con_btn)
        row2.add_widget(self._exh_widget)
        row2.add_widget(self._timer_lbl)
        self.add_widget(row2)

    def refresh(self, state: SanityState):
        wis = state.wis_score; wm = state.wis_mod
        con = state.con_score; cm = state.con_mod
        self._wis_btn.text    = f"WIS {wis}  {wm:+d}"
        self._con_btn.text    = f"CON {con}  {cm:+d}"
        self._exh_widget.level = state.exhaustion

    def _tick_timer(self, dt):
        elapsed = int(time.time() - self._timer_start)
        m, s = divmod(elapsed, 60)
        self._timer_lbl.text = f"{m:02d}:{s:02d}"

    def _on_name_change(self, inst, val):
        App.get_running_app().char_name = val.strip() or "Unnamed Adventurer"

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
        app.save_manager.save(app.state, app.fm, app.char_name, app.enc_history)

    def _on_undo_pressed(self, *_):
        App.get_running_app()._on_undo()

    def _on_show_log(self, *_):
        App.get_running_app()._on_show_log()


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

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.title         = "Sanity, Fear & Madness"
        self.state         = SanityState()
        self.fm            = FearManager()
        self.undo_stack    = UndoStack()
        self.enc_history:  list[str] = []
        self.char_name     = "Unnamed Adventurer"
        self.save_manager: SaveManager | None = None
        self._sep_color    = T.GOLD
        self._sep_widget:  Widget | None = None
        self._active_dialog: MDDialog | None = None

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
        self._header = HeaderCard(size_hint_y=None, height=dp(88))
        root.add_widget(self._header)

        # Sanity bar
        self._san_bar = SanityBar(size_hint_y=None, height=dp(28))
        root.add_widget(self._san_bar)

        # Madness banner
        self._mad_banner = MadnessBanner(size_hint_y=None, height=dp(52))
        root.add_widget(self._mad_banner)

        # Sanity label
        self._san_label = MDLabel(
            text="Sanity: 25 / 25",
            theme_text_color="Custom",
            text_color=T.k(T.PURPLE_LT),
            font_style="Caption",
            halign="center",
            size_hint_y=None, height=dp(18))
        root.add_widget(self._san_label)

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
        self.state.rebuild_thresholds()
        self.state.wounds    = []
        self.state.madnesses = []
        from models import WoundEntry, MadnessEntry
        for w in data.get("wounds", []):
            self.state.wounds.append(WoundEntry.from_dict(w))
        for m in data.get("madnesses", []):
            self.state.madnesses.append(MadnessEntry.from_dict(m))
        self.fm.restore(data.get("fears", data))   # handle old flat format
        self.char_name = data.get("char_name", "Unnamed Adventurer")
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
        self._san_label.text = f"Sanity: {st.current_sanity} / {st.max_sanity}"
        self._mad_banner.set_stage(st.madness)
        self._header.refresh(st)

        self._fears_tab.refresh()
        self._sanity_tab.refresh()
        self._wounds_tab.refresh()
        self._spells_tab.refresh()

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
