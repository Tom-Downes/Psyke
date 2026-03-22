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
FEAR_ENC_DC        = 10
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

# Per-rung blues — decreasing brightness (Low=brightest, Extreme=darkest)
DESENS_RUNG_COLORS: Dict[int, str] = {
    1: "#78d4ff",   # Low      — bright azure (least desensitized)
    2: "#3898d8",   # Moderate — medium blue
    3: "#1a5faa",   # High     — deep blue
    4: "#0c3272",   # Extreme  — dark navy (most desensitized)
}

# ───────────────────────────────────────────────────────────────────────────
# D20 MADNESS TABLES  (roll_label, name, effect)
# ───────────────────────────────────────────────────────────────────────────

SHORT_TERM_MADNESS_TABLE: List[Tuple[str, str, str]] = [
    ("1",  "Black Out",
     "The afflicted's vision gutters out, and they collapse. They fall unconscious, but do not lose hit points and are stable. Another creature can use an action to shake them awake, ending the effect."),
    ("2",  "Tell-Tale Heart",
     "The afflicted hears a loud, relentless heartbeat drowning out all other sound. They are deafened, and have disadvantage on attack rolls made against creatures behind them."),
    ("3",  "Pyric Delusion",
     "The afflicted is certain their clothes and gear are burning their skin. On their turn, they use their action to doff their clothing and armour down to underclothes, believing it is the source of the pain. They refuse to don the removed clothing or armour until the madness ends."),
    ("4",  "Tremors",
     "The afflicted develops uncontrollable tremors and tics that ruin precision and leverage. They have disadvantage on Strength and Dexterity ability checks, and disadvantage on attack rolls."),
    ("5",  "Pica",
     "The afflicted is seized by an overpowering craving to eat something unnatural - dirt, slime, wax, hair, or worse. If such a substance is within reach, they must use their action to consume it (or try to), unless physically prevented."),
    ("6",  "Formication",
     "The afflicted feels insects crawling beneath their skin, scratching and tunnelling. At the end of each of their turns in which they did not take damage, they take 1d4 slashing damage as they claw at themself to dig the 'bugs' out. This continues until the madness ends or until they have lost half of their current hit points (from the moment the madness began) from this effect."),
    ("7",  "Separation Anxiety",
     "The afflicted becomes convinced they will die if left alone. Choose a random ally the afflicted can see when the madness begins. The afflicted is compelled to remain within 5 feet of that ally. While farther than 5 feet from that ally, the afflicted has disadvantage on all rolls."),
    ("8",  "Fear",
     "The afflicted's mind latches onto a nearby omen of doom. The DM chooses a nearby trigger. The afflicted becomes frightened of that trigger. Add that trigger to the afflicted's Fear List."),
    ("9",  "Safe Space",
     "The afflicted fixates on a 15-foot by 15-foot area as the only place they can survive. They believe they will die if they leave it. They become fiercely territorial: if another creature enters the area, the afflicted attacks any creature in the area (prioritizing those who entered the 'safe zone')."),
    ("10", "Frenzied",
     "The afflicted froths at the mouth as panic and violence take over reason. Each round, they must use their action to attack the nearest creature."),
    ("11", "Babbling",
     "The afflicted's thoughts spill out in tangled, feverish nonsense. They are incapable of normal speech and cannot form the focus needed for magic. They cannot speak coherently or cast spells."),
    ("12", "Hysterical Weeping",
     "The afflicted begins uncontrollably weeping - shaking breaths, blurred vision, tears they cannot stop - yet can otherwise act normally. They have disadvantage on Perception checks that rely on sight."),
    ("13", "No Truce with the Furies",
     "The afflicted is convinced unseen adversaries are chasing them. They cannot end their turn within 20 feet of where they began it. If they would end their turn within 20 feet of where they began, they must use their reaction (if available) to move until they end their turn outside that boundary."),
    ("14", "Phantom Infant",
     "The afflicted becomes absolutely convinced they are holding a baby in their off-hand. If they were holding something in that hand, they drop it as the 'baby' takes its place. They behave as though that hand is occupied for the duration."),
    ("15", "Gold Purge",
     "The afflicted becomes convinced their gold is trying to kill them. While affected, they must use their bonus action each turn to remove 1d20 gp from wherever they store it and throw it on the ground."),
    ("16", "Hallucinations",
     "The afflicted experiences vivid hallucinations - faces in fog, movement at the edge of vision, whispers in another voice. They have disadvantage on ability checks."),
    ("17", "Startled",
     "The afflicted is wound so tight that any sudden movement snaps their body into reflex. Whenever a creature moves within 5 feet of the afflicted, they must succeed on a DC 10 Dexterity saving throw or drop what they're holding as a reaction (if they have one). On a failed save, their speed becomes 0 until the start of their next turn."),
    ("18", "Hypersensitive",
     "Every wound affects not only the body but the mind. Whenever the afflicted takes damage, they take 1 additional psychic damage per die rolled as part of that damage."),
    ("19", "Emotional Numbness",
     "The afflicted goes cold inside. They are immune to being charmed, but they have disadvantage on Charisma ability checks."),
    ("20", "Adrenaline",
     "The afflicted becomes suffused with adrenaline. They gain advantage on all attack rolls. When the madness ends, they gain 1 level of exhaustion."),
]

