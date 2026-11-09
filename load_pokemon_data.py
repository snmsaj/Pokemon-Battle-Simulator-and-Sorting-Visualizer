"""
load_pokemon_data.py
CSC-300, Fall 2026 - Shawn Saj
Project: Pokemon Battle Simulator and Sorting Visualizer

Step 1 of the project: load, clean, and filter the data.

What this script does:
  1.Downloads data for the original 151 Pokemon, their moves, and all 18
    types from PokeAPI (https://pokeapi.co). Every response is
    cached in data/raw/, so the API is only contacted once. Later runs
    read from the cache and work offline.
    ...
         type_chart.csv  - 18 x 18 damage multiplier matrix (attacker x defender)
  2. Filters the raw data down to only what the battle simulator needs.
  3. Validates the result and saves three clean CSV files in data/clean/:
       pokemon.csv - one row per Pokemon (types, base stats, default battle moves, and every damaging move it can learn)
       moves.csv - damaging moves only (type, category, power, accuracy, PP)
       type_chart.csv - 18 x 18 damage multiplier matrix (attacker x defender)
  4. Runs a few example filters to show the clean data is usable.

Usage:
    pip install pandas
    python3 load_pokemon_data.py              # data only
    python3 load_pokemon_data.py --sprites    # also download sprite images
"""

import argparse
import json
import time
import urllib.request
from pathlib import Path

import pandas as pd

# ---------------------------------------------------------------------------
# Settings
# ---------------------------------------------------------------------------
API_URL = "https://pokeapi.co/api/v2"
NUM_POKEMON = 151                 # original Kanto Pokedex
VERSION_GROUP = "red-blue"        # use the move lists from the original games
MAX_MOVES = 4                     # a Pokemon can know at most 4 moves in battle
REQUEST_DELAY = 0.2               # seconds between API calls (PokeAPI fair use)

# All 18 current types. Only the first 151 Pokemon are used, but they keep
# their modern typing (e.g. Clefairy is Fairy, Magnemite is Electric/Steel).
ALL_TYPES = [
    "normal", "fire", "water", "electric", "grass", "ice", "fighting",
    "poison", "ground", "flying", "psychic", "bug", "rock", "ghost", "dragon",
    "dark", "steel", "fairy",
]

STAT_COLUMNS = ["hp", "attack", "defense", "sp_attack", "sp_defense", "speed"]
API_STAT_NAMES = {
    "hp": "hp", "attack": "attack", "defense": "defense",
    "special-attack": "sp_attack", "special-defense": "sp_defense", "speed": "speed",
}

# API names that don't turn into nice display names with .title()
DISPLAY_NAMES = {
    "nidoran-f": "Nidoran (F)",
    "nidoran-m": "Nidoran (M)",
    "mr-mime": "Mr. Mime",
    "farfetchd": "Farfetch'd",
}


DATA_DIR = Path(__file__).resolve().parent / "data"
RAW_DIR = DATA_DIR / "raw"
CLEAN_DIR = DATA_DIR / "clean"
SPRITE_DIR = DATA_DIR / "sprites"


# ---------------------------------------------------------------------------
# Loading (download + cache)
# ---------------------------------------------------------------------------
def fetch_url(url):
    """Download a URL and return the raw bytes."""
    request = urllib.request.Request(url, headers={"User-Agent": "CSC300-student-project"})
    with urllib.request.urlopen(request, timeout=30) as response:
        return response.read()


def fetch_json(endpoint, key):
    """Return the JSON for API_URL/endpoint/key, using a cached copy if one exists."""
    cache_file = RAW_DIR / endpoint / f"{key}.json"
    if cache_file.exists():
        return json.loads(cache_file.read_text(encoding="utf-8"))

    data = json.loads(fetch_url(f"{API_URL}/{endpoint}/{key}").decode("utf-8"))
    cache_file.parent.mkdir(parents=True, exist_ok=True)
    cache_file.write_text(json.dumps(data), encoding="utf-8")
    time.sleep(REQUEST_DELAY)
    return data


# ---------------------------------------------------------------------------
# Filtering / cleaning helpers
# ---------------------------------------------------------------------------
def display_name(api_name):
    return DISPLAY_NAMES.get(api_name, api_name.replace("-", " ").title())


def pokemon_types(raw_pokemon):
    """Return (type1, type2) using the Pokemon's current types."""
    names = [t["type"]["name"] for t in sorted(raw_pokemon["types"], key=lambda t: t["slot"])]
    type1 = names[0]
    type2 = names[1] if len(names) > 1 else ""
    return type1, type2


def level_up_moves(raw_pokemon):
    """Return a sorted list of (level, move_name) learned by level-up in Red/Blue."""
    moves = []
    for entry in raw_pokemon["moves"]:
        for detail in entry["version_group_details"]:
            if (detail["version_group"]["name"] == VERSION_GROUP
                    and detail["move_learn_method"]["name"] == "level-up"):
                moves.append((detail["level_learned_at"], entry["move"]["name"]))
    return sorted(moves)


