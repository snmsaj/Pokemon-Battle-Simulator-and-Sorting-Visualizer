"""
battle_features.py

Features added from classmates' discussion feedback:
  - Move selection (Ardina): the player picks 4 moves from everything their
    Pokemon can learn, instead of always getting the automatic 4.
  - Smarter Hard mode (Ardina): the computer scores each move by expected
    damage (power, stats, type multiplier, and accuracy), not type alone.
  - Battle history (Jaiden): every attack is saved in a list so the player
    can review the battle and see which moves worked best.

The battle loop in step 5 (Speed-based turn queue) calls these functions.
"""

import random

from load_pokemon_data import MAX_MOVES, load_clean_data
from pokemon_classes import load_roster


# ---------------------------------------------------------------------------
# Type effectiveness and attacking
# ---------------------------------------------------------------------------
def effectiveness(move, defender, type_chart):
    """
    Type multiplier for a move against a defender. Dual types multiply
    together, e.g. Fire vs. Grass/Poison = 2.0 x 1.0, Ice vs. Grass/Flying = 4.0.
    """
    multiplier = 1.0
    for defender_type in defender.types:
        multiplier *= type_chart.loc[move.type, defender_type]
    return multiplier


def effectiveness_message(multiplier):
    if multiplier == 0:
        return "It doesn't affect the target..."
    if multiplier > 1:
        return "It's super effective!"
    if multiplier < 1:
        return "It's not very effective..."
    return ""


def attack(attacker, defender, move, type_chart, history=None, turn=0):
    """
    Use a move: spend PP, check accuracy, deal damage, and print what
    happened. If a BattleHistory is passed in, the attack is recorded.
    Returns the HP the defender lost.
    """
    print(f"{attacker.display_name} used {move.display_name}!")
    multiplier = effectiveness(move, defender, type_chart)
    hit = move.use()
    lost = 0
    if not hit:
        print("  But it missed!")
    else:
        damage = int(move.base_damage(attacker, defender) * multiplier)
        lost = defender.take_damage(damage)
        message = effectiveness_message(multiplier)
        if message:
            print(f"  {message}")
        print(f"  {defender.display_name} lost {lost} HP "
              f"({defender.current_hp}/{defender.max_hp} left)")
        if defender.is_fainted():
            print(f"  {defender.display_name} fainted!")

    if history is not None:
        history.record(turn, attacker, defender, move, lost, multiplier, hit)
    return lost


# ---------------------------------------------------------------------------
# Computer opponent
# ---------------------------------------------------------------------------
def pick_move_easy(attacker, defender, type_chart):
    """Easy mode: any move that still has PP."""
    return random.choice(attacker.usable_moves())


def expected_damage(move, attacker, defender, type_chart):
    """
    Average damage a move would do: base damage (power and stats) x type
    multiplier x chance to hit. A super effective but weak move can lose
    to a strong neutral one, and a strong move that often misses scores lower.
    """
    hit_chance = move.accuracy / 100
    return move.base_damage(attacker, defender) * effectiveness(move, defender, type_chart) * hit_chance


def pick_move_hard(attacker, defender, type_chart):
    """Hard mode: the move with the highest expected damage."""
    return max(attacker.usable_moves(),
               key=lambda move: expected_damage(move, attacker, defender, type_chart))


