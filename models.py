"""
Pure-Python data models, tables, and state management.
FSM-Android-V2: Full FSM-6.py parity — desensitization system,
D20 named madness tables, severity renaming, extreme severity rules.
No Tkinter dependencies.
"""
from __future__ import annotations

import json, math, os, random, sys
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum, auto
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# ───────────────────────────────────────────────────────────────────────────
# CONSTANTS
# ───────────────────────────────────────────────────────────────────────────

WIS_MIN, WIS_MAX   = 1, 30
CON_MIN, CON_MAX   = 1, 30
SANITY_BASE        = 15
MAX_FEAR_STAGE     = 4
D4_SIDES           = 4
UNDO_STACK_LIMIT   = 50
MAX_EXHAUSTION     = 6
FEAR_ENC_DC        = 12
SAVE_FILE_NAME     = "save_v6.json"

THRESHOLDS: List[Tuple[str, float, str]] = [
    ("Crossed below 75%", 0.75, "short"),
    ("Crossed below 50%", 0.50, "long"),
    ("Crossed below 25%", 0.25, "indefinite"),
    ("Reached 0 — DM controls character", 0.00, "zero"),
]

SIMPLE_FEAR_POOL: List[str] = [
    "Heights", "Spiders", "Numbers", "Food", "Confined Spaces",
    "Madness", "Night", "Sleep", "Blood", "The Dark", "The Mists",
    "Wolves", "Graveyards", "Mirrors", "Dolls", "Bells", "Storms",
    "Empty Houses", "Being Watched", "Fire", "Water", "Snakes",
    "Silence", "Crowds", "Being Alone", "Thunder", "Fog",
]

# ───────────────────────────────────────────────────────────────────────────
# DESENSITIZATION CONSTANTS
# ───────────────────────────────────────────────────────────────────────────

DESENS_DC: Dict[int, int] = {1: 16, 2: 14, 3: 12, 4: 10}

DESENS_NAMES: Dict[int, str] = {
    1: "Low Desensitization",
    2: "Moderate Desensitization",
    3: "High Desensitization",
    4: "Extreme Desensitization",
}

DESENS_DESCS: Dict[int, str] = {
    1: "Encounter DC 16. Rung 1 of 4.\nMinimal exposure — the fear feels distant.\nConfront raises rung; Avoid lowers rung.",
    2: "Encounter DC 14. Rung 2 of 4.\nSome exposure — the fear is familiar but raw.\nConfront raises rung; Avoid lowers rung.",
    3: "Encounter DC 12. Rung 3 of 4.\nSignificant exposure — the fear is internalised.\nConfront raises rung; Avoid lowers rung.",
    4: "Encounter DC 10. Rung 4 of 4.\nDeep exposure — the fear is part of you now.\nConfront maintains rung; Avoid lowers rung.",
}

# Teal accent used for all desensitization UI elements
DESENS_COLOR    = "#4a9ab8"
DESENS_COLOR_DK = "#2a5870"

# Per-rung blues — increasing luminosity from dim to bright
DESENS_RUNG_COLORS: Dict[int, str] = {
    1: "#2a5f8a",   # Low      — dim steel-blue
    2: "#2d85c0",   # Moderate — medium blue
    3: "#3aabdc",   # High     — bright blue
    4: "#5ad0f8",   # Extreme  — vivid cyan-blue
}

# ───────────────────────────────────────────────────────────────────────────
# D20 MADNESS TABLES  (roll_label, name, effect)
# ───────────────────────────────────────────────────────────────────────────