def clean_pokemon(raw_pokemon):
    """Keep only the fields the simulator needs from one raw Pokemon record."""
    stats = {API_STAT_NAMES[s["stat"]["name"]]: s["base_stat"] for s in raw_pokemon["stats"]}
    type1, type2 = pokemon_types(raw_pokemon)
    row = {
        "id": raw_pokemon["id"],
        "name": raw_pokemon["name"],
        "display_name": display_name(raw_pokemon["name"]),
        "type1": type1,
        "type2": type2,
    }
    row.update({col: stats[col] for col in STAT_COLUMNS})
    row["total"] = sum(stats[col] for col in STAT_COLUMNS)
    row["front_sprite"] = raw_pokemon["sprites"]["front_default"]
    row["back_sprite"] = raw_pokemon["sprites"]["back_default"]
    return row


def clean_move(raw_move):
    """
    Keep only the battle-relevant fields of a move.

    Note: PokeAPI uses the modern physical/special split for damage_class.
    The original games split by type instead, but the modern version is
    simpler and is what the Move class inheritance will be based on.
    """
    english = [n["name"] for n in raw_move["names"] if n["language"]["name"] == "en"]
    return {
        "name": raw_move["name"],
        "display_name": english[0] if english else display_name(raw_move["name"]),
        "type": raw_move["type"]["name"],
        "category": raw_move["damage_class"]["name"],   # physical / special / status
        "power": raw_move["power"],                      # None for status moves
        "accuracy": raw_move["accuracy"] if raw_move["accuracy"] is not None else 100,
        "pp": raw_move["pp"],
        "priority": raw_move["priority"],
    }


def pick_battle_moves(level_moves, damaging_moves):
    """
    Pick up to MAX_MOVES damaging moves, preferring the most recently learned
    ones (highest level), which is how the games choose a wild Pokemon's moves.
    """
    chosen = []
    for _, move_name in reversed(level_moves):
        if move_name in damaging_moves and move_name not in chosen:
            chosen.append(move_name)
        if len(chosen) == MAX_MOVES:
            break
    return chosen

def learnable_damaging_moves(level_moves, damaging_moves):
    """
    Every damaging move the Pokemon learns by level-up, newest first and with
    no repeats. The player picks their 4 battle moves from this list. The
    first MAX_MOVES entries are the same as pick_battle_moves(), so the
    default moveset is just the top of this list.
    """
    names = [name for _, name in reversed(level_moves) if name in damaging_moves]
    return list(dict.fromkeys(names))

def build_type_chart():
    """
    Build an 18 x 18 matrix where chart.loc[attacker, defender] is the damage
    multiplier (2.0 super effective, 0.5 not very effective, 0.0 no effect).
    Uses PokeAPI's current type relations.
    """
    chart = pd.DataFrame(1.0, index=ALL_TYPES, columns=ALL_TYPES)
    for attacker in ALL_TYPES:
        relations = fetch_json("type", attacker)["damage_relations"]
        for key, multiplier in (("double_damage_to", 2.0),
                                ("half_damage_to", 0.5),
                                ("no_damage_to", 0.0)):
            for defender in relations[key]:
                if defender["name"] in ALL_TYPES:
                    chart.loc[attacker, defender["name"]] = multiplier
    chart.index.name = "attacker"
    return chart


# ---------------------------------------------------------------------------
# Main pipeline
# ---------------------------------------------------------------------------
def build_tables():
    # 1. Pokemon
    pokemon_rows = []
    learnsets = {}
    for pokemon_id in range(1, NUM_POKEMON + 1):
        raw = fetch_json("pokemon", pokemon_id)
        pokemon_rows.append(clean_pokemon(raw))
        learnsets[raw["name"]] = level_up_moves(raw)
        print(f"\rLoaded Pokemon {pokemon_id}/{NUM_POKEMON}", end="")
    print()

    # 2. Moves: only fetch moves that some Pokemon actually learns
    unique_moves = sorted({name for moves in learnsets.values() for _, name in moves})
    move_rows = []
    for i, move_name in enumerate(unique_moves, start=1):
        move_rows.append(clean_move(fetch_json("move", move_name)))
        print(f"\rLoaded move {i}/{len(unique_moves)}", end="")
    print()
    all_moves = pd.DataFrame(move_rows)

    # Filter: battles only use moves that deal damage
    moves_df = all_moves[(all_moves["category"] != "status")
                         & all_moves["power"].notna()].copy()
    moves_df["power"] = moves_df["power"].astype(int)
    moves_df = moves_df.reset_index(drop=True)
    print(f"Moves: {len(all_moves)} learnable, kept {len(moves_df)} damaging "
          f"(removed {len(all_moves) - len(moves_df)} status / fixed-damage moves)")

    # 3. Give each Pokemon its default battle moves, plus the full list the player can choose from before a battle
    damaging = set(moves_df["name"])
    for row in pokemon_rows:
        chosen = pick_battle_moves(learnsets[row["name"]], damaging)
        learnable = learnable_damaging_moves(learnsets[row["name"]], damaging)
        row["moves"] = ";".join(chosen)
        row["num_moves"] = len(chosen)
        row["learnable_moves"] = ";".join(learnable)
        row["num_learnable"] = len(learnable)
        row["battle_ready"] = len(chosen) > 0

    pokemon_df = pd.DataFrame(pokemon_rows)

    # 4. Type chart
    type_chart = build_type_chart()
    return pokemon_df, moves_df, type_chart


