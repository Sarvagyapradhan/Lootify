"""
Comprehensive Clash of Clans Troop & Spell Knowledge Base.
Contains exhaustive metadata for all permanent, seasonal, and super troops, heroes, spells, and siege machines:
- Role & Tactical Category (TANK, WALL_BREAKER, RESOURCE_HUNTER, DPS, SUPPORT, HERO, SPELL)
- Preferred Target (Defenses, Resources, Walls, Any, Heroes)
- Movement Speed, Housing Space, Damage Type (Single, Splash, Chain)
- Tactical Deployment Rules (Tanks first, Wall Breakers next, Goblins on collectors, Spells on core)
"""

# Tactical Roles
ROLE_TANK = "TANK"
ROLE_WALL_BREAKER = "WALL_BREAKER"
ROLE_RESOURCE_HUNTER = "RESOURCE_HUNTER"
ROLE_DPS = "DPS"
ROLE_SUPPORT = "SUPPORT"
ROLE_HERO = "HERO"
ROLE_SPELL = "SPELL"
ROLE_SIEGE = "SIEGE"

TROOP_ENCYCLOPEDIA = {
    # --- Frontline Tanks ---
    "Giant": {
        "role": ROLE_TANK,
        "target": "Defenses",
        "damage_type": "Single",
        "space": 5,
        "priority_order": 1,
        "description": "Heavy frontline shield, draws cannon, mortar, and archer tower fire."
    },
    "Golem": {
        "role": ROLE_TANK,
        "target": "Defenses",
        "damage_type": "Splash on death",
        "space": 30,
        "priority_order": 1,
        "description": "Ultimate damage absorber; splits into Golemites upon destruction."
    },
    "Ice Golem": {
        "role": ROLE_TANK,
        "target": "Defenses",
        "damage_type": "Freeze on death",
        "space": 15,
        "priority_order": 1,
        "description": "Soaks heavy fire and completely freezes adjacent defenses on death."
    },
    "P.E.K.K.A": {
        "role": ROLE_TANK,
        "target": "Any",
        "damage_type": "Heavy Single DPS",
        "space": 25,
        "priority_order": 1,
        "description": "Armored colossus with massive single-hit damage and huge hitpoint pool."
    },
    "Root Rider": {
        "role": ROLE_TANK,
        "target": "Defenses",
        "damage_type": "Wall Crusher",
        "space": 20,
        "priority_order": 1,
        "description": "Smashes directly through walls, creating natural funnel passages."
    },
    "Electro Titan": {
        "role": ROLE_TANK,
        "target": "Any",
        "damage_type": "Aura & Single Target",
        "space": 32,
        "priority_order": 1,
        "description": "Heavy tank emitting constant electrical aura destroying swarms and walls."
    },
    "Lava Hound": {
        "role": ROLE_TANK,
        "target": "Air Defenses",
        "damage_type": "Air Tank / Lava Pups",
        "space": 30,
        "priority_order": 1,
        "description": "Shields flying units by rushing Air Defenses; bursts into Lava Pups."
    },

    # --- Wall Breakers ---
    "Wall Breaker": {
        "role": ROLE_WALL_BREAKER,
        "target": "Walls (40x damage)",
        "damage_type": "Splash",
        "space": 2,
        "priority_order": 2,
        "description": "Carries explosives directly into outer walls to open compartments."
    },
    "Super Wall Breaker": {
        "role": ROLE_WALL_BREAKER,
        "target": "Walls",
        "damage_type": "Guaranteed detonation",
        "space": 8,
        "priority_order": 2,
        "description": "Guaranteed wall breach regardless of defensive traps or death location."
    },

    # --- Resource Harvesters (Farming Specialists) ---
    "Goblin": {
        "role": ROLE_RESOURCE_HUNTER,
        "target": "Resources (2x damage)",
        "damage_type": "Single",
        "space": 1,
        "priority_order": 3,
        "description": "Ultra-fast sprinter targeting Gold Mines, Elixir Collectors, and Storages."
    },
    "Sneaky Goblin": {
        "role": ROLE_RESOURCE_HUNTER,
        "target": "Resources (3x damage)",
        "damage_type": "Invisible 5s",
        "space": 3,
        "priority_order": 3,
        "description": "The king of farming! Completely invisible for 5 seconds; obliterates storages."
    },
    "Baby Dragon": {
        "role": ROLE_RESOURCE_HUNTER,
        "target": "Any (Tantrum alone)",
        "damage_type": "Air Splash",
        "space": 10,
        "priority_order": 3,
        "description": "Enrages with double damage/attack speed when deployed apart from other air units."
    },
    "Miner": {
        "role": ROLE_RESOURCE_HUNTER,
        "target": "Any",
        "damage_type": "Underground Burrow",
        "space": 6,
        "priority_order": 3,
        "description": "Burrows underground beneath walls directly toward targets."
    },

    # --- Backline DPS & Cleaners ---
    "Barbarian": {
        "role": ROLE_DPS,
        "target": "Any",
        "damage_type": "Single Melee",
        "space": 1,
        "priority_order": 4,
        "description": "Basic melee frontline swarm troop."
    },
    "Archer": {
        "role": ROLE_DPS,
        "target": "Any",
        "damage_type": "Ranged Single",
        "space": 1,
        "priority_order": 4,
        "description": "Ranged attacker, can snipe outer perimeter buildings over walls."
    },
    "Wizard": {
        "role": ROLE_DPS,
        "target": "Any",
        "damage_type": "High Area Splash",
        "space": 4,
        "priority_order": 4,
        "description": "Devastating fireball splash; destroys clusters of defense buildings."
    },
    "Dragon": {
        "role": ROLE_DPS,
        "target": "Any",
        "damage_type": "Air Splash",
        "space": 20,
        "priority_order": 4,
        "description": "Heavy flying beast immune to mortars and cannons."
    },
    "Electro Dragon": {
        "role": ROLE_DPS,
        "target": "Any",
        "damage_type": "Chain Lightning",
        "space": 30,
        "priority_order": 4,
        "description": "Chain lightning arcs up to 5 adjacent buildings."
    },
    "Minion": {
        "role": ROLE_DPS,
        "target": "Any",
        "damage_type": "Fast Air Swarm",
        "space": 2,
        "priority_order": 4,
        "description": "Fast flying cleaner, un-targetable by ground-only defenses."
    },
    "Witch": {
        "role": ROLE_DPS,
        "target": "Any",
        "damage_type": "Skeleton Spawner",
        "space": 12,
        "priority_order": 4,
        "description": "Continuously summons waves of skeleton distraction units."
    },
    "Bowler": {
        "role": ROLE_DPS,
        "target": "Any",
        "damage_type": "Bouncing Splash",
        "space": 6,
        "priority_order": 4,
        "description": "Bounces heavy boulders that strike through two buildings in line."
    },
    "Balloon": {
        "role": ROLE_DPS,
        "target": "Defenses",
        "damage_type": "Air Area Splash",
        "space": 5,
        "priority_order": 4,
        "description": "Drops heavy bombs on defensive structures; death damage destroys clustered defenses."
    },
    "Dragon Rider": {
        "role": ROLE_DPS,
        "target": "Defenses",
        "damage_type": "Ranged Air Splash",
        "space": 25,
        "priority_order": 4,
        "description": "Skeletal dragon machine that snipes defenses from above."
    },
    "Hog Rider": {
        "role": ROLE_DPS,
        "target": "Defenses",
        "damage_type": "Jumps Walls",
        "space": 5,
        "priority_order": 4,
        "description": "Leaps directly over walls to smash interior defense structures."
    },
    "Valkyrie": {
        "role": ROLE_DPS,
        "target": "Any",
        "damage_type": "Whirlwind Splash",
        "space": 8,
        "priority_order": 4,
        "description": "Spins two-handed battleaxe hitting all adjacent buildings simultaneously."
    },
    "Headhunter": {
        "role": ROLE_DPS,
        "target": "Heroes",
        "damage_type": "Poison Darts",
        "space": 6,
        "priority_order": 4,
        "description": "Hops walls, throws poison darts that slow and eliminate enemy heroes."
    },
    "Super Miner": {
        "role": ROLE_DPS,
        "target": "Any",
        "damage_type": "Inferno Drill",
        "space": 26,
        "priority_order": 4,
        "description": "Underground miner with ramping single-target inferno damage and death bomb."
    },
    "Healer": {
        "role": ROLE_SUPPORT,
        "target": "Allies",
        "damage_type": "Area Healing",
        "space": 14,
        "priority_order": 4,
        "description": "Sustains heroes and high-HP tanks with continuous flying healing aura."
    },
    "Druid": {
        "role": ROLE_SUPPORT,
        "target": "Allies",
        "damage_type": "Healing & Bear Transformation",
        "space": 16,
        "priority_order": 4,
        "description": "Bounces restorative healing between units; morphs into a fierce tank bear on death."
    },
    "Apprentice Warden": {
        "role": ROLE_SUPPORT,
        "target": "Any",
        "damage_type": "Life Aura",
        "space": 16,
        "priority_order": 4,
        "description": "Carries miniature Life Aura boosting hit points of frontline troops."
    },
    "Yeti": {
        "role": ROLE_TANK,
        "target": "Any",
        "damage_type": "Yetimites on damage",
        "space": 18,
        "priority_order": 1,
        "description": "Spawns defense-seeking Yetimites whenever taking heavy damage."
    },

    # --- Heroes ---
    "Barbarian King": {
        "role": ROLE_HERO,
        "target": "Any",
        "damage_type": "Melee Tank",
        "ability": "Iron Fist / Giant Gauntlet",
        "priority_order": 5,
        "description": "Village monarch; soaks damage and smashes through core compartments."
    },
    "Archer Queen": {
        "role": ROLE_HERO,
        "target": "Any",
        "damage_type": "Extreme Long-Range DPS",
        "ability": "Royal Cloak / Invisibility",
        "priority_order": 5,
        "description": "Deadly precision sniper; royal cloak heals and provides stealth."
    },
    "Grand Warden": {
        "role": ROLE_HERO,
        "target": "Any",
        "damage_type": "Support Life Aura",
        "ability": "Eternal Tome (Invulnerability)",
        "priority_order": 5,
        "description": "Boosts maximum HP of nearby troops; Eternal Tome makes army invulnerable."
    },
    "Royal Champion": {
        "role": ROLE_HERO,
        "target": "Defenses",
        "damage_type": "Jumping Defense Sniper",
        "ability": "Seeking Shield",
        "priority_order": 5,
        "description": "Hops over walls and hurls shield targeting high-tier defenses."
    },
    "Minion Prince": {
        "role": ROLE_HERO,
        "target": "Any",
        "damage_type": "Flying Hero DPS",
        "ability": "Dark Flight",
        "priority_order": 5,
        "description": "Aerial hero providing flying support and rapid splash bursts."
    },

    # --- Super Troops (Max 2 Active in Army Composition) ---
    "Super Barbarian": {
        "role": ROLE_DPS,
        "target": "Any",
        "damage_type": "Raging Melee",
        "space": 5,
        "priority_order": 4,
        "description": "Spawns with 8-second Rage boosting speed and damage on deployment."
    },
    "Super Archer": {
        "role": ROLE_DPS,
        "target": "Any",
        "damage_type": "Piercing Sharp Shot",
        "space": 12,
        "priority_order": 4,
        "description": "Fires giant piercing arrows that strike through multiple consecutive buildings."
    },
    "Super Giant": {
        "role": ROLE_TANK,
        "target": "Defenses",
        "damage_type": "Wall Buster Strike",
        "space": 32,
        "priority_order": 1,
        "description": "Deals massive bonus damage against walls and tanks heavy defensive fire."
    },
    "Rocket Balloon": {
        "role": ROLE_DPS,
        "target": "Defenses",
        "damage_type": "Rocket Speed Air Splash",
        "space": 8,
        "priority_order": 4,
        "description": "Propelled by booster rockets directly into air defenses upon deployment."
    },
    "Super Wizard": {
        "role": ROLE_DPS,
        "target": "Any",
        "damage_type": "Chain Lightning Fireball",
        "space": 10,
        "priority_order": 4,
        "description": "Casts chain-reaction fireballs that arc between multiple clustered structures."
    },
    "Super Dragon": {
        "role": ROLE_DPS,
        "target": "Any",
        "damage_type": "Continuous Flame Blast",
        "space": 40,
        "priority_order": 4,
        "description": "Molten fire drake dealing continuous burst area damage to all targets in path."
    },
    "Inferno Dragon": {
        "role": ROLE_DPS,
        "target": "Any",
        "damage_type": "Ramping Inferno Beam",
        "space": 15,
        "priority_order": 4,
        "description": "Fires a focused inferno beam that ramps up to catastrophic single-target damage."
    },
    "Super Minion": {
        "role": ROLE_DPS,
        "target": "Any",
        "damage_type": "Long-Range Rocket Bursts",
        "space": 12,
        "priority_order": 4,
        "description": "Snipes distant targets with high-damage sniper rockets before closing into melee."
    },
    "Super Valkyrie": {
        "role": ROLE_DPS,
        "target": "Any",
        "damage_type": "Rage Drop on Death",
        "space": 20,
        "priority_order": 4,
        "description": "Whirlwind warrior who drops a full Rage Spell on the ground upon death."
    },
    "Super Witch": {
        "role": ROLE_DPS,
        "target": "Any",
        "damage_type": "Big Boy Spawner",
        "space": 40,
        "priority_order": 4,
        "description": "Summons Big Boy, a colossus giant skeleton who smashes frontline defenses."
    },
    "Ice Hound": {
        "role": ROLE_TANK,
        "target": "Air Defenses",
        "damage_type": "Frost Nova on Death",
        "space": 30,
        "priority_order": 1,
        "description": "Freezes surrounding defenses when damaged; bursts into Ice Pups on death."
    },
    "Super Bowler": {
        "role": ROLE_DPS,
        "target": "Any",
        "damage_type": "Triple Bounce Boulder",
        "space": 30,
        "priority_order": 4,
        "description": "Hurls massive boulders that bounce three times, devastating interior base cores."
    },
    "Super Yeti": {
        "role": ROLE_TANK,
        "target": "Any",
        "damage_type": "Electrified Heavy Tank",
        "space": 30,
        "priority_order": 1,
        "description": "Colossal frost yeti spawning electrified Yetimites targeting heavy defenses."
    },
    "Super Hog Rider": {
        "role": ROLE_DPS,
        "target": "Defenses",
        "damage_type": "Hog & Rider Split",
        "space": 12,
        "priority_order": 4,
        "description": "Leaps walls; on defeat, rider and hog split into two independent combatants."
    },

    # --- Spells ---
    "Rage Spell": {
        "role": ROLE_SPELL,
        "target": "Troops in ring",
        "effect": "+130% Damage, +30 Speed",
        "priority_order": 6,
        "description": "Rages all units inside circle, doubling damage and movement."
    },
    "Healing Spell": {
        "role": ROLE_SPELL,
        "target": "Troops in ring",
        "effect": "Continuous HP Regen",
        "priority_order": 6,
        "description": "Saturates troops with healing rings against wizard towers and mortars."
    },
    "Jump Spell": {
        "role": ROLE_SPELL,
        "target": "Walls",
        "effect": "Wall bypass",
        "priority_order": 6,
        "description": "Enables ground units to leap over walls into core compartments."
    },
    "Freeze Spell": {
        "role": ROLE_SPELL,
        "target": "Heavy Defenses (Eagle/Inferno/TH)",
        "effect": "Stuns defenses for 5s",
        "priority_order": 6,
        "description": "Completely disables target defenses and enemy clan castle troops."
    },
    "Lightning Spell": {
        "role": ROLE_SPELL,
        "target": "Air Defenses / Mortars",
        "effect": "Pinpoint Lightning Bolt",
        "priority_order": 6,
        "description": "Zaps and resets defenses; snipes Air Defenses and Sweepers."
    },
    "Invisibility Spell": {
        "role": ROLE_SPELL,
        "target": "Troops & Buildings",
        "effect": "Stealth cloak",
        "priority_order": 6,
        "description": "Conceals friendly units so defenses cannot target them."
    },
    "Earthquake Spell": {
        "role": ROLE_SPELL,
        "target": "Walls (4x destroys all walls)",
        "effect": "Shatters walls",
        "priority_order": 6,
        "description": "Four earthquake spells instantly shatter any level wall compartment."
    },
    "Clone Spell": {
        "role": ROLE_SPELL,
        "target": "Friendly Units",
        "effect": "Duplicate units",
        "priority_order": 6,
        "description": "Clones units entering the spell circle."
    },
    "Recall Spell": {
        "role": ROLE_SPELL,
        "target": "Friendly Units",
        "effect": "Withdraw & redeploy",
        "priority_order": 6,
        "description": "Teleports deployed units back into the unit tray for redeployment elsewhere."
    },
    "Revive Spell": {
        "role": ROLE_SPELL,
        "target": "Fallen Hero",
        "effect": "Revive Hero",
        "priority_order": 6,
        "description": "Brings a fallen hero back to life on the battlefield."
    },
    "Poison Spell": {
        "role": ROLE_SPELL,
        "target": "Enemy Troops & Heroes",
        "effect": "Slow & Poison Damage",
        "priority_order": 6,
        "description": "Decimates enemy defending clan castle troops and heroes."
    },
    "Haste Spell": {
        "role": ROLE_SPELL,
        "target": "Troops in ring",
        "effect": "Extreme Movement Speed",
        "priority_order": 6,
        "description": "Provides rapid speed boost for balloons and slow tanks."
    },
    "Skeleton Spell": {
        "role": ROLE_SPELL,
        "target": "Core Defenses",
        "effect": "Distraction Swarm",
        "priority_order": 6,
        "description": "Summons distraction skeletons directly inside enemy compartments."
    },
    "Bat Spell": {
        "role": ROLE_SPELL,
        "target": "Defenses",
        "effect": "Flying Bat Swarm",
        "priority_order": 6,
        "description": "Summons a swarm of flying bats that target and overwhelm defenses."
    },
    "Overgrowth Spell": {
        "role": ROLE_SPELL,
        "target": "Buildings & Defenses",
        "effect": "Entangles defenses",
        "priority_order": 6,
        "description": "Freezes defenses and buildings in vines, making troops ignore them."
    },

    # --- Siege Machines ---
    "Wall Wrecker": {
        "role": ROLE_SIEGE,
        "target": "Town Hall",
        "damage_type": "Battering Ram",
        "space": 1,
        "priority_order": 1,
        "description": "Smashes through walls toward the Town Hall, delivering Clan Castle troops."
    },
    "Battle Blimp": {
        "role": ROLE_SIEGE,
        "target": "Town Hall",
        "damage_type": "Air Transport",
        "space": 1,
        "priority_order": 1,
        "description": "Flies directly toward the Town Hall over walls and ground defenses."
    },
    "Stone Slammer": {
        "role": ROLE_SIEGE,
        "target": "Defenses",
        "damage_type": "Area Earthquake",
        "space": 1,
        "priority_order": 1,
        "description": "Heavy flying boulder machine that targets and flattens defenses."
    },
    "Siege Barracks": {
        "role": ROLE_SIEGE,
        "target": "Perimeter Drop",
        "damage_type": "P.E.K.K.A & Wizards",
        "space": 1,
        "priority_order": 1,
        "description": "Deploys a P.E.K.K.A and a stream of Wizards before releasing CC troops."
    },
    "Log Launcher": {
        "role": ROLE_SIEGE,
        "target": "Town Hall",
        "damage_type": "Rolling Logs",
        "space": 1,
        "priority_order": 1,
        "description": "Hurls piercing logs that damage buildings and shatter walls from a distance."
    },
    "Flame Flinger": {
        "role": ROLE_SIEGE,
        "target": "Defenses (Long Range)",
        "damage_type": "Fire Spirits",
        "space": 1,
        "priority_order": 1,
        "description": "Long-range catapult hurling Fire Spirits; outranges most defenses."
    },
    "Battle Drill": {
        "role": ROLE_SIEGE,
        "target": "Defenses",
        "damage_type": "Underground Burrow / Stun",
        "space": 1,
        "priority_order": 1,
        "description": "Burrows underground between defenses, stunning targets upon emergence."
    }
}


