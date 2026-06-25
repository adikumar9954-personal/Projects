"""Known meta archetypes and their card compositions.

Source: ptcg-kaggle-meta.vercel.app (2026-06-24)
"""

DRAGAPULT_EX = {
    "name": "Dragapult ex / Dreepy",
    "win_rate": 0.596,
    "meta_share": 0.067,
    "decklists": 740,
    "core_cards": {
        2: {"name": "Basic {R} Energy", "avg": 4.06, "usage": 1.00},
        5: {"name": "Basic {P} Energy", "avg": 4.02, "usage": 1.00},
        119: {"name": "Dreepy", "avg": 4.00, "usage": 1.00},
        120: {"name": "Drakloak", "avg": 4.00, "usage": 1.00},
        1086: {"name": "Buddy-Buddy Poffin", "avg": 4.00, "usage": 1.00},
        1227: {"name": "Lillie's Determination", "avg": 4.00, "usage": 1.00},
        1121: {"name": "Ultra Ball", "avg": 3.98, "usage": 1.00},
        1198: {"name": "Crispin", "avg": 3.88, "usage": 1.00},
        1152: {"name": "Poke Pad", "avg": 3.20, "usage": 1.00},
        121: {"name": "Dragapult ex", "avg": 3.03, "usage": 1.00},
        1182: {"name": "Boss's Orders", "avg": 3.03, "usage": 1.00},
        1097: {"name": "Night Stretcher", "avg": 2.00, "usage": 1.00},
        235: {"name": "Budew", "avg": 1.99, "usage": 1.00},
        140: {"name": "Fezandipiti ex", "avg": 1.00, "usage": 1.00},
        1080: {"name": "Unfair Stamp", "avg": 0.98, "usage": 0.978},
        1079: {"name": "Rare Candy", "avg": 2.08, "usage": 0.973},
        184: {"name": "Latias ex", "avg": 0.97, "usage": 0.972},
        1210: {"name": "Brock's Scouting", "avg": 1.94, "usage": 0.964},
        1071: {"name": "Meowth ex", "avg": 0.98, "usage": 0.943},
        1120: {"name": "Crushing Hammer", "avg": 3.50, "usage": 0.932},
        1256: {"name": "Team Rocket's Watchtower", "avg": 1.74, "usage": 0.927},
        1156: {"name": "Lucky Helmet", "avg": 0.81, "usage": 0.814},
    },
    "fringe_cards": {
        1123: {"name": "Switch", "avg": 0.06, "usage": 0.058},
        318: {"name": "Ho-Oh", "avg": 0.06, "usage": 0.055},
        1260: {"name": "Risky Ruins", "avg": 0.08, "usage": 0.049},
        305: {"name": "Dunsparce", "avg": 0.08, "usage": 0.042},
        306: {"name": "Dudunsparce ex", "avg": 0.04, "usage": 0.042},
        66: {"name": "Dudunsparce", "avg": 0.04, "usage": 0.042},
        1246: {"name": "Jamming Tower", "avg": 0.08, "usage": 0.038},
        272: {"name": "Lillie's Clefairy ex", "avg": 0.04, "usage": 0.036},
        112: {"name": "Munkidori", "avg": 0.07, "usage": 0.035},
        7: {"name": "Basic {D} Energy", "avg": 0.07, "usage": 0.035},
        31: {"name": "Chi-Yu", "avg": 0.03, "usage": 0.030},
        1159: {"name": "Hero's Cape", "avg": 0.02, "usage": 0.022},
        1197: {"name": "Xerosic's Machinations", "avg": 0.02, "usage": 0.019},
        1240: {"name": "Rosa's Encouragement", "avg": 0.02, "usage": 0.018},
        1231: {"name": "Dawn", "avg": 0.02, "usage": 0.015},
        131: {"name": "Duskull", "avg": 0.02, "usage": 0.011},
        133: {"name": "Dusknoir", "avg": 0.01, "usage": 0.011},
        132: {"name": "Dusclops", "avg": 0.01, "usage": 0.011},
        1219: {"name": "Team Rocket's Petrel", "avg": 0.01, "usage": 0.007},
        1187: {"name": "Morty's Conviction", "avg": 0.01, "usage": 0.007},
        1124: {"name": "Pokemon Catcher", "avg": 0.01, "usage": 0.003},
        1213: {"name": "Judge", "avg": 0.01, "usage": 0.003},
        490: {"name": "Victini", "avg": 0.00, "usage": 0.001},
    },
}

META_ARCHETYPES = {
    "dragapult_ex": DRAGAPULT_EX,
}

ARCHETYPE_SIGNATURES = {
    "dragapult_ex": {119, 120, 121},
    "mega_lucario": set(),
    "hops_trevenant": set(),
    "alakazam": set(),
    "team_rocket_petrel": set(),
    "mega_starmie": set(),
    "nighttime_mine": set(),
    "ionos_bellibolt": set(),
    "genesect": set(),
    "gravity_mountain": set(),
}