LONG_TERM_MADNESS_TABLE: List[Tuple[str, str, str]] = [
    ("1",  "Object Deification",
     "The afflicted becomes convinced an object they can see is a god. They must keep it in their possession at all times. Before making any meaningful decision (attacks, spell targets, skill checks, movement choices), they must consult the object aloud. If they do not, they have disadvantage on the roll."),
    ("2",  "Yellow Wallpaper",
     "Patterns crawl and shift in walls and floors, revealing imagined figures watching from within. The afflicted has disadvantage on Investigation checks. The first time each combat they target a creature, they roll a d6; on a 1-3, they instead target an illusory space and automatically miss."),
    ("3",  "Verbal Disinhibition",
     "The afflicted verbalizes their internal thoughts unless they make a concerted effort not to. While suppressing this, they have disadvantage on skill checks and saving throws, cannot cast concentration spells, and speak in strained, broken sentences."),
    ("4",  "Identity Delusion",
     "The afflicted adopts the personality of another character or NPC the DM decides, and fully believes they are that person. They speak, react, and make choices as that identity would, including using names and memories that aren't theirs."),
    ("5",  "Insomnia",
     "Sleep refuses to hold the afflicted, and night terrors plague the mind. After a long rest, they must succeed on a DC 13 Constitution saving throw. On a failure, they still gain the long rest, but gain 1 level of exhaustion and regain only half their hit dice."),
    ("6",  "Hypervigilant",
     "The afflicted's nerves never stop scanning; every creak is a threat, every shadow a knife. They cannot be surprised, but they have disadvantage on Stealth checks."),
    ("7",  "Shared Suffering",
     "The afflicted feels pain they witness as if it is their own. Any damage dealt to any creature within 15 feet of the afflicted is halved, and the afflicted takes the other half as non-lethal psychic damage."),
    ("8",  "Amnesia",
     "The afflicted remembers who they are and retains racial traits and class features, but they do not recognize other people or remember anything that happened before the madness took hold."),
    ("9",  "Potion Delusion",
     "The afflicted clings to a powerful delusion that they drank an alchemical draught. The DM chooses a potion. The afflicted imagines they are under its effects and behaves accordingly."),
    ("10", "Kleptomania",
     "The afflicted has an itch in the hands and a hunger in the eyes. They feel compelled to steal, even when doing so is foolish, impossible, or dangerous. They repeatedly attempt to take objects when an opportunity presents itself."),
    ("11", "Flowers for Algernon",
     "The afflicted's mind blooms and then collapses. For the first half of the duration, they have advantage on Intelligence ability checks and advantage on Intelligence saving throws. For the remaining duration, they have disadvantage on Intelligence ability checks and disadvantage on Intelligence saving throws."),
    ("12", "Derealization",
     "The world feels distant and unreal, as though the afflicted is walking through a dream. They have resistance to psychic damage. Whenever they roll a d20, on an odd result they resolve the roll normally, but are stunned until the end of their next turn."),
    ("13", "Depersonalization",
     "The afflicted no longer believes they exist in the way others do. They think others cannot truly notice, perceive, or interact with them. Whenever they roll a d20, on an even result, until the end of their next turn they cannot willingly target themself with attacks, abilities, or effects."),
    ("14", "Confused",
     "The afflicted's thoughts scatter like frightened birds. Whenever they take damage, they must succeed on a DC 13 Wisdom saving throw or be affected as though they failed a saving throw against the confusion spell. The confusion effect lasts for 1 minute."),
    ("15", "Hyperreactive Terror",
     "Fear breeds fear. Whenever the afflicted becomes frightened, they immediately gain another fear determined by the DM."),
    ("16", "The Grand Conspiracy",
     "The afflicted becomes certain that every event and every person is part of Strahd's design; nothing is coincidence. They have advantage on Investigation and Perception checks, and disadvantage on all other ability checks."),
    ("17", "Tunnel Vision",
     "The afflicted's sight narrows into a single harsh beam. They can only see clearly in a 30-foot line directly ahead. Creatures outside this line have advantage on attack rolls against the afflicted. The afflicted gains a +2 bonus to ranged attack rolls against targets directly in front of them."),
    ("18", "Tourettes",
     "The afflicted develops involuntary tics and vocalizations. Whenever they roll a d20, on an even result their speed becomes 0 until the start of their next turn."),
    ("19", "Paranoia",
     "The afflicted's trust rots away. They become highly distrustful of others. They have disadvantage on Insight checks, and if they fail an Insight check they always assume the other creature is lying."),
    ("20", "Unbreakable",
     "Something inside the afflicted has calcified into iron. Once per long rest, when they would be reduced to 0 hit points but not killed outright, they instead drop to 1 hit point and remain standing. When this triggers, they gain 1 level of exhaustion."),
]