SHORT_TERM_MADNESS_TABLE: List[Tuple[str, str, str]] = [
    ("D20-1",  "Black Out",
     "The afflicted's vision gutters out, and they collapse. They fall unconscious, but do not "
     "lose hit points and are stable. Another creature can use an action to shake them awake, ending the effect."),
    ("D20-2",  "Tell-Tale Heart",
     "The afflicted hears a loud, relentless heartbeat drowning out all other sound. They are "
     "deafened, and have disadvantage on attack rolls made against creatures behind them."),
    ("D20-3",  "Pyric Delusion",
     "The afflicted is certain their clothes and gear are burning their skin. On their turn, they "
     "use their action to doff their clothing and armour down to underclothes, believing it is the "
     "source of the pain. They refuse to don the removed clothing or armour until the madness ends."),
    ("D20-4",  "Tremors",
     "The afflicted develops uncontrollable tremors and tics that ruin precision and leverage. "
     "They have disadvantage on Strength and Dexterity ability checks, and disadvantage on attack rolls."),
    ("D20-5",  "Pica",
     "The afflicted is seized by an overpowering craving to eat something unnatural — dirt, slime, "
     "wax, hair, or worse. If such a substance is within reach, they must use their action to consume "
     "it (or try to), unless physically prevented."),
    ("D20-6",  "Formication",
     "The afflicted feels insects crawling beneath their skin, scratching and tunnelling. At the end "
     "of each of their turns in which they did not take damage, they take 1d4 slashing damage as they "
     "claw at themself. This continues until the madness ends or until they have lost half of their "
     "current hit points from this effect."),
    ("D20-7",  "Separation Anxiety",
     "The afflicted becomes convinced they will die if left alone. Choose a random ally the afflicted "
     "can see when the madness begins. The afflicted is compelled to remain within 5 feet of that ally. "
     "While farther than 5 feet from that ally, the afflicted has disadvantage on all rolls."),
    ("D20-8",  "Fear",
     "The afflicted's mind latches onto a nearby omen of doom. The DM chooses a nearby trigger. "
     "The afflicted becomes frightened of that trigger. Add that trigger to the afflicted's Fear List."),
    ("D20-9",  "Safe Space",
     "The afflicted fixates on a 15-foot by 15-foot area as the only place they can survive. "
     "They believe they will die if they leave it. They become fiercely territorial: if another "
     "creature enters the area, the afflicted attacks any creature in the area."),
    ("D20-10", "Frenzied",
     "The afflicted froths at the mouth as panic and violence take over reason. "
     "Each round, they must use their action to attack the nearest creature."),
    ("D20-11", "Babbling",
     "The afflicted's thoughts spill out in tangled, feverish nonsense. They are incapable of "
     "normal speech and cannot form the focus needed for magic. "
     "They cannot speak coherently or cast spells."),
    ("D20-12", "Hysterical Weeping",
     "The afflicted begins uncontrollably weeping — shaking breaths, blurred vision, tears they "
     "cannot stop — yet can otherwise act normally. "
     "They have disadvantage on Perception checks that rely on sight."),
    ("D20-13", "No Truce with the Furies",
     "The afflicted is convinced unseen adversaries are chasing them. They cannot end their turn "
     "within 20 feet of where they began it. If they would, they must use their reaction (if "
     "available) to move until they end outside that boundary."),
    ("D20-14", "Phantom Infant",
     "The afflicted becomes absolutely convinced they are holding a baby in their off-hand. If they "
     "were holding something in that hand, they drop it as the 'baby' takes its place. "
     "They behave as though that hand is occupied for the duration."),
    ("D20-15", "Gold Purge",
     "The afflicted becomes convinced their gold is trying to kill them. While affected, they must "
     "use their bonus action each turn to remove 1d20 gp from wherever they store it "
     "and throw it on the ground."),
    ("D20-16", "Hallucinations",
     "The afflicted experiences vivid hallucinations — faces in fog, movement at the edge of vision, "
     "whispers in another voice. They have disadvantage on ability checks."),
    ("D20-17", "Startled",
     "The afflicted is wound so tight that any sudden movement snaps their body into reflex. Whenever "
     "a creature moves within 5 feet of the afflicted, they must succeed on a DC 10 Dexterity saving "
     "throw or drop what they're holding as a reaction. On a failed save, speed becomes 0 until the "
     "start of their next turn."),
    ("D20-18", "Hypersensitive",
     "Every wound affects not only the body but the mind. Whenever the afflicted takes damage, "
     "they take 1 additional psychic damage per die rolled as part of that damage."),
    ("D20-19", "Emotional Numbness",
     "The afflicted goes cold inside. They are immune to being charmed, "
     "but they have disadvantage on Charisma ability checks."),
    ("D20-20", "Adrenaline",
     "The afflicted becomes suffused with adrenaline. They gain advantage on all attack rolls. "
     "When the madness ends, they gain 1 level of exhaustion."),
]