def get_troop_metadata(name):
    """Returns metadata dict for any troop, hero, or spell name (case-insensitive fuzzy match)."""
    norm = name.strip().lower()
    # 1. Check exact match first
    for tname, data in TROOP_ENCYCLOPEDIA.items():
        if norm == tname.lower():
            return {"name": tname, **data}

    # 2. Check longest match first (e.g. "Barbarian King" matches before "Barbarian", "Super Archer" before "Archer")
    for tname in sorted(TROOP_ENCYCLOPEDIA.keys(), key=len, reverse=True):
        if tname.lower() in norm or norm in tname.lower():
            return {"name": tname, **TROOP_ENCYCLOPEDIA[tname]}

    # Generic fallback
    if "hero" in norm:
        return {"name": name, "role": ROLE_HERO, "priority_order": 5, "description": "Hero Unit"}
    if "spell" in norm:
        return {"name": name, "role": ROLE_SPELL, "priority_order": 6, "description": "Spell"}
    return {"name": name, "role": ROLE_DPS, "priority_order": 4, "description": "Combat Unit"}


def get_deployment_order(card_list):
    """
    Sorts detected army cards into the ideal tactical Clash of Clans deployment sequence:
    1. Tanks (soak fire)
    2. Wall Breakers (breach perimeter)
    3. Resource Harvesters (loot collectors)
    4. Backline DPS (destroy base)
    5. Heroes (lead core assault)
    6. Spells (support core push)
    """
    def _order_key(card):
        meta = get_troop_metadata(card.get("name", ""))
        return meta.get("priority_order", 4)

    return sorted(card_list, key=_order_key)