INDEFINITE_MADNESS_TABLE: List[Tuple[str, str, str]] = [
    ("1",  "Out, Damned Spot!",
     "The afflicted is convinced their hands are stained with blood no one else can see. They must spend every short rest attempting to wash their hands and gain no benefits from that short rest. Alternatively, they may suppress the compulsion and gain the benefits of the short rest, but they must immediately increase all entries on their Fear List by one stage."),
    ("2",  "Inferiority Complex",
     "The afflicted is consumed by the certainty that they are inadequate and will be exposed. They have disadvantage on ability checks using skills they are proficient in."),
    ("3",  "Apathy",
     "The afflicted has lost interest in something they once cared about deeply; the spark simply isn't there anymore. They are no longer proficient in a skill of the DM's choice."),
    ("4",  "Personality Split",
     "The afflicted fractures into multiple distinct selves. They gain a new personality and believe it is a separate person who has always been that way since birth. After each long rest, roll a d20. On a result of 9 or lower, the new personality is dominant. On a result of 10 or higher, the original personality is dominant."),
    ("5",  "Nihilism",
     "Nothing is real; the afflicted believes there is no inherent meaning, value, or purpose in life. They cannot benefit from Hope, Inspiration, Bardic Inspiration, guidance, bless, heroism, or any other morale or hope bonuses or spells."),
    ("6",  "Despair",
     "Something in the afflicted breaks and does not cleanly mend. Roll a d6 (1=STR, 2=DEX, 3=CON, 4=INT, 5=WIS, 6=CHA). The rolled ability score is permanently reduced by 1."),
    ("7",  "Homicidal",
     "The afflicted develops a need to kill. They must make a DC 15 Wisdom saving throw at the end of each 24-hour period. On a success, they suppress the urge for another 24 hours. On a failure, they become fixated on killing a creature the DM decides. They have disadvantage on all rolls until they kill that creature. If they cannot reach it within 24 hours, they gain 1 level of exhaustion."),
    ("8",  "Relentless Exhaustion",
     "The afflicted's body never truly recovers from the mental strain. They permanently have 1 level of exhaustion."),
    ("9",  "Demoralizing Aura",
     "The afflicted becomes unpleasant to be around; people recoil without knowing why. Allies within 10 feet of the afflicted take a -1 penalty to all dice rolls."),
    ("10", "Whom the Gods Would Destroy",
     "The afflicted mind is broken; they are in a perpetual state of madness. They can no longer rise above 75% of their sanity, and they permanently have a short-term madness effect active."),
    ("11", "Masochist",
     "The afflicted seeks pain as proof they are still real. Each day, they cause themself harm and inflict a minor injury (as determined by the DM)."),
    ("12", "Dead Soul",
     "Something inside has gone, as if the afflicted's spirit refuses to knit back together. Magical healing restores only half the normal number of hit points to them."),
    ("13", "Age Regression",
     "The afflicted reverts backward into childhood. Their mannerisms change; their voice, posture, and personality shift to reflect a younger self. They behave as a young child would, responding to situations as they once did in earlier life."),
    ("14", "Suicidal Ideation",
     "The afflicted is haunted by a persistent desire to die. When they reach 0 hit points, they automatically fail all death saving throws."),
    ("15", "Death Dread",
     "The afflicted is deathly afraid to die. When reduced below half their hit points, they become frightened of all hostile creatures until the end of their next turn. They have disadvantage on death saving throws. Add Death to their Fear List."),
    ("16", "Self-Sabotage",
     "The afflicted cannot bear the weight of success and will always try to stop themselves from succeeding. Whenever they roll a natural 20, they must reroll it."),
    ("17", "The Metamorphosis",
     "The afflicted is convinced their body is no longer their own - something chitinous, crawling, and shameful has replaced it. They believe they are a bug. Their speed is halved, and they have disadvantage on Charisma checks. When they are hit, they must succeed on a DC 15 Wisdom saving throw or fall prone."),
    ("18", "Martyr",
     "The afflicted believes suffering makes them virtuous, and that their pain redeems others. When they could avoid damage with a reaction, they must succeed on a DC 15 Wisdom saving throw or choose not to use it. When a party member within 30 feet would be reduced to 0 hit points, the afflicted uses a free action to prevent that damage entirely, but they immediately fall unconscious."),
    ("19", "Corruption",
     "The afflicted's will bends toward the vampire, and they desire to become one. Whenever they see a vampire, they are automatically charmed by it for 1 minute. They have disadvantage on saving throws to resist a vampire's attempts to turn them."),
    ("20", "Fearless",
     "The afflicted does not fear. Fear is the mind-killer. Fear is the little-death that brings total obliteration. The afflicted will face their fear. They will permit it to pass over them and through them. And when it has gone past, they will turn the inner eye to see its path. Where the fear has gone there will be nothing. Only they will remain. They are immune to being frightened. The Fear system no longer applies to them: they cannot gain new fears, and all entries on their Fear List are permanently erased"),
]