LONG_TERM_MADNESS_TABLE: List[Tuple[str, str, str]] = [
    ("D20-1",  "Object Deification",
     "The afflicted becomes convinced an object they can see is a god. They must keep it in their "
     "possession at all times. Before making any meaningful decision, they must consult the object "
     "aloud. If they do not, they have disadvantage on the roll."),
    ("D20-2",  "Yellow Wallpaper",
     "Patterns crawl and shift in walls and floors, revealing imagined figures watching from within. "
     "The afflicted has disadvantage on Investigation checks. The first time each combat they target "
     "a creature, they roll a d6; on a 1–3, they instead target an illusory space and automatically miss."),
    ("D20-3",  "Verbal Disinhibition",
     "The afflicted verbalizes their internal thoughts unless they make a concerted effort not to. "
     "While suppressing this, they have disadvantage on skill checks and saving throws, cannot cast "
     "concentration spells, and speak in strained, broken sentences."),
    ("D20-4",  "Identity Delusion",
     "The afflicted adopts the personality of another character or NPC the DM decides, and fully "
     "believes they are that person. They speak, react, and make choices as that identity would, "
     "including using names and memories that aren't theirs."),
    ("D20-5",  "Insomnia",
     "Sleep refuses to hold the afflicted, and night terrors plague the mind. After a long rest, "
     "they must succeed on a DC 13 Constitution saving throw. On a failure, they still gain the "
     "long rest, but gain 1 level of exhaustion and regain only half their hit dice."),
    ("D20-6",  "Hypervigilant",
     "The afflicted's nerves never stop scanning; every creak is a threat, every shadow a knife. "
     "They cannot be surprised, but they have disadvantage on Stealth checks."),
    ("D20-7",  "Shared Suffering",
     "The afflicted feels pain they witness as if it is their own. Any damage dealt to any creature "
     "within 15 feet of the afflicted is halved, and the afflicted takes the other half as "
     "non-lethal psychic damage."),
    ("D20-8",  "Amnesia",
     "The afflicted remembers who they are and retains racial traits and class features, but they "
     "do not recognize other people or remember anything that happened before the madness took hold."),
    ("D20-9",  "Potion Delusion",
     "The afflicted clings to a powerful delusion that they drank an alchemical draught. The DM "
     "chooses a potion. The afflicted imagines they are under its effects and behaves accordingly."),
    ("D20-10", "Kleptomania",
     "The afflicted has an itch in the hands and a hunger in the eyes. They feel compelled to steal, "
     "even when doing so is foolish, impossible, or dangerous. They repeatedly attempt to take "
     "objects when an opportunity presents itself."),
    ("D20-11", "Flowers for Algernon",
     "For the first half of the duration, they have advantage on Intelligence ability checks and "
     "saving throws. For the remaining duration, they have disadvantage on Intelligence ability "
     "checks and saving throws."),
    ("D20-12", "Derealization",
     "The world feels distant and unreal, as though the afflicted is walking through a dream. "
     "They have resistance to psychic damage. Whenever they roll a d20, on an odd result they "
     "resolve the roll normally but are stunned until the end of their next turn."),
    ("D20-13", "Depersonalization",
     "The afflicted no longer believes they exist in the way others do. Whenever they roll a d20, "
     "on an even result, until the end of their next turn they cannot willingly target themself "
     "with attacks, abilities, or effects."),
    ("D20-14", "Confused",
     "The afflicted's thoughts scatter like frightened birds. Whenever they take damage, they must "
     "succeed on a DC 13 Wisdom saving throw or be affected as though they failed a saving throw "
     "against the confusion spell. The confusion effect lasts for 1 minute."),
    ("D20-15", "Hyperreactive Terror",
     "Fear breeds fear. Whenever the afflicted becomes frightened, they immediately gain another "
     "fear determined by the DM."),
    ("D20-16", "The Grand Conspiracy",
     "The afflicted becomes certain that every event and every person is part of a grand design; "
     "nothing is coincidence. They have advantage on Investigation and Perception checks, and "
     "disadvantage on all other ability checks."),
    ("D20-17", "Tunnel Vision",
     "The afflicted's sight narrows into a single harsh beam. They can only see clearly in a "
     "30-foot line directly ahead. Creatures outside this line have advantage on attack rolls "
     "against the afflicted. The afflicted gains +2 to ranged attack rolls against targets "
     "directly in front of them."),
    ("D20-18", "Tourettes",
     "The afflicted develops involuntary tics and vocalizations. Whenever they roll a d20, "
     "on an even result their speed becomes 0 until the start of their next turn."),
    ("D20-19", "Paranoia",
     "The afflicted's trust rots away. They become highly distrustful of others. They have "
     "disadvantage on Insight checks, and if they fail an Insight check they always assume "
     "the other creature is lying."),
    ("D20-20", "Unbreakable",
     "Once per long rest, when they would be reduced to 0 hit points but not killed outright, "
     "they instead drop to 1 hit point and remain standing. "
     "When this triggers, they gain 1 level of exhaustion."),
]

INDEFINITE_MADNESS_TABLE: List[Tuple[str, str, str]] = [
    ("D20-1",  "Out, Damned Spot!",
     "The afflicted is convinced their hands are stained with blood no one else can see. They must "
     "spend every short rest attempting to wash their hands and gain no benefits from that short rest. "
     "Alternatively, they may suppress the compulsion and gain the benefits, but must immediately "
     "increase all entries on their Fear List by one stage."),
    ("D20-2",  "Inferiority Complex",
     "The afflicted is consumed by the certainty that they are inadequate and will be exposed. "
     "They have disadvantage on ability checks using skills they are proficient in."),
    ("D20-3",  "Apathy",
     "The afflicted has lost interest in something they once cared about deeply; the spark simply "
     "isn't there anymore. They are no longer proficient in a skill of the DM's choice."),
    ("D20-4",  "Personality Split",
     "The afflicted fractures into multiple distinct selves. They gain a new personality and believe "
     "it is a separate person. After each long rest, roll a d20. On 9 or lower, the new personality "
     "is dominant. On 10 or higher, the original personality is dominant."),
    ("D20-5",  "Nihilism",
     "Nothing is real; the afflicted believes there is no inherent meaning, value, or purpose in "
     "life. They cannot benefit from Hope, Inspiration, Bardic Inspiration, guidance, bless, "
     "heroism, or any other morale or hope bonuses or spells."),
    ("D20-6",  "Despair",
     "Something in the afflicted breaks and does not cleanly mend. Roll a d6 (1=STR, 2=DEX, 3=CON, "
     "4=INT, 5=WIS, 6=CHA). The rolled ability score is permanently reduced by 1."),
    ("D20-7",  "Homicidal",
     "The afflicted develops a need to kill. They must make a DC 15 Wisdom saving throw at the end "
     "of each 24-hour period. On a failure, they become fixated on killing a creature the DM decides. "
     "They have disadvantage on all rolls until they kill that creature."),
    ("D20-8",  "Relentless Exhaustion",
     "The afflicted's body never truly recovers from the mental strain. "
     "They permanently have 1 level of exhaustion."),
    ("D20-9",  "Demoralizing Aura",
     "The afflicted becomes unpleasant to be around; people recoil without knowing why. "
     "Allies within 10 feet of the afflicted take a −1 penalty to all dice rolls."),
    ("D20-10", "Whom the Gods Would Destroy",
     "The afflicted's mind is broken. They can no longer rise above 75% of their sanity, "
     "and they permanently have a short-term madness effect active."),
    ("D20-11", "Masochist",
     "The afflicted seeks pain as proof they are still real. Each day, they cause themself harm "
     "and inflict a minor injury as determined by the DM."),
    ("D20-12", "Dead Soul",
     "Something inside has gone, as if the afflicted's spirit refuses to knit back together. "
     "Magical healing restores only half the normal number of hit points to them."),
    ("D20-13", "Age Regression",
     "The afflicted reverts backward into childhood. Their mannerisms change; their voice, posture, "
     "and personality shift to reflect a younger self. They behave as a young child would."),
    ("D20-14", "Suicidal Ideation",
     "The afflicted is haunted by a persistent desire to die. "
     "When they reach 0 hit points, they automatically fail all death saving throws."),
    ("D20-15", "Death Dread",
     "The afflicted is deathly afraid to die. When reduced below half their hit points, they become "
     "frightened of all hostile creatures until the end of their next turn. They have disadvantage "
     "on death saving throws. Add Death to their Fear List."),
    ("D20-16", "Self-Sabotage",
     "The afflicted cannot bear the weight of success. "
     "Whenever they roll a natural 20, they must reroll it."),
    ("D20-17", "The Metamorphosis",
     "The afflicted is convinced their body is no longer their own — something chitinous and shameful "
     "has replaced it. They believe they are a bug. Their speed is halved, and they have disadvantage "
     "on Charisma checks. When hit, they must succeed on a DC 15 Wisdom saving throw or fall prone."),
    ("D20-18", "Martyr",
     "The afflicted believes suffering makes them virtuous. When a party member within 30 feet would "
     "be reduced to 0 hit points, the afflicted uses a free action to prevent that damage entirely, "
     "but they immediately fall unconscious."),
    ("D20-19", "Corruption",
     "The afflicted's will bends toward darkness, and they desire to become a monster. Whenever they "
     "see a vampire or similar creature, they are automatically charmed by it for 1 minute. They have "
     "disadvantage on saving throws to resist a vampire's attempts to turn them."),
    ("D20-20", "The End of All Things",
     "The afflicted's sanity is shattered beyond conventional description. "
     "They become an NPC under DM control until Greater Restoration is administered."),
]

