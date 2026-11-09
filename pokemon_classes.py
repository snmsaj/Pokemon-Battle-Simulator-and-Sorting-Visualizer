"""
pokemon_classes.py
CSC-300, Fall 2026 - Shawn Saj
Project: Pokemon Battle Simulator and Sorting Visualizer

Step 2 of the project: Pokemon and Move classes.

Classes:
  Move          - base class for every damaging move (type, power, accuracy, PP)
  PhysicalMove  - uses the attacker's Attack vs. the defender's Defense
  SpecialMove   - uses the attacker's Sp. Attack vs. the defender's Sp. Defense
  Pokemon       - one battler: types, level 50 stats, current HP, up to 4 battle
                  moves, and every damaging move it can learn (for move selection)

The data comes from the clean CSV files made by load_pokemon_data.py.
"""

import copy
import random
from abc import ABC, abstractmethod

from load_pokemon_data import MAX_MOVES, STAT_COLUMNS, load_clean_data

LEVEL = 50   # every Pokemon battles at level 50 so fights are even


# ---------------------------------------------------------------------------
# Moves
# ---------------------------------------------------------------------------
class Move(ABC):
    """
    Base class for a damaging move. It holds everything moves have in common.
    Each subclass decides which attacker and defender stats the move uses.
    """

    category = None   # "physical" or "special", set by each subclass

    def __init__(self, name, display_name, move_type, power, accuracy, pp, priority=0):
        self.name = name
        self.display_name = display_name
        self.type = move_type
        self.power = power
        self.accuracy = accuracy
        self.max_pp = pp
        self.pp = pp
        self.priority = priority          # e.g. Quick Attack goes first (used in step 5)

    @abstractmethod
    def get_stats(self, attacker, defender):
        """Return (attacking stat, defending stat) for this kind of move."""

    def can_use(self):
        return self.pp > 0

    def use(self):
        """Spend 1 PP. Return True if the move hits, False if it misses."""
        self.pp -= 1
        return random.randint(1, 100) <= self.accuracy

    def base_damage(self, attacker, defender):
        """
        Simplified version of the games' damage formula, before type
        effectiveness. Step 3 multiplies this by the type chart value.
        """
        attack, defense = self.get_stats(attacker, defender)
        damage = ((2 * LEVEL / 5 + 2) * self.power * attack / defense) / 50 + 2
        return max(1, int(damage))

    def restore_pp(self):
        self.pp = self.max_pp

    def __str__(self):
        return (f"{self.display_name} ({self.type}, {self.category}) "
                f"Power {self.power}  Acc {self.accuracy}  PP {self.pp}/{self.max_pp}")


class PhysicalMove(Move):
    """Physical moves like Tackle or Slash: Attack vs. Defense."""

    category = "physical"

    def get_stats(self, attacker, defender):
        return attacker.attack, defender.defense


class SpecialMove(Move):
    """Special moves like Ember or Thunderbolt: Sp. Attack vs. Sp. Defense."""

    category = "special"

    def get_stats(self, attacker, defender):
        return attacker.sp_attack, defender.sp_defense


def create_move(row):
    """Build the right Move subclass from one row of moves.csv."""
    move_class = PhysicalMove if row.category == "physical" else SpecialMove
    return move_class(row.name, row.display_name, row.type, int(row.power),
                      int(row.accuracy), int(row.pp), int(row.priority))


# ---------------------------------------------------------------------------
# Pokemon
# ---------------------------------------------------------------------------
def calc_hp(base):
    """Level-based HP from the games' formula (no IVs or EVs)."""
    return int(2 * base * LEVEL / 100) + LEVEL + 10


def calc_stat(base):
    """Level-based Attack/Defense/etc. from the games' formula (no IVs or EVs)."""
    return int(2 * base * LEVEL / 100) + 5