# ───────────────────────────────────────────────────────────────────────────
# WOUND TABLES
# ───────────────────────────────────────────────────────────────────────────

MINOR_WOUND_TABLE: List[Tuple[int, str, str]] = [
    (1,  "Shell Shocked",     "The afflicted has been violently rattled by trauma, their senses overwhelmed and their judgment clouded. They have disadvantage on Wisdom-based checks, saving throws, and attack rolls."),
    (2,  "Concussed",         "A heavy blow to the head leaves the afflicted dazed and struggling to think clearly. They have disadvantage on Intelligence-based checks, saving throws, and attack rolls."),
    (3,  "Ringing Blow",      "A sharp strike to the head leaves the afflicted's ears ringing and their hearing distorted. They are temporarily Deafened."),
    (4,  "Hobbled",           "The afflicted's leg is injured, forcing them to limp and shift their weight painfully. Their speed is reduced by 10 feet."),
    (5,  "Blood Loss",        "The afflicted is bleeding internally or externally, their strength steadily draining from the wound. Reduce their maximum hit points by 2d6."),
    (6,  "Infected Injury",   "The afflicted's wound festers with sickness and inflammation, weakening their resilience. They gain the Poisoned condition."),
    (7,  "Broken Bone",       "A fracture splinters beneath the afflicted's skin, making forceful movement agonizing. They have disadvantage on Strength-based checks, saving throws, and attack rolls."),
    (8,  "Internal Injuries", "The blow has caused the afflicted deep internal damage, making every breath and movement painful. They have disadvantage on Constitution-based checks and saving throws."),
    (9,  "Blurred Vision",    "The afflicted's vision swims with pain and disorientation. They are temporarily Blinded."),
    (10, "Minor Scar",        "The wound leaves a visible mark on the afflicted, altering how others perceive them. They have disadvantage on Charisma-based skill checks, except Intimidation, which they make with advantage."),
    (11, "Staggered",         "Pain and imbalance disrupt the afflicted's coordination in the heat of battle. They cannot take Bonus Actions."),
    (12, "Whiplash",          "The afflicted's neck and head snap violently, leaving their senses unfocused. They suffer -5 to Perception checks and Passive Perception."),
    (13, "Nerve Damage",      "Trauma to the afflicted's nervous system dulls their reflexes. They cannot take reactions."),
    (14, "Muscle Spasms",     "The afflicted's muscles twitch and seize unpredictably, disrupting their movements. They have disadvantage on Dexterity-based checks, saving throws, and attack rolls."),
    (15, "Unsteady",          "The afflicted's footing falters and their balance is compromised. They have disadvantage on Initiative rolls."),
    (16, "Chronic Pain",      "Lingering agony from the afflicted's injury saps their energy and focus. They gain one level of exhaustion."),
    (17, "Arm Injury",        "An injury renders one of the afflicted's arms unusable and painfully stiff. The limb is rendered useless."),
    (18, "Shaken",            "The afflicted's confidence falters and their presence weakens. They have disadvantage on Charisma-based checks, saving throws, and attack rolls."),
    (19, "Off Balance",       "The afflicted's posture and stance are thrown off by injury, leaving them exposed. They suffer -1 to AC until a Long Rest."),
    (20, "Seared Synapses",   "The strike fried something inside the afflicted, they smell burning toast. It left their synapses misfiring and pain signals no longer register correctly. They gain resistance to bludgeoning, piercing, and slashing damage from non-magical attacks."),
]