# ───────────────────────────────────────────────────────────────────────────
# WOUND TABLES
# ───────────────────────────────────────────────────────────────────────────

MINOR_WOUND_TABLE: List[Tuple[int, str, str]] = [
    (1,  "Shell Shocked",     "Disadvantage on Wisdom-based checks, saving throws, and attack rolls."),
    (2,  "Concussed",         "Disadvantage on Intelligence-based checks, saving throws, and attack rolls."),
    (3,  "Ringing Blow",      "You are temporarily Deafened."),
    (4,  "Hobbled",           "Speed reduced by 10 feet."),
    (5,  "Blood Loss",        "Reduce maximum hit points by 2d6."),
    (6,  "Infected Injury",   "You gain the Poisoned condition."),
    (7,  "Broken Bone",       "Disadvantage on Strength-based checks, saving throws, and attack rolls."),
    (8,  "Internal Injuries", "Disadvantage on Constitution-based checks, saving throws, and attack rolls."),
    (9,  "Blurred Vision",    "You are temporarily Blinded."),
    (10, "Minor Scar",        "Disadvantage on Charisma-based skill checks, except Intimidation (advantage)."),
    (11, "Staggered",         "You cannot take Bonus Actions."),
    (12, "Whiplash",          "-5 to Perception checks and Passive Perception."),
    (13, "Nerve Damage",      "You cannot take reactions."),
    (14, "Muscle Spasms",     "Disadvantage on Dexterity-based checks, saving throws, and attack rolls."),
    (15, "Unsteady",          "Disadvantage on Initiative rolls."),
    (16, "Chronic Pain",      "Gain one level of exhaustion."),
    (17, "Memory Loss",       "Short-term memory loss and disorientation."),
    (18, "Arm Injury",        "One arm is rendered useless."),
    (19, "Shaken",            "Disadvantage on Charisma-based checks, saving throws, and attack rolls."),
    (20, "Off Balance",       "-1 to AC until a Long Rest."),
]

MAJOR_WOUND_TABLE: List[Tuple[int, str, str]] = [
    (1,  "Lose an Eye",    "Disadvantage on Perception (sight) and ranged attack rolls. Regenerate restores."),
    (2,  "Lose Both Eyes", "You are blinded. Regenerate restores."),
    (3,  "Lose Fingers",   "Lose 1d3 fingers on one hand. Disadvantage on items held by that hand. Regenerate restores."),
    (4,  "Lose Hand",      "Cannot hold anything with two hands; only one item at a time. Regenerate restores."),
    (5,  "Lose Arm",       "Cannot hold two-handed items; disadvantage on Athletics. Regenerate restores."),
    (6,  "Lame",           "Speed -5 ft. DC 10 DEX save after Dash or fall prone. 20+ HP magical healing cures."),
    (7,  "Severe Limp",    "Speed -10 ft. DC 15 DEX save after Dash or fall prone. 40+ HP magical healing cures."),
    (8,  "Lose a Foot",    "Speed halved; need cane/crutch. Fall prone after Dash. Disadvantage DEX (balance). Regenerate restores."),
    (9,  "Lose a Leg",     "Speed halved; need cane/crutch. Fall prone after Dash. Disadvantage all DEX checks. Regenerate restores."),
    (10, "Chronic Injury", "HP max reduced by 1d3 every 24h. 0 HP max = death. 40+ HP healing or DC 20 Medicine (4h surgery) cures."),
    (11, "Crippled",       "Reduce Strength by 1d3. Greater Restoration cures."),
    (12, "Mutilated",      "Reduce Dexterity by 1d3. Greater Restoration cures."),
    (13, "Maimed",         "Reduce Constitution by 1d3. Greater Restoration cures."),
    (14, "Brain Injury",   "Reduce Charisma by 1d3. Greater Restoration cures."),
    (15, "Deep Coma",      "Incapacitated. DC 20 WIS save at end of each long rest to remove."),
    (16, "Bodily Strain",  "Gain 1d6 levels of exhaustion (cannot be removed normally; Greater Restoration removes one level)."),
]

