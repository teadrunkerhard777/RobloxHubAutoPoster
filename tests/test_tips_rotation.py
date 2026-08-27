import random
import unittest

from tips_rotation import (
    ALLOWED_TIP_CATEGORIES,
    PRIORITY_TIP_GAMES,
    build_tips_post,
    choose_tips,
    validate_tip_catalog,
)

GAMES = [
    "Steal a Brainrot",
    "99 Nights in the Forest",
    "Blox Fruits",
    "Brookhaven",
    "Adopt Me!",
    "RIVALS",
    "Grow a Garden",
    "Dress To Impress",
    "Pet Simulator 99",
    "Blade Ball",
]


def make_tips(used=False):
    tips = []
    tip_id = 1

    for game in GAMES:
        for category in ("strategy", "mechanics", "items"):
            tips.append(
                {
                    "id": tip_id,
                    "game": game,
                    "text": f"Совет {tip_id}",
                    "category": category,
                    "used": used,
                }
            )
            tip_id += 1

    return tips


class TipsRotationTests(unittest.TestCase):
    def test_selects_exactly_five_tips_from_different_games(self):
        selected = choose_tips(make_tips(), count=5, rng=random.Random(4))

        self.assertEqual(len(selected), 5)
        self.assertEqual(len({tip["game"] for tip in selected}), 5)
        self.assertEqual(len({tip["id"] for tip in selected}), 5)

    def test_does_not_repeat_used_id_before_game_pool_is_exhausted(self):
        tips = make_tips()
        first = choose_tips(tips, 5, rng=random.Random(2))
        second = choose_tips(tips, 5, rng=random.Random(2))

        self.assertTrue(
            {tip["id"] for tip in first}.isdisjoint({tip["id"] for tip in second})
        )

    def test_avoids_recent_games_when_five_fresh_games_exist(self):
        recent_games = GAMES[:5]
        selected = choose_tips(
            make_tips(), 5, recent_games=recent_games, rng=random.Random(5)
        )

        self.assertTrue({tip["game"] for tip in selected}.isdisjoint(recent_games))

    def test_categories_are_valid_and_avoid_last_game_category(self):
        tips = make_tips()
        history = {game: ["strategy"] for game in GAMES}
        selected = choose_tips(tips, 5, category_history=history, rng=random.Random(7))

        self.assertTrue(
            all(tip["category"] in ALLOWED_TIP_CATEGORIES for tip in selected)
        )
        self.assertTrue(all(tip["category"] != "strategy" for tip in selected))

    def test_priority_is_strong_but_not_mandatory(self):
        releases_with_priority = 0
        releases_without_priority = 0

        for seed in range(100):
            selected = choose_tips(make_tips(), 5, rng=random.Random(seed))
            games = {tip["game"] for tip in selected}

            if games & PRIORITY_TIP_GAMES:
                releases_with_priority += 1
            else:
                releases_without_priority += 1

        self.assertGreaterEqual(releases_with_priority, 80)
        self.assertGreater(releases_without_priority, 0)

    def test_resets_only_after_game_tips_are_exhausted(self):
        tips = make_tips(used=True)
        selected = choose_tips(tips, 5, rng=random.Random(3))
        selected_games = {tip["game"] for tip in selected}

        for game in selected_games:
            game_tips = [tip for tip in tips if tip["game"] == game]
            self.assertEqual(sum(bool(tip["used"]) for tip in game_tips), 1)

    def test_builds_five_game_blocks_with_category_emojis(self):
        selected = choose_tips(make_tips(), 5, rng=random.Random(9))
        games, text = build_tips_post(selected, {game: "🎮" for game in GAMES})

        self.assertEqual(games.count(" + "), 4)
        for tip in selected:
            self.assertIn(f"🎮 {tip['game']}\n", text)
        self.assertIn("🎯 ", text)
        self.assertTrue(text.endswith("🎮 Roblox Hub"))

    def test_project_catalog_has_fifteen_valid_tips_per_game(self):
        import json

        with open("tips.json", "r", encoding="utf-8") as file:
            tips = json.load(file)

        self.assertEqual(
            validate_tip_catalog(tips, set(GAMES), minimum_per_game=15), []
        )


if __name__ == "__main__":
    unittest.main()
