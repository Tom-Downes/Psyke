"""
Color constants and KivyMD theme helpers.
All hex colors match FSM-6.py Theme class.
"""

# ── Raw hex constants ───────────────────────────────────────────────────────
BG_DEEP    = "#0a0c10"
BG         = "#10131a"
BG_CARD    = "#171c26"
BG_INSET   = "#0d1018"
BG_HOVER   = "#1e2433"

BORDER     = "#2a3040"
BORDER_LT  = "#353d50"

TEXT       = "#d4c5a0"
TEXT_DIM   = "#8a7e66"
TEXT_BRIGHT= "#f0e6cc"
TEXT_DARK  = "#0a0c10"

GOLD       = "#c8a44e"
GOLD_LT    = "#e0c06a"
GOLD_DK    = "#8a7030"

RED        = "#8c3838"
RED_LT     = "#a84848"
RED_DK     = "#5c2020"

BLUE       = "#5090c8"
BLUE_LT    = "#70b0e0"
GREEN      = "#50a870"
GREEN_LT   = "#70c890"
PURPLE     = "#8060b0"
PURPLE_LT  = "#a080d0"
WHITE      = "#ffffff"

BLOOD      = "#9c2020"
BLOOD_LT   = "#c03030"
BLOOD_DK   = "#5a1010"

SILVER     = "#8898a8"
SILVER_LT  = "#a8b8c8"

WOUND_MIN    = "#c06060"
WOUND_MIN_DK = "#8c3030"

STAGE_1    = "#50a870"
STAGE_2    = "#c8a44e"
STAGE_3    = "#d08040"
STAGE_4    = "#c44040"

M_STABLE   = "#3a5a70"
M_SHORT    = "#c8a44e"
M_LONG     = "#c07838"
M_INDEF    = "#8c3838"
M_ZERO     = "#2a0808"

# Desensitization teal palette
DESENS        = "#4a9ab8"
DESENS_DK     = "#2a5870"
DESENS_LT     = "#6abcd8"

# Per-rung desensitization button colors (increasing luminosity)
DESENS_1   = "#2a5f8a"   # Low      — dim steel-blue
DESENS_2   = "#2d85c0"   # Moderate — medium blue
DESENS_3   = "#3aabdc"   # High     — bright blue
DESENS_4   = "#5ad0f8"   # Extreme  — vivid cyan-blue

# ── Kivy float-tuple converters ─────────────────────────────────────────────

def k(h: str, a: float = 1.0):
    """Convert '#rrggbb' hex to Kivy RGBA float tuple."""
    return (int(h[1:3],16)/255, int(h[3:5],16)/255, int(h[5:7],16)/255, a)

# Pre-built Kivy tuples for common colors
K_BG          = k(BG)
K_BG_CARD     = k(BG_CARD)
K_BG_INSET    = k(BG_INSET)
K_BORDER      = k(BORDER)
K_TEXT        = k(TEXT)
K_TEXT_DIM    = k(TEXT_DIM)
K_TEXT_BRIGHT = k(TEXT_BRIGHT)
K_GOLD        = k(GOLD)
K_GOLD_DK     = k(GOLD_DK)
K_RED         = k(RED)
K_BLUE        = k(BLUE)
K_GREEN       = k(GREEN)
K_PURPLE      = k(PURPLE)
K_BLOOD       = k(BLOOD)
K_WOUND_MIN   = k(WOUND_MIN)
K_STAGE_1     = k(STAGE_1)
K_STAGE_2     = k(STAGE_2)
K_STAGE_3     = k(STAGE_3)
K_STAGE_4     = k(STAGE_4)
K_DESENS      = k(DESENS)
K_DESENS_DK   = k(DESENS_DK)

# KivyMD custom_color palette entries (used in App.theme_cls)
KIVY_PRIMARY   = "DeepPurple"
KIVY_ACCENT    = "Amber"
KIVY_STYLE     = "Dark"

# Madness stage -> hex color lookup
MADNESS_COLORS = {
    "STABLE":     M_STABLE,
    "SHORT_TERM": M_SHORT,
    "LONG_TERM":  M_LONG,
    "INDEFINITE": M_INDEF,
    "ZERO":       M_ZERO,
}

# Fear stage -> hex color
STAGE_COLORS = {1: STAGE_1, 2: STAGE_2, 3: STAGE_3, 4: STAGE_4}

# Desensitization rung -> hex color
DESENS_RUNG_COLORS = {1: DESENS_1, 2: DESENS_2, 3: DESENS_3, 4: DESENS_4}