# ───────────────────────────────────────────────────────────────────────────
# RULES TEXT
# ───────────────────────────────────────────────────────────────────────────

FEAR_RULES_TEXT = (
    "FEAR & SANITY SYSTEM\n"
    "Max Sanity = 15 + WIS score\n\n"
    "FEAR ENCOUNTERS\n"
    "1. Select a fear and trigger Encounter\n"
    "2. Severity effects apply IMMEDIATELY\n"
    "3. Roll WIS Save: d20 + WIS mod vs DC\n"
    "   DC = base 12 + desensitization DC\n"
    "4. Pass → encounter ends\n"
    "5. Fail → roll Xd4 (based on severity)\n"
    "   Confront: lose that many sanity\n"
    "             desensitization rung +1\n"
    "   Avoid:    recover that much sanity\n"
    "             fear severity +1\n"
    "             desensitization rung -1\n\n"
    "SEVERITY LEVELS:\n"
    "1 - Low Severity      (1d4 on fail)\n"
    "    Disadvantage on checks\n"
    "2 - Moderate Severity (2d4 on fail)\n"
    "    Frightened Condition\n"
    "3 - High Severity     (3d4 on fail)\n"
    "    Frightened + Incapacitated\n"
    "4 - Extreme Severity  (4d4 on fail)\n"
    "    Frightened + Prone + Unconscious\n"
    "    +1 Exhaustion on encounter start\n"
    "    Avoid → new random fear added\n\n"
    "DESENSITIZATION:\n"
    "Rung 1 (Low)     DC 16 — Minimal exposure\n"
    "Rung 2 (Moderate) DC 14 — Familiar but raw\n"
    "Rung 3 (High)     DC 12 — Internalised\n"
    "Rung 4 (Extreme)  DC 10 — Part of you now"
)

MADNESS_RULES_TEXT = (
    "MADNESS SYSTEM\n\n"
    "THRESHOLDS (auto-triggered):\n"
    "  Below 75% → Short-Term Madness\n"
    "  Below 50% → Long-Term Madness\n"
    "  Below 25% → Indefinite Madness\n"
    "  0 Sanity  → DM controls character\n\n"
    "DURATIONS:\n"
    "  Short-Term  → 1d10 minutes\n"
    "  Long-Term   → 1d10 x 10 hours\n"
    "  Indefinite  → Until cured\n\n"
    "CURING MADNESS:\n"
    "  Short-Term  → Minor Restoration / rest\n"
    "  Long-Term   → Minor Restoration\n"
    "  Indefinite  → Major Restoration\n\n"
    "MADNESS TABLES: D20 named entries\n"
    "Each roll produces a named effect\n"
    "with unique mechanical consequence."
)

WOUND_RULES_TEXT = (
    "LINGERING WOUNDS SYSTEM\n\n"
    "TRIGGER: When a creature drops to 0 HP or\n"
    "suffers a critical hit, it must make a CON save.\n\n"
    "DC = 10 (or half damage taken, whichever higher)\n\n"
    "OUTCOMES:\n"
    "  Pass by 5+  → No wound\n"
    "  Pass        → Minor Wound (d20 table)\n"
    "  Fail        → Major Wound (d16 table)\n"
    "  Fail by 5+  → Major Wound + 1 Exhaustion\n\n"
    "HEALING:\n"
    "  Minor → Minor Restoration or Long Rest\n"
    "  Major → Major Restoration\n"
    "          Major Restoration also regenerates\n"
    "          lost body parts when removing\n"
    "          a qualifying Major Wound."
)

SPELL_RULES_TEXT = (
    "HEALING SPELLS\n\n"
    "MINOR RESTORATION:\n"
    "  Removes one Short-Term or Long-Term\n"
    "  madness entry, OR cures one Minor Wound.\n\n"
    "MAJOR RESTORATION:\n"
    "  Removes one Indefinite madness entry,\n"
    "  OR cures one Major Wound (also regenerates\n"
    "  lost body parts where applicable).\n\n"
    "Use the dropdowns to select the specific\n"
    "madness or wound to target before casting."
)

# ───────────────────────────────────────────────────────────────────────────
# UTILITY
# ───────────────────────────────────────────────────────────────────────────

def clamp(x, lo, hi):   return max(lo, min(hi, x))
def lerp(a, b, t):       return a + (b - a) * t
def smoothstep(t):
    t = clamp(t, 0.0, 1.0); return t * t * (3.0 - 2.0 * t)
def roll_d(sides: int, n: int = 1) -> List[int]:
    return [random.randint(1, sides) for _ in range(n)]
def safe_int(raw: str, *, lo=None, hi=None) -> int:
    v = int(raw.strip())
    if lo is not None and v < lo: raise ValueError
    if hi is not None and v > hi: raise ValueError
    return v
def hex_lerp(c1: str, c2: str, t: float) -> str:
    r1,g1,b1 = int(c1[1:3],16), int(c1[3:5],16), int(c1[5:7],16)
    r2,g2,b2 = int(c2[1:3],16), int(c2[3:5],16), int(c2[5:7],16)
    return f"#{int(lerp(r1,r2,t)):02x}{int(lerp(g1,g2,t)):02x}{int(lerp(b1,b2,t)):02x}"
