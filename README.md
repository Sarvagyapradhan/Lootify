# ⚔️ Lootify - Autonomous Clash of Clans AI Farming Suite

An advanced, external computer vision and ADB automation engine designed for high-speed, intelligent farming in **Clash of Clans** on Android emulators (MEmu, LDPlayer, or BlueStacks). Powered by deep learning, real-time OCR, humanized biometric inputs, and Markov decision processes.

---

## 🌟 Key Features

1. **Independent Hero Ability Timers & Modern Equipment Support**:
   - Built to handle the modern **Hero Equipment** system (Active vs. Passive equipment).
   - Configure individual countdown timers per hero (e.g., King at T+15s, Queen Cloak at T+22s, Warden Tome at T+8s, RC Shield at T+12s).
   - Ability triggers run on asynchronous background threads without stalling army deployment.
   - Passive-only heroes (e.g., Vampstache, Frozen Arrow) skip redundant taps.

2. **Saved Army Composition Recipes**:
   - Fully customizable army profiles in `config/army_recipes.yaml`:
     - **Sneaky Goblins Farming**: Surgical perimeter collector sniping + Jump/Invisibility core push + early surrender when loot is collected.
     - **BARCH Collector Raid**: Four-side wave deployment along the red border.
     - **Baby Dragon Air Farming**: Spaced-out single drops to maximize solo enrage damage.
   - Quickly create new army recipes with distinct deployment phases, delays, and spell sequences.

3. **High-Speed Loot OCR & Matchmaking Scanner**:
   - Scans Gold, Elixir, and Dark Elixir values during matchmaking in `<50ms`.
   - Configurable criteria (`OR` / `AND` thresholds, e.g. Gold $\ge 500k$ OR Elixir $\ge 500k$, Dark Elixir $\ge 4000$).
   - Skips bases in sub-second cycles to find abandoned/dead bases.
   - *(Trophy dropping has been disabled/removed in alignment with modern game changes where farming attacks can proceed without trophy constraints).*

4. **Full-Storage Wall Dumping (Resource Sink)**:
   - When Gold or Elixir storages exceed the threshold (e.g., $\ge 90\%$), the bot triggers a wall upgrading cycle.
   - Selects wall segments and dumps excess Gold/Elixir before the next raid.
   - Retains a configurable gold reserve (e.g., 300,000 Gold) so matchmaking search fees are never depleted.

5. **Base Maintenance & Potions Suite**:
   - **Quick Train**: Automatically trains Quick Train Slot 1, 2, or 3 upon returning home.
   - **Training Potions**: Auto-consumes 1-hour 4x training potions for high-speed farming bursts.
   - **Clock Tower**: Visits Builder Base and triggers free speed-ups.
   - **Clan Operations**: Automatic Clan Castle troop request with custom text message every cooldown, plus auto-donation to clanmates.
   - **Obstacle & Gem Box Clearing**: Scans the perimeter and assigns free builders to harvest gems from obstacles.

6. **Anti-Detection & Humanized Inputs**:
   - **Gaussian Click Jitter**: Every tap is offset by a random Gaussian distribution (`radius ± 5px`) so clicks never land on identical coordinates.
   - **Dynamic Delays**: Realistic human tap intervals and swipe gestures.
   - **Session Scheduling**: Configurable session intervals (e.g., 90 min play, 25 min break).

---

## ⚙️ Emulator Configuration

For pixel-perfect coordinate mapping and fast image recognition, configure your emulator:

1. **Resolution**: Set to **Tablet Mode: 1280 x 720 (DPI 160)**.
2. **ADB Debugging**: Enable ADB connection in emulator settings.
   - **LDPlayer**: Settings ➔ Advanced ➔ Resolution: 1280x720 ➔ Other ➔ Enable ADB (Port 5555).
   - **MEmu**: Settings ➔ Display ➔ 1280x720 ➔ Developer Options ➔ USB Debugging (Port 21503).
   - **BlueStacks 5**: Settings ➔ Display ➔ 1280x720 ➔ Advanced ➔ Android Debug Bridge (Port 5555).

---

## 🚀 Quick Start

### 1. Requirements
Ensure Python 3.10+ is installed. Dependencies are listed in `requirements.txt`:
```bash
pip install -r requirements.txt
```

### 2. Configure Settings
Review and customize configurations in the `config/` directory:
- [settings.yaml](file:///e:/Coc%20farming%20bot/config/settings.yaml): Emulator port, loot thresholds, wall dumping %, boost potions, clan text.
- [heroes.yaml](file:///e:/Coc%20farming%20bot/config/heroes.yaml): Hero equipment types, active ability delay seconds, deployment order.
- [army_recipes.yaml](file:///e:/Coc%20farming%20bot/config/army_recipes.yaml): Army recipes and deployment plans.

### 3. Launching the Bot
Run the main controller:
```bash
python main.py
```
You can choose to launch the full automation loop or test individual routines:
```text
  [1] Start Full Automated Farming Loop
  [2] Test Hero Deployment & Ability Delay Timers
  [3] Test Screen Capture & Loot OCR Scanner
  [4] Test Wall Dumping Routine
  [5] Test Base Maintenance (Quick Train & Harvest)
```