MAJOR_WOUND_TABLE: List[Tuple[int, str, str]] = [
    (1,  "Mortal Wound",            "A catastrophic blow tears through a vital organ, and death closes in fast. The afflicted suffers a mortal wound, such as a slashed jugular or punctured lung, and will quickly perish. Unless they are stabilized by an ally (DC 15 Medicine check) or receive magical healing, they bleed out and die within 3 rounds, automatically failing their death saving throws."),
    (2,  "Lose an Eye",             "A brutal strike destroys one of the afflicted's eyes in a flash of blood and darkness. (Roll a d20, Even = Right, Odd = Left). The afflicted has disadvantage on Wisdom (Perception) checks that rely on sight and on ranged attack rolls. Magic such as Major Restoration can restore the lost eye. If they have no eyes left after sustaining this injury, they are blinded."),
    (3,  "Lose Both Eyes",          "The world goes black as both eyes are ruined beyond saving. The afflicted is blinded. Magic such as Major Restoration can restore one lost eye; if this happens, change the effect to Lose an Eye."),
    (4,  "Lose Fingers",            "A savage attack shears away several fingers. The afflicted loses 1d3 fingers on one hand (Roll a d20, Even = Right, Odd = Left), and they have disadvantage on checks involving items held by that hand. Magic such as Major Restoration can restore the fingers."),
    (5,  "Lose Hand",               "Their hand is severed in a sudden, irreversible stroke. The afflicted loses a hand (Roll a d20, Even = Right, Odd = Left). They can no longer hold anything with two hands and can only hold a single object at a time. Magic such as Major Restoration can restore the hand."),
    (6,  "Lose Arm",                "The limb is violently removed, leaving the afflicted maimed and off-balance. The afflicted loses an arm (Roll a d20, Even = Right, Odd = Left). They can no longer hold anything with two hands, can only hold a single object at a time, and they have disadvantage on Strength checks. Magic such as Major Restoration can restore the arm."),
    (7,  "Lame",                    "A shattered joint or torn tendon leaves one leg permanently weakened. (Roll a d20, Even = Right Leg, Odd = Left Leg). The afflicted's speed is reduced by 10 feet. They must make a DC 15 Dexterity saving throw after using the Dash action or fall prone."),
    (8,  "Lose a Foot",             "A devastating injury removes the afflicted's foot at the ankle. (Roll a d20, Even = Right, Odd = Left). The afflicted's speed is reduced by 15 feet, and they must use a cane or crutch to move unless they have a peg leg or prosthesis. They fall prone after making the Dash action."),
    (9,  "Lose a Leg",              "A catastrophic blow takes the afflicted's leg entirely, forever altering their mobility. (Roll a d20, Even = Right, Odd = Left). The afflicted's speed is halved, and they must use a cane or crutch to move unless they have a peg leg or prosthesis. They fall prone after making the Dash action. They have disadvantage on all Dexterity checks."),
    (10, "Emotional Trauma",        "The horrors the afflicted has endured fracture something deep within their psyche. The afflicted gains one Indefinite Madness."),
    (11, "Major Scar",              "A terrible wound leaves the afflicted permanently disfigured in body and spirit. The wound has left them visibly and psychologically disfigured. It reshapes not only their appearance, but their sense of self. Others see the damage before they see them, and they feel it in every interaction. They have disadvantage on all Charisma rolls."),
    (12, "Deaf",                    "A thunderous impact steals the afflicted's hearing in an instant. They become permanently deaf."),
    (13, "Organ Failure",           "Internal damage festers quietly, weakening the afflicted from within. When they complete a long rest, they must succeed at a DC 15 Constitution saving throw or gain the poisoned condition until they complete a long rest. Magic such as Major Restoration can cure their Organ Failure."),
    (14, "Brain Damage",            "A traumatic head injury scrambles the afflicted's thoughts and dulls their awareness. They have disadvantage on Intelligence, Wisdom, and Charisma checks, as well as Intelligence, Wisdom, and Charisma saving throws. If they fail a DC 15 saving throw against bludgeoning, force, or psychic damage, they are stunned until the end of their next turn."),
    (15, "Systemic Damage",         "Widespread trauma leaves the afflicted's entire body compromised. They have disadvantage on Strength, Dexterity, and Constitution ability checks and Strength, Dexterity, and Constitution saving throws."),
    (16, "Neurotmesis",             "Severe nerve trauma disrupts the signals between mind and body. Whenever the afflicted attempts an action in combat, they must make a DC 15 Constitution saving throw. On a failed save, they lose their bonus action and can't use reactions until the start of their next turn."),
    (17, "Cardiac Injury",          "The afflicted's heart struggles under strain, especially when gripped by fear. If the afflicted fails a saving throw against fear effects or the Fear System, they gain a level of exhaustion."),
    (18, "Intellectual Disability", "A lasting cognitive injury diminishes the afflicted's mental acuity. They lose 2 points from one mental ability. Roll a d6: 1\u20132 Intelligence, 3\u20134 Wisdom, 5\u20136 Charisma."),
    (19, "Physical Disability",     "A physical injury permanently weakens the afflicted's body. They lose 2 points from one physical ability. Roll a d6: 1\u20132 Strength, 3\u20134 Dexterity, 5\u20136 Constitution."),
    (20, "Knocked Loose",           "My head keeps spinnin', I go to sleep and keep grinnin'. If this is just the beginnin', my life is gonna be beautiful, I've sunshine enough to spread \u2014 it's just like the fella said, tell me quick, ain't that a kick in the head! Something struck the afflicted hard enough to send stars shimmering across their vision. And somehow, some of that light stayed behind. Because their brain damage was so severe that it paradoxically came back to become stable, and the part of their mind that once understood hopelessness no longer functions. At the start of each session, they gain 1 Hope."),
]