def stat_modifier(score: int) -> int:
    return (score - 10) // 2
def hex_to_kivy(h: str):
    r = int(h[1:3],16)/255; g = int(h[3:5],16)/255; b = int(h[5:7],16)/255
    return (r, g, b, 1)

def roll_random_madness(kind: str) -> Tuple[str, str, str]:
    """Returns (roll_label, name, effect) from D20 named table."""
    if kind == "short":
        entry = random.choice(SHORT_TERM_MADNESS_TABLE)
    elif kind == "long":
        entry = random.choice(LONG_TERM_MADNESS_TABLE)
    elif kind == "indefinite":
        entry = random.choice(INDEFINITE_MADNESS_TABLE)
    else:
        return ("??", "Unknown", "Unknown madness type.")
    return entry  # (roll_label, name, effect)

def roll_random_wound(severity: str) -> Tuple[int, str, str]:
    if severity == "minor": return random.choice(MINOR_WOUND_TABLE)
    else:                   return random.choice(MAJOR_WOUND_TABLE)

# ───────────────────────────────────────────────────────────────────────────
# ENUMS
# ───────────────────────────────────────────────────────────────────────────

class MadnessStage(Enum):
    STABLE=auto(); SHORT_TERM=auto(); LONG_TERM=auto()
    INDEFINITE=auto(); ZERO=auto()

    @staticmethod
    def from_state(pct: float, current: int) -> MadnessStage:
        if current == 0:   return MadnessStage.ZERO
        if pct < 0.25:     return MadnessStage.INDEFINITE
        if pct < 0.50:     return MadnessStage.LONG_TERM
        if pct < 0.75:     return MadnessStage.SHORT_TERM
        return MadnessStage.STABLE

class EncounterPhase(Enum):
    IDLE=auto(); AWAITING_SAVE=auto(); AWAITING_CHOICE=auto()

class WoundEncPhase(Enum):
    IDLE=auto(); AWAITING_SAVE=auto(); RESOLVED=auto()

# ───────────────────────────────────────────────────────────────────────────
# STATIC INFO DICTS
# ───────────────────────────────────────────────────────────────────────────

@dataclass
class MadnessInfo:
    title: str; desc: str; color: str; bar_dark: str; bar_light: str

MADNESS: Dict[MadnessStage, MadnessInfo] = {
    MadnessStage.STABLE:     MadnessInfo("STABLE",             "No madness effects.",                              "#78b083","#4f7d58","#78b083"),
    MadnessStage.SHORT_TERM: MadnessInfo("SHORT-TERM MADNESS", "Roll on Short-Term table.\n1d10 minutes.",        "#c8a44e","#9e7a28","#d4b04a"),
    MadnessStage.LONG_TERM:  MadnessInfo("LONG-TERM MADNESS",  "Roll on Long-Term table.\n1d10 x 10 hours.",     "#c07838","#9a5e28","#c88a48"),
    MadnessStage.INDEFINITE: MadnessInfo("INDEFINITE MADNESS", "Roll on Indefinite table.\nLasts until cured.",  "#8c3838","#7a2828","#a84848"),
    MadnessStage.ZERO:       MadnessInfo("INSANITY",           "DM takes full control.\nThe mind is shattered.", "#2a0808","#1a0808","#3a1818"),
}

@dataclass
class FearStageInfo:
    name: str; desc: str; dice: int; color: str

FEAR_STAGES: Dict[int, FearStageInfo] = {
    1: FearStageInfo(
        "Low Severity",
        "Disadvantage on ability checks involving the fear.",
        1, "#50a870"),
    2: FearStageInfo(
        "Moderate Severity",
        "Frightened Condition.",
        2, "#c8a44e"),
    3: FearStageInfo(
        "High Severity",
        "Frightened + Incapacitated until end of next turn. "
        "Then: disadvantage on attacks, checks, saves for encounter.",
        3, "#d08040"),
    4: FearStageInfo(
        "Extreme Severity",
        "Frightened. Fall Prone & Unconscious (stable). "
        "Unconscious 1 min or until ally snaps you out. "
        "+1 Exhaustion on encounter. "
        "AVOID at Extreme Severity → auto-adds 1 new random fear.",
        4, "#c44040"),
}

# ───────────────────────────────────────────────────────────────────────────
# DATACLASSES
# ───────────────────────────────────────────────────────────────────────────

@dataclass
class MadnessEntry:
    kind: str; roll_range: str; effect: str; timestamp: str = ""; name: str = ""

    def to_dict(self):
        return {"kind":self.kind,"roll_range":self.roll_range,
                "effect":self.effect,"timestamp":self.timestamp,"name":self.name}

    @staticmethod
    def from_dict(d: dict) -> MadnessEntry:
        return MadnessEntry(kind=d.get("kind","short"),
                            roll_range=d.get("roll_range","??"),
                            effect=d.get("effect","Unknown"),
                            timestamp=d.get("timestamp",""),
                            name=d.get("name",""))

    @property
    def kind_label(self):
        return {"short":"Short-Term","long":"Long-Term","indefinite":"Indefinite"}.get(self.kind,"???")

    @property
    def kind_color(self):
        return {"short":"#c8a44e","long":"#c07838","indefinite":"#8c3838"}.get(self.kind,"#d4c5a0")