def validate(pokemon_df, moves_df, type_chart):
    """Basic checks that the cleaned data is complete and correct."""
    assert set(pokemon_df["type1"]) <= set(ALL_TYPES), "unknown primary type found"
    assert set(pokemon_df["type2"]) <= set(ALL_TYPES) | {""}, "unknown secondary type found"
    assert set(moves_df["type"]) <= set(ALL_TYPES), "unknown move type found"
    assert type_chart.shape == (18, 18)
    # Spot checks against well-known matchups
    assert type_chart.loc["water", "fire"] == 2.0
    assert type_chart.loc["fire", "water"] == 0.5
    assert type_chart.loc["normal", "ghost"] == 0.0
    assert type_chart.loc["electric", "ground"] == 0.0
    assert type_chart.loc["dragon", "fairy"] == 0.0
    assert type_chart.loc["psychic", "dark"] == 0.0
    print("Validation passed.")


def save_tables(pokemon_df, moves_df, type_chart):
    CLEAN_DIR.mkdir(parents=True, exist_ok=True)
    pokemon_df.to_csv(CLEAN_DIR / "pokemon.csv", index=False)
    moves_df.to_csv(CLEAN_DIR / "moves.csv", index=False)
    type_chart.to_csv(CLEAN_DIR / "type_chart.csv")
    print(f"Saved clean CSV files to {CLEAN_DIR}")


def download_sprites(pokemon_df):
    """Save front and back sprite PNGs as data/sprites/<id>_front.png, <id>_back.png."""
    SPRITE_DIR.mkdir(parents=True, exist_ok=True)
    for row in pokemon_df.itertuples():
        for side, url in (("front", row.front_sprite), ("back", row.back_sprite)):
            path = SPRITE_DIR / f"{row.id}_{side}.png"
            if path.exists() or not isinstance(url, str):
                continue
            path.write_bytes(fetch_url(url))
            time.sleep(REQUEST_DELAY)
        print(f"\rDownloaded sprites {row.id}/{NUM_POKEMON}", end="")
    print()


def load_clean_data():
    """
    Load the cleaned CSV files. Later parts of the project (classes, hash
    table, battle screen, sorting visualizer) import and call this function.
    """
    pokemon_df = pd.read_csv(CLEAN_DIR / "pokemon.csv").fillna(
        {"type2": "", "moves": "", "learnable_moves": ""})
    moves_df = pd.read_csv(CLEAN_DIR / "moves.csv")
    type_chart = pd.read_csv(CLEAN_DIR / "type_chart.csv", index_col="attacker")
    return pokemon_df, moves_df, type_chart


# ---------------------------------------------------------------------------
# Example filters
# ---------------------------------------------------------------------------
def show_examples(pokemon_df, moves_df):
    print("\n--- Example filters ---")

    is_fire = (pokemon_df["type1"] == "fire") | (pokemon_df["type2"] == "fire")
    print(f"\nFire-type Pokemon ({is_fire.sum()}):")
    print(", ".join(pokemon_df.loc[is_fire, "display_name"]))

    print("\nTop 5 fastest Pokemon (Speed decides turn order):")
    print(pokemon_df.nlargest(5, "speed")[["display_name", "speed"]].to_string(index=False))

    strong = pokemon_df[pokemon_df["total"] >= 500]
    print(f"\nPokemon with base stat total >= 500: {len(strong)}")

    print("\nNumber of Pokemon per type:")
    all_types = pd.concat([pokemon_df["type1"], pokemon_df.loc[pokemon_df["type2"] != "", "type2"]])
    print(all_types.value_counts().to_string())

    not_ready = pokemon_df[~pokemon_df["battle_ready"]]
    print(f"\nPokemon with no damaging level-up moves (left out of battles): {len(not_ready)}")
    if len(not_ready):
        print(", ".join(not_ready["display_name"]))
        has_choice = pokemon_df[pokemon_df["num_learnable"] > MAX_MOVES]
        print(f"\nPokemon with more than {MAX_MOVES} damaging moves to choose from: {len(has_choice)}")

    print("\nStrongest physical and special moves:")
    for category in ("physical", "special"):
        top = moves_df[moves_df["category"] == category].nlargest(3, "power")
        print(f"  {category}: " + ", ".join(f"{m.display_name} ({m.power})" for m in top.itertuples()))


def main():
    parser = argparse.ArgumentParser(description="Load and filter Gen 1 Pokemon data from PokeAPI.")
    parser.add_argument("--sprites", action="store_true", help="also download sprite images")
    args = parser.parse_args()

    pokemon_df, moves_df, type_chart = build_tables()
    validate(pokemon_df, moves_df, type_chart)
    save_tables(pokemon_df, moves_df, type_chart)
    if args.sprites:
        download_sprites(pokemon_df)
    show_examples(pokemon_df, moves_df)


if __name__ == "__main__":
    main()