# ---------------------------------------------------------------------------
# Battle history
# ---------------------------------------------------------------------------
class BattleHistory:
    """A list of every attack in the battle, in the order they happened."""

    def __init__(self):
        self.entries = []

    def record(self, turn, attacker, defender, move, damage, multiplier, hit):
        self.entries.append({
            "turn": turn,
            "attacker": attacker.display_name,
            "defender": defender.display_name,
            "move": move.display_name,
            "damage": damage,
            "multiplier": multiplier,
            "hit": hit,
        })

    def last(self, count=4):
        """Most recent entries, for the small history box on the Pygame screen."""
        return self.entries[-count:]

    def damage_by_move(self):
        """Total damage per (attacker, move), e.g. {("Charmander", "Ember"): 54}."""
        totals = {}
        for entry in self.entries:
            key = (entry["attacker"], entry["move"])
            totals[key] = totals.get(key, 0) + entry["damage"]
        return totals

    def print_log(self):
        print("\n--- Battle history ---")
        for entry in self.entries:
            if entry["hit"]:
                result = f"{entry['damage']} damage (x{entry['multiplier']:g})"
            else:
                result = "missed"
            print(f"Turn {entry['turn']:>2}: {entry['attacker']:<12} "
                  f"{entry['move']:<14} -> {result}")

    def print_summary(self):
        print("\n--- Most effective moves ---")
        totals = self.damage_by_move()
        # Python's sorted() for now; can be swapped for the merge sort from step 6
        for (attacker, move), damage in sorted(totals.items(), key=lambda kv: kv[1], reverse=True):
            print(f"  {attacker:<12} {move:<14} {damage} total damage")


# ---------------------------------------------------------------------------
# Move selection (terminal version)
# ---------------------------------------------------------------------------
def choose_moves_menu(pokemon):
    """
    Let the player pick up to 4 battle moves from the Pokemon's learnable
    moves. Pressing Enter keeps the default moveset.
    """
    options = pokemon.learnable_moves
    if len(options) <= MAX_MOVES:
        print(f"{pokemon.display_name} only knows {len(options)} damaging move(s), "
              f"so it keeps all of them.")
        return

    print(f"\nChoose up to {MAX_MOVES} moves for {pokemon.display_name}:")
    for i, move in enumerate(options, start=1):
        print(f"  {i:>2}. {move}")
    current = ", ".join(move.display_name for move in pokemon.moves)
    print(f"Current moves: {current}")

    while True:
        answer = input(f"Enter {MAX_MOVES} numbers separated by spaces "
                       f"(or press Enter to keep current): ").strip()
        if not answer:
            return
        try:
            indexes = [int(part) - 1 for part in answer.replace(",", " ").split()]
            if any(i < 0 or i >= len(options) for i in indexes):
                raise ValueError(f"numbers must be from 1 to {len(options)}")
            pokemon.set_moves(indexes)
        except ValueError as error:
            print(f"  Invalid choice: {error}")
            continue
        print("New moves: " + ", ".join(move.display_name for move in pokemon.moves))
        return


# ---------------------------------------------------------------------------
# Demo
# ---------------------------------------------------------------------------
def main():
    _, _, type_chart = load_clean_data()
    roster = load_roster()
    by_name = {p.name: p for p in roster}   # replaced by the custom hash table in step 4

    player = by_name["charmander"].fresh_copy()
    computer = by_name["bulbasaur"].fresh_copy()

    choose_moves_menu(player)

    print(f"\nHard mode scores for {computer.display_name} vs. {player.display_name}:")
    for move in computer.usable_moves():
        print(f"  {move.display_name:<14} x{effectiveness(move, player, type_chart):g}  "
              f"expected {expected_damage(move, computer, player, type_chart):.1f} HP")
    print(f"Hard mode picks: {pick_move_hard(computer, player, type_chart).display_name}")

    # Simple alternating turns just to show the history; step 5 replaces
    # this with the Speed-based turn queue.
    history = BattleHistory()
    turn = 1
    while not player.is_fainted() and not computer.is_fainted() and turn <= 20:
        if not player.usable_moves() or not computer.usable_moves():
            print("\nOut of PP, so the demo stops here.")
            break
        print(f"\n-- Turn {turn} --")
        attack(player, computer, pick_move_hard(player, computer, type_chart),
               type_chart, history, turn)
        if not computer.is_fainted():
            attack(computer, player, pick_move_hard(computer, player, type_chart),
                   type_chart, history, turn)
        turn += 1

    history.print_log()
    history.print_summary()


if __name__ == "__main__":
    main()
