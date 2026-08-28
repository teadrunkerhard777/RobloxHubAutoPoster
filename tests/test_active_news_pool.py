import ast
import json
import unittest
from pathlib import Path

from external_news_facts import (
    MAX_ARTICLE_AGE_DAYS,
    SECONDARY_NEWS_MAX_AGE_DAYS,
)

PROJECT_ROOT = Path(__file__).parents[1]
ACTIVE_GAMES = [
    "Steal An Egg",
    "Animal Hospital (Anomaly)",
    "+1 Speed Keyboard Escape",
    "Murder Mystery 2",
    "Brookhaven RP",
    "Blox Fruits",
    "Adopt Me!",
    "RIVALS",
    "99 Nights in the Forest",
    "Steal a Brainrot",
]
LEGACY_GAMES = [
    "Grow a Garden",
    "Dress To Impress",
    "Pet Simulator 99",
    "Blade Ball",
]
NEW_GAME_IDS = {
    "Steal An Egg": (10563114921, 107778070777162, 825735094),
    "Animal Hospital (Anomaly)": (10148749921, 78515283254292, 344908697),
    "+1 Speed Keyboard Escape": (9831440772, 81245647985532, 175742687),
    "Murder Mystery 2": (66654135, 142823291, None),
}


def load_json(name):
    return json.loads((PROJECT_ROOT / name).read_text(encoding="utf-8"))


def load_selector():
    path = PROJECT_ROOT / "format_news_ru.py"
    tree = ast.parse(path.read_text(encoding="utf-8"))
    node = next(
        item
        for item in tree.body
        if isinstance(item, ast.FunctionDef) and item.name == "select_news_items"
    )
    namespace = {"MAX_NEWS_ITEMS": 3}
    exec(  # noqa: S102
        compile(ast.Module(body=[node], type_ignores=[]), str(path), "exec"), namespace
    )
    return namespace["select_news_items"]


class ActiveNewsPoolTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.games = load_json("games.json")
        cls.sources = load_json("official_sources.json")
        cls.select_news_items = staticmethod(load_selector())

    def test_active_pool_contains_exactly_ten_current_games(self):
        active = [game["name"] for game in self.games if game["pool"] == "active"]
        self.assertEqual(active, ACTIVE_GAMES)

    def test_all_active_games_participate_in_primary_discovery(self):
        self.assertEqual([game["name"] for game in self.games[:10]], ACTIVE_GAMES)
        self.assertTrue(all(game["pool"] == "active" for game in self.games[:10]))

    def test_legacy_pool_is_preserved_without_priority(self):
        legacy = [game["name"] for game in self.games if game["pool"] == "legacy"]
        self.assertEqual(legacy, LEGACY_GAMES)
        self.assertTrue(all("priority" not in game for game in self.games))

    def test_new_games_have_confirmed_ids(self):
        for name, expected in NEW_GAME_IDS.items():
            source = self.sources[name]
            self.assertEqual(
                (
                    source["universe_id"],
                    source["root_place_id"],
                    source["roblox_group_id"],
                ),
                expected,
            )

    def test_mm2_uses_confirmed_creator_instead_of_invented_group(self):
        source = self.sources["Murder Mystery 2"]
        self.assertIsNone(source["roblox_group_id"])
        self.assertEqual(source["roblox_creator_name"], "Nikilis")
        self.assertEqual(source["roblox_creator_id"], 1848960)

    def test_registry_pool_matches_central_game_registry(self):
        for game in self.games:
            self.assertEqual(self.sources[game["name"]]["pool"], game["pool"])

    def test_active_candidate_is_selected_before_stronger_legacy(self):
        formatted = [
            ({"pool": "legacy"}, {"game": "Blade Ball", "score": 10}, False),
            ({"pool": "active"}, {"game": "RIVALS", "score": 5}, False),
        ]
        selected = self.select_news_items(formatted, max_items=2)
        self.assertEqual([item["game"] for item in selected], ["RIVALS", "Blade Ball"])

    def test_legacy_candidate_is_used_when_active_pool_is_empty(self):
        formatted = [({"pool": "legacy"}, {"game": "Blade Ball", "score": 8}, False)]
        self.assertEqual(self.select_news_items(formatted)[0]["game"], "Blade Ball")

    def test_existing_freshness_strategy_is_unchanged(self):
        self.assertEqual(MAX_ARTICLE_AGE_DAYS, 14)
        self.assertEqual(SECONDARY_NEWS_MAX_AGE_DAYS, 30)


if __name__ == "__main__":
    unittest.main()