# ───────────────────────────────────────────────────────────────────────────
# RULES TEXT
# ───────────────────────────────────────────────────────────────────────────

FEAR_RULES_TEXT = (
    "FEAR ENCOUNTER SYSTEM\n"
    "A character begins with 3 fears, manually added to their fear list, "
    "representing tangible fears they may encounter during the game. "
    "All starting fears begin at Low Severity and Low Desensitization.\n\n"
    "─────────────────────\n\n"
    "FEAR SEVERITY:\n"
    "Reflects how overwhelming and intense a fear feels, "
    "growing stronger the more it is avoided.\n\n"
    "─────────────────────\n\n"
    "FEAR DESENSITIZATION:\n"
    "Reflects how familiar and manageable a fear "
    "becomes, gradually weakening its hold the more it is confronted\n\n"
    "─────────────────────\n\n"
    "HOW AN ENCOUNTER WORKS\n\n"
    "1: Start the Encounter\n\n"
    "Select an active fear and press ENCOUNTER.\n\n"
    "When encountering a fear, the Fear Severity effects apply immediately.\n\n"
    "2: Make a Saving throw\n\n"
    "Roll a Wisdom saving throw: d20 + WIS modifier vs DC.\n"
    "The DC defaults to the fear's current Desensitization DC, "
    "but can be adjusted manually.\n\n"
    "3: Check the Saving throw result\n\n"
    "PASS – The encounter ends. No sanity change.\n"
    "FAIL – Roll Xd4 sanity dice (X = severity level), then choose Confront or Avoid.\n\n"
    "4: Choose your response\n\n"
    "CONFRONT- The character must describe how they confront the fear "
    "directly (e.g., forcing themselves through a tight space if they "
    "are claustrophobic).\n"
    "- Lose the rolled sanity.\n"
    "- Desensitization rung +1. The DC decreases next encounter, "
    "making the fear easier to face.\n\n"
    "AVOID - The character must describe how they avoid or withdraw "
    "from the fear (e.g., refusing to enter a tight space).\n"
    "- Regain the rolled sanity.\n"
    "- Fear Severity +1. The fear grows stronger.\n"
    "- Desensitization rung -1. The DC increases next encounter.\n\n"
    "─────────────────────\n\n"
    "GAINING FEARS\n"
    "Choosing AVOID at [color=#c44040]Extreme Severity[/color] causes the character to gain "
    "one new random fear, automatically added to the fear list.\n\n"
    "─────────────────────\n\n"
    "CURING FEARS\n"
    "Encountering a fear and Choosing to CONFRONT it at [color=#5ad0f8]Extreme "
    "Desensitization[/color] removes the fear\n\n"
    "─────────────────────\n\n"
    "EXHAUSTION\n"
    "Exhaustion is tracked separately and accumulates from multiple "
    "sources: Extreme Severity fear encounters (+1 at encounter start), "
    "Wound check failures by 5 or more (+1), and certain madness effects. "
    "All levels are cumulative—each adds to the ones before it.\n\n"
    "Hover over each pip on the exhaustion tracker to see the effect for that level. "
    "Click a pip to set exhaustion manually.\n"
    "Reduce exhaustion through long rests or restorative magic."
)