class Pokemon:
    """One Pokemon in a battle."""

    def __init__(self, pokedex_id, name, display_name, type1, type2, base_stats, moves,
                 front_sprite=None, back_sprite=None, learnable_moves=None):
        self.id = pokedex_id
        self.name = name
        self.display_name = display_name
        self.types = [type1, type2] if type2 else [type1]
        self.base_stats = base_stats
        self.moves = moves # list of Move objects (max 4)
        # every damaging move it can learn; the player picks 4 of these
        self.learnable_moves = learnable_moves if learnable_moves else list(moves)
        self.front_sprite = front_sprite  # sprite URLs, used by the Pygame screen in step 7
        self.back_sprite = back_sprite

        self.max_hp = calc_hp(base_stats["hp"])
        self.attack = calc_stat(base_stats["attack"])
        self.defense = calc_stat(base_stats["defense"])
        self.sp_attack = calc_stat(base_stats["sp_attack"])
        self.sp_defense = calc_stat(base_stats["sp_defense"])
        self.speed = calc_stat(base_stats["speed"])
        self.current_hp = self.max_hp

    def is_fainted(self):
        return self.current_hp == 0

    def take_damage(self, amount):
        """Lower HP (never below 0) and return how much HP was actually lost."""
        lost = min(amount, self.current_hp)
        self.current_hp -= lost
        return lost

    def hp_fraction(self):
        """Current HP as a value from 0 to 1, for drawing the HP bar later."""
        return self.current_hp / self.max_hp

    def usable_moves(self):
        return [move for move in self.moves if move.can_use()]

    def has_type(self, type_name):
        return type_name in self.types

    def set_moves(self, indexes):
        """
        Replace the battle moves with the learnable moves at the given
        positions (e.g. [0, 2, 5, 6]). Each pick is a fresh copy with full PP.
        """
        if not 1 <= len(indexes) <= MAX_MOVES or len(set(indexes)) != len(indexes):
            raise ValueError(f"pick 1 to {MAX_MOVES} different moves")
        self.moves = [copy.deepcopy(self.learnable_moves[i]) for i in indexes]
        for move in self.moves:
            move.restore_pp()

    def reset(self):
        """Restore full HP and PP before a new battle."""
        self.current_hp = self.max_hp
        for move in self.moves:
            move.restore_pp()

    def fresh_copy(self):
        """A separate copy with its own HP and PP (e.g. Pikachu vs. Pikachu)."""
        clone = copy.deepcopy(self)
        clone.reset()
        return clone

    def __str__(self):
        return (f"{self.display_name} [{'/'.join(self.types)}]  "
                f"HP {self.current_hp}/{self.max_hp}  Atk {self.attack}  Def {self.defense}  "
                f"SpA {self.sp_attack}  SpD {self.sp_defense}  Spe {self.speed}")


# ---------------------------------------------------------------------------
# Loading
# ---------------------------------------------------------------------------
def load_roster(battle_ready_only=True):
    """
    Build a Pokemon object for every row of pokemon.csv. Each Pokemon gets
    its own Move objects, so using a move only spends that Pokemon's PP.
    Pokemon with no damaging moves (like Abra or Ditto) are skipped unless
    battle_ready_only is False.
    """
    pokemon_df, moves_df, _ = load_clean_data()
    move_rows = {row.name: row for row in moves_df.itertuples(index=False)}

    roster = []
    for row in pokemon_df.itertuples(index=False):
        if battle_ready_only and not row.battle_ready:
            continue
        moves = [create_move(move_rows[name]) for name in row.moves.split(";") if name]
        # Older CSVs don't have learnable_moves; rerun load_pokemon_data.py to add it
        learnable_names = getattr(row, "learnable_moves", "") or ""
        learnable = [create_move(move_rows[name]) for name in learnable_names.split(";") if name]
        base_stats = {col: int(getattr(row, col)) for col in STAT_COLUMNS}
        roster.append(Pokemon(int(row.id), row.name, row.display_name, row.type1, row.type2,
            base_stats, moves, row.front_sprite, row.back_sprite, learnable))
    return roster


# ---------------------------------------------------------------------------
# Demo
# ---------------------------------------------------------------------------
def main():
    roster = load_roster()
    print(f"Loaded {len(roster)} battle-ready Pokemon")

    by_name = {p.name: p for p in roster}   # replaced by the custom hash table in step 4
    attacker, defender = by_name["charmander"], by_name["bulbasaur"]
    print(f"\n{attacker}\n{defender}")

    print(f"\n{attacker.display_name}'s moves:")
    for move in attacker.moves:
        print(f"  {move}  ->  {type(move).__name__}")

    print(f"\nDamage to {defender.display_name} (before type effectiveness):")
    for move in attacker.moves:
        attack, defense = move.get_stats(attacker, defender)
        print(f"  {move.display_name:<14} uses {attack} vs {defense}  ->  "
              f"{move.base_damage(attacker, defender)} HP")

    move = attacker.moves[0]
    if move.use():
        lost = defender.take_damage(move.base_damage(attacker, defender))
        print(f"\n{attacker.display_name} used {move.display_name}! "
              f"{defender.display_name} lost {lost} HP.")
    else:
        print(f"\n{attacker.display_name} used {move.display_name}, but it missed!")
    print(defender)


if __name__ == "__main__":
    main()
