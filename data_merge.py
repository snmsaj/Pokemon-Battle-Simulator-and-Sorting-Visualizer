"""
data_merge.py
CSC-300, Fall 2026 - Shawn Saj
Project: Pokemon Battle Simulator and Sorting Visualizer

Merges the three clean data sources (pokemon.csv, moves.csv, type_chart.csv)
into one dataframe: one row per Pokemon + battle move.
"""

from load_pokemon_data import CLEAN_DIR, load_clean_data


def main():
    df_pokemon_all, df_moves_all, type_chart = load_clean_data()

    # Filter: only Pokemon that can battle, one row per default battle move
    df_pokemon_of_interest = df_pokemon_all[df_pokemon_all["battle_ready"]].copy()
    df_pokemon_of_interest["move"] = df_pokemon_of_interest["moves"].str.split(";")
    df_pokemon_moves = df_pokemon_of_interest.explode("move")

    # Merge 1: Pokemon + move stats (moves.csv)
    df_merged = df_pokemon_moves.merge(
        df_moves_all.add_prefix("move_"),
        left_on="move", right_on="move_name", how="left")

    # Same-type attack bonus: move type matches one of the Pokemon's types
    df_merged["same_type"] = ((df_merged["move_type"] == df_merged["type1"])
                              | (df_merged["move_type"] == df_merged["type2"]))

    # Merge 2: how many types each move type is super effective against (type_chart.csv)
    df_type_strength = ((type_chart > 1).sum(axis=1)
                        .rename("super_effective_vs").reset_index())
    df_merged = df_merged.merge(df_type_strength, left_on="move_type",
                                right_on="attacker", how="left").drop(columns="attacker")

    df_merged = df_merged[["id", "display_name", "type1", "type2", "move_display_name",
                           "move_type", "move_category", "move_power", "move_accuracy",
                           "same_type", "super_effective_vs"]]

    assert df_merged["move_power"].notna().all(), "a battle move is missing from moves.csv"
    print(f"Merged dataframe: {df_merged.shape[0]} rows x {df_merged.shape[1]} columns")
    print(df_merged.head(8).to_string(index=False))

    df_merged.to_csv(CLEAN_DIR / "pokemon_moves_merged.csv", index=False)
    print(f"Saved {CLEAN_DIR / 'pokemon_moves_merged.csv'}")


if __name__ == "__main__":
    main()