MADNESS_RULES_TEXT = (
    "SANITY & INSANITY SYSTEM\n"
    "───────────────────────\n\n"
    "SANITY POOL\n"
    "Your maximum Sanity equals 15 + your Wisdom score. It represents "
    "your character's mental fortitude.\n"
    "As Sanity is lost through fear encounters and other events, your "
    "character gradually descends into insanity.\n\n"
    "SANITY THRESHOLDS\n"
    "As your Sanity falls and crosses percentage thresholds of your "
    "maximum Sanity, your character gains Insanity effects.\n"
    "Each threshold triggers only once per descent; you are not affected "
    "again unless your Sanity rises above that threshold and then drops "
    "below it again.\n"
    "- Above 75% > Stable\n"
    "- Below 75% > Short-Term Insanity\n"
    "- Below 50% > Long-Term Insanity\n"
    "- Below 25% > Indefinite Insanity\n"
    "- At 0 > Total Insanity (the DM takes full control of the character)\n\n"
    "INSANITY DURATIONS\n"
    "- Short-Term Insanity: 1d10 minutes\n"
    "- Long-Term Insanity: 1d10 x 10 hours\n"
    "- Indefinite Insanity: Permanent until cured\n"
    "- Total Insanity: Permanent\n\n"
    "SANITY RECOVERY\n"
    "Sanity can be regained through Avoid choices in fear encounters, "
    "rest, spells, or other in-world effects.\n"
    "Short-Term Insanity can be cured by rising above 75% or through "
    "Minor Restoration (See Spell Tab)\n"
    "Long-Term Insanity can be cured by rising above 50% or through "
    "Minor Restoration (See Spell Tab)\n"
    "Indefinite Insanity must be cured through Major Restoration "
    "(See Spell Tab)\n"
    "Total Insanity cannot be cured\n\n"
    "EXHAUSTION\n"
    "Exhaustion is tracked separately and accumulates from multiple "
    "sources: Extreme Severity fear encounters (+1), Wound check failures "
    "by 5 or more (+1), and certain madness effects. All levels are "
    "cumulative - each adds to the ones before it.\n\n"
    "Hover over each pip on the exhaustion tracker to see the effect\n"
    "for that level. Click a pip to set exhaustion manually.\n"
    "Reduce exhaustion through long rests or restorative magic."
)