@dataclass
class WoundEntry:
    description: str; effect: str; severity: str; timestamp: str = ""

    def to_dict(self):
        return {"description":self.description,"effect":self.effect,
                "severity":self.severity,"timestamp":self.timestamp}

    @staticmethod
    def from_dict(d: dict) -> WoundEntry:
        return WoundEntry(description=d.get("description","Unknown wound"),
                          effect=d.get("effect",""),
                          severity=d.get("severity","minor"),
                          timestamp=d.get("timestamp",""))


@dataclass
class SanityState:
    wis_score: int = 10; con_score: int = 10
    max_sanity: int = 25; current_sanity: int = 25
    exhaustion: int = 0
    fired_thresholds: set = field(default_factory=set)
    wounds: List[WoundEntry] = field(default_factory=list)
    madnesses: List[MadnessEntry] = field(default_factory=list)
    hope: bool = False

    @property
    def percent(self): return self.current_sanity/self.max_sanity if self.max_sanity else 0.0
    @property
    def madness(self): return MadnessStage.from_state(self.percent, self.current_sanity)
    @property
    def wis_mod(self): return stat_modifier(self.wis_score)
    @property
    def con_mod(self): return stat_modifier(self.con_score)
    @property
    def minor_wounds(self): return [w for w in self.wounds if w.severity=="minor"]
    @property
    def major_wounds(self): return [w for w in self.wounds if w.severity=="major"]

    def recalc_and_reset(self):
        self.max_sanity = SANITY_BASE + self.wis_score
        self.current_sanity = self.max_sanity; self.fired_thresholds.clear()

    def apply_loss(self, amt: int):
        amt = max(0,amt); old = self.current_sanity
        self.current_sanity = max(0, self.current_sanity - amt)
        return self._check(old, self.current_sanity)

    def apply_recovery(self, amt: int):
        self.current_sanity = min(self.max_sanity, self.current_sanity + max(0,amt))
        self.rebuild_thresholds()

    def rebuild_thresholds(self):
        pct = self.percent; self.fired_thresholds.clear()
        for _,c,_ in THRESHOLDS:
            if pct <= c: self.fired_thresholds.add(c)

    def add_wound(self, desc, effect, severity) -> WoundEntry:
        w = WoundEntry(description=desc, effect=effect, severity=severity,
                       timestamp=datetime.now().strftime("%H:%M"))
        self.wounds.append(w); return w

    def add_madness(self, kind: str, custom_effect: str = "") -> MadnessEntry:
        """Add a madness entry. Rolled madness uses D20 named table; custom uses provided text."""
        if custom_effect:
            name = self._next_madness_name(kind)
            m = MadnessEntry(kind=kind, roll_range="Custom", effect=custom_effect,
                             timestamp=datetime.now().strftime("%H:%M"), name=name)
        else:
            roll_label, entry_name, effect = roll_random_madness(kind)
            m = MadnessEntry(kind=kind, roll_range=roll_label, effect=effect,
                             timestamp=datetime.now().strftime("%H:%M"), name=entry_name)
        self.madnesses.append(m)
        return m

    def snapshot(self):
        return {"wis":self.wis_score,"con":self.con_score,
                "max":self.max_sanity,"cur":self.current_sanity,
                "exh":self.exhaustion,"fired":list(self.fired_thresholds),
                "wounds":[w.to_dict() for w in self.wounds],
                "madnesses":[m.to_dict() for m in self.madnesses],
                "hope":self.hope}

    def restore(self, s):
        self.wis_score=s["wis"]; self.con_score=s.get("con",10)
        self.max_sanity=s["max"]; self.current_sanity=s["cur"]
        self.exhaustion=s.get("exh",0)
        self.fired_thresholds=set(s["fired"])
        self.wounds=[WoundEntry.from_dict(w) for w in s.get("wounds",[])]
        self.madnesses=[MadnessEntry.from_dict(m) for m in s.get("madnesses",[])]
        self.hope=s.get("hope",False)
        self._backfill_madness_names()

    def _check(self, old, new):
        msgs=[]
        if not self.max_sanity: return msgs
        op,np_=old/self.max_sanity, new/self.max_sanity
        for label,c,kind in THRESHOLDS:
            if op>c and np_<=c and c not in self.fired_thresholds:
                self.fired_thresholds.add(c); msgs.append((label,kind))
        return msgs

    def _next_madness_name(self, kind: str) -> str:
        label = {"short": "Short-Term", "long": "Long-Term",
                 "indefinite": "Indefinite"}.get(kind, "Madness")
        prefix = f"{label} Effect "
        n = 1; used = set()
        for m in self.madnesses:
            if not m.name.startswith(prefix): continue
            tail = m.name[len(prefix):].strip()
            if tail.isdigit(): used.add(int(tail))
        while n in used: n += 1
        return f"{prefix}{n}"

    def _backfill_madness_names(self):
        for m in self.madnesses:
            if not m.name.strip():
                m.name = self._next_madness_name(m.kind)