WOUND_RULES_TEXT = (
    "LINGERING WOUNDS SYSTEM\n\n"
    "TRIGGER: When a creature drops to 0 HP or "
    "suffers a critical hit, it must make a CON save.\n\n"
    "DC = 10 (or half damage taken, whichever higher)\n\n"
    "OUTCOMES:\n"
    "- Pass by 5+  > No wound\n"
    "- Pass        > Minor Wound (d20 table)\n"
    "- Fail        > Major Wound (d20 table)\n"
    "- Fail by 5+  > Major Wound + 1 Exhaustion\n\n"
    "HEALING:\n"
    "- Minor > Minor Restoration or Long Rest\n"
    "- Major > Major Restoration\n"
    "  Major Restoration also regenerates\n"
    "  lost body parts when removing\n"
    "  a qualifying Major Wound."
)

SPELL_RULES_TEXT = (
    "MINOR RESTORATION:\n"
    "2nd-level Abjuration\n"
    "Casting Time: 10 minutes\n"
    "Range: Touch\n"
    "Components: V, S\n"
    "Duration: Instantaneous\n"
    "Classes: Artificer, Bard, Cleric, Druid, Paladin, Ranger\n\n"
    "You touch a creature and mend lesser afflictions of body or mind.\n"
    "Choose one:\n"
    "• End one Minor Wound affecting the target.\n"
    "• End one instance of Long-Term Madness or Short-Term Madness affecting the target.\n\n"
    "This spell has no effect on Major Wounds or Indefinite Madness.\n\n"
    "─────────────────────\n\n"
    "MAJOR RESTORATION:\n"
    "4th-level Abjuration\n"
    "Casting Time: 1 Hour\n"
    "Range: Touch\n"
    "Components: V, S, M (nonmagical item ≥100 gp, destroyed)\n"
    "Duration: Instantaneous\n"
    "Classes: Artificer, Bard, Cleric, Druid, Paladin, Ranger\n\n"
    "You present an object of personal or material value, offering it as sacrifice. "
    "The item crumbles to ash as restorative magic flows into the creature you touch.\n"
    "Choose one:\n"
    "• End one Minor Or Major Wound affecting the target, regenerating any lost body parts.\n"
    "• End one instance of Short-Term Madness, Long-Term Madness or Indefinite Madness "
    "affecting the target.\n\n"
    "After the spell is cast, the target must make a DC 15 Constitution saving throw.\n"
    "• Success: The restoration succeeds.\n"
    "• Failure: The restoration succeeds, but the target gains 1 level of exhaustion "
    "and cannot benefit from this spell again until they complete a Long Rest."
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
    MadnessStage.SHORT_TERM: MadnessInfo("SHORT-TERM INSANITY", "Roll on Short-Term table.\n1d10 minutes.",        "#c8a44e","#9e7a28","#d4b04a"),
    MadnessStage.LONG_TERM:  MadnessInfo("LONG-TERM INSANITY",  "Roll on Long-Term table.\n1d10 x 10 hours.",     "#c07838","#9a5e28","#c88a48"),
    MadnessStage.INDEFINITE: MadnessInfo("INDEFINITE INSANITY", "Roll on Indefinite table.\nLasts until cured.",  "#8c3838","#7a2828","#a84848"),
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
        "AVOID at Extreme Severity > auto-adds 1 new random fear.",
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
    hope_img_path: str = ""

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
                "hope":self.hope,"hope_img":self.hope_img_path}

    def restore(self, s):
        self.wis_score=s["wis"]; self.con_score=s.get("con",10)
        self.max_sanity=s["max"]; self.current_sanity=s["cur"]
        self.exhaustion=s.get("exh",0)
        self.fired_thresholds=set(s["fired"])
        self.wounds=[WoundEntry.from_dict(w) for w in s.get("wounds",[])]
        self.madnesses=[MadnessEntry.from_dict(m) for m in s.get("madnesses",[])]
        self.hope=s.get("hope",False)
        self.hope_img_path=s.get("hope_img","")
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
                "hope_img": getattr(st, "hope_img_path", ""),
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