class FearManager:
    def __init__(self):
        self.fears: Dict[str, int] = {}
        self.desens: Dict[str, int] = {}   # fear name → desensitization rung 1-4

    @property
    def sorted_names(self): return sorted(self.fears.keys(), key=str.lower)

    def add(self, name: str, stage: int = 1):
        name = name.strip()
        if not name: return "Enter a fear name."
        low = {k.lower(): k for k in self.fears}
        if name.lower() in low: return f"Already exists: '{low[name.lower()]}'"
        self.fears[name] = int(clamp(stage, 1, 4))
        self.desens[name] = 1   # Start at Low desensitization
        return None

    def remove(self, n: str):
        self.desens.pop(n, None)
        return bool(self.fears.pop(n, None))

    def set_stage(self, n: str, s: int):
        if n in self.fears: self.fears[n] = int(clamp(s, 1, 4))

    def get_stage(self, n: str) -> int:
        return self.fears.get(n, 1)

    def increment_stage(self, n: str) -> int:
        old = self.get_stage(n); new = min(4, old + 1)
        self.fears[n] = new; return new

    def get_desens(self, n: str) -> int:
        return self.desens.get(n, 1)

    def set_desens(self, n: str, rung: int):
        if n in self.fears: self.desens[n] = int(clamp(rung, 1, 4))

    def incr_desens(self, n: str) -> int:
        old = self.get_desens(n); new = min(4, old + 1)
        self.desens[n] = new; return new

    def decr_desens(self, n: str) -> int:
        old = self.get_desens(n); new = max(1, old - 1)
        self.desens[n] = new; return new

    def add_random(self) -> Optional[str]:
        pool = [f for f in SIMPLE_FEAR_POOL if f.lower() not in {k.lower() for k in self.fears}]
        if not pool: return None
        n = random.choice(pool)
        self.fears[n] = 1
        self.desens[n] = 1
        return n

    def suggest(self) -> Optional[str]:
        pool = [f for f in SIMPLE_FEAR_POOL if f.lower() not in {k.lower() for k in self.fears}]
        return random.choice(pool) if pool else None

    def snapshot(self) -> dict:
        return {"fears": dict(self.fears), "desens": dict(self.desens)}

    def restore(self, s):
        # Handle both new format {"fears": {...}, "desens": {...}} and legacy flat dict
        if isinstance(s, dict) and "fears" in s:
            raw = s["fears"]
            raw_desens = s.get("desens", {})
        elif isinstance(s, dict):
            # Legacy: entire dict was just fears
            raw = s; raw_desens = {}
        else:
            raw = {}; raw_desens = {}

        self.fears = {str(k): int(clamp(v, 1, 4)) for k, v in raw.items()}
        self.desens = {str(k): int(clamp(v, 1, 4)) for k, v in raw_desens.items()}
        # Back-fill desens for fears that have no rung yet
        for k in self.fears:
            if k not in self.desens:
                self.desens[k] = 1


@dataclass
class EncounterState:
    phase: EncounterPhase = EncounterPhase.IDLE
    fear_name: Optional[str] = None
    fear_stage: Optional[int] = None
    roll_total: Optional[int] = None
    roll_text: Optional[str] = None
    wis_save_total: Optional[int] = None

    def reset(self):
        self.phase = EncounterPhase.IDLE
        self.fear_name = self.fear_stage = None
        self.roll_total = self.roll_text = self.wis_save_total = None

    @property
    def active(self): return self.phase != EncounterPhase.IDLE


@dataclass
class WoundEncounterState:
    phase: WoundEncPhase = WoundEncPhase.IDLE
    dc: int = 10; damage_taken: int = 0
    roll_total: Optional[int] = None; con_mod_used: int = 0; result_text: str = ""

    def reset(self):
        self.phase = WoundEncPhase.IDLE; self.dc = 10; self.damage_taken = 0
        self.roll_total = None; self.con_mod_used = 0; self.result_text = ""

    @property
    def active(self): return self.phase != WoundEncPhase.IDLE


class SaveManager:
    def __init__(self, user_data_dir: str = ""):
        if user_data_dir:
            self._path = Path(user_data_dir) / SAVE_FILE_NAME
        elif os.name == "nt":
            base = Path(os.environ.get("APPDATA", Path.home()/"AppData/Roaming"))
            self._path = base / "SanityFearMadnessTrackerAppData" / SAVE_FILE_NAME
        elif sys.platform == "darwin":
            self._path = Path.home()/"Library/Application Support/SanityFearMadnessTrackerAppData"/SAVE_FILE_NAME
        else:
            base = Path(os.environ.get("XDG_CONFIG_HOME", Path.home()/".config"))
            self._path = base / "SanityFearMadnessTrackerAppData" / SAVE_FILE_NAME
        self._path.parent.mkdir(parents=True, exist_ok=True)

    def save(self, st: SanityState, fm: FearManager, char_name: str, enc_history: list):
        data = {"wis": st.wis_score, "con": st.con_score, "cur": st.current_sanity,
                "exh": st.exhaustion, "hope": st.hope,
                "fears": fm.snapshot(), "char_name": char_name,
                "enc_history": enc_history[-20:],
                "wounds": [w.to_dict() for w in st.wounds],
                "madnesses": [m.to_dict() for m in st.madnesses]}
        try:
            self._path.write_text(json.dumps(data, indent=2), encoding="utf-8")
            return None
        except Exception as e:
            return str(e)

    def load(self):
        if not self._path.exists(): return None
        try: return json.loads(self._path.read_text(encoding="utf-8"))
        except: return None


class UndoStack:
    def __init__(self, limit=UNDO_STACK_LIMIT):
        self._s: list = []; self._limit = limit

    def push(self, st: SanityState, fm: FearManager):
        self._s.append((st.snapshot(), fm.snapshot()))
        if len(self._s) > self._limit: self._s.pop(0)

    def pop(self): return self._s.pop() if self._s else None

    @property
    def can_undo(self): return bool(self._s)
