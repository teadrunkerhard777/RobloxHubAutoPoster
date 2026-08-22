import json
import os
import runpy
import tempfile
import unittest

from pathlib import Path
from unittest.mock import Mock, patch


PROJECT_DIR = Path(__file__).resolve().parents[1]


class GenerateNewsDescriptionTests(unittest.TestCase):
    def run_generator(self, old_description, new_description):
        universe_id = 1686885941
        games = [
            {
                "name": "Brookhaven",
                "universe_id": universe_id,
                "priority": False,
            }
        ]
        snapshots = {
            str(universe_id): {
                "game": "Brookhaven",
                "description": old_description,
            }
        }
        response = Mock()
        response.raise_for_status.return_value = None
        response.json.return_value = {
            "data": [
                {
                    "id": universe_id,
                    "name": "Brookhaven RP",
                    "description": new_description,
                    "updated": "2026-08-20T12:00:00Z",
                    "created": "2020-01-01T00:00:00Z",
                    "creator": {"name": "Brookhaven by Voldex"},
                }
            ]
        }

        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            (temp_path / "games.json").write_text(
                json.dumps(games),
                encoding="utf-8",
            )
            (temp_path / "game_snapshots.json").write_text(
                json.dumps(snapshots),
                encoding="utf-8",
            )
            previous_cwd = Path.cwd()

            try:
                os.chdir(temp_path)

                with patch("requests.get", return_value=response):
                    runpy.run_path(
                        str(PROJECT_DIR / "generate_news.py"),
                        run_name="__main__",
                    )
            finally:
                os.chdir(previous_cwd)

            return json.loads(
                (temp_path / "news_candidates.json").read_text(
                    encoding="utf-8"
                )
            )[0]

    def test_unchanged_description_is_not_republished(self):
        description = (
            "UPDATE 21 - The RIVALS Summer Event is here!\n"
            "Complete contracts for exclusive rewards."
        )

        candidate = self.run_generator(description, description)

        self.assertEqual(candidate["score"], 0)
        self.assertEqual(candidate["facts"], [])

    def test_specific_brookhaven_update_beats_generic_update(self):
        candidate = self.run_generator(
            "Latest Update:",
            (
                "Latest Update:\n"
                "Bank Update - A new, refreshed Bank is now open!\n"
                "Updated Tools - New credit cards, cash bags and more!"
            ),
        )

        self.assertGreaterEqual(candidate["score"], 8)
        self.assertTrue(
            any("Bank Update" in fact["text"] for fact in candidate["facts"])
        )

    def test_adopt_me_style_event_lines_are_concrete(self):
        candidate = self.run_generator(
            "Welcome!",
            (
                "Welcome!\n"
                "Tux & Shepherd on the Stray Case\n"
                "Find forks for the Mysterious Stranger!\n"
                "Chihuahua found in Basic and Crystal Eggs!"
            ),
        )

        kinds = {fact["kind"] for fact in candidate["facts"]}
        self.assertTrue({"event", "quests", "pets"}.issubset(kinds))
        self.assertGreaterEqual(candidate["score"], 9)

    def test_brookhaven_prison_lines_are_facts_without_update_word(self):
        candidate = self.run_generator(
            "Welcome to Brookhaven!",
            (
                "Welcome to Brookhaven!\n"
                "Prison Landmark\n"
                "Warden tear gas launcher and pistol\n"
                "prisoner bus\n"
                "new handcuffs\n"
                "shank\n"
                "scanner wand\n"
                "prison props"
            )
        )

        kinds = {fact["kind"] for fact in candidate["facts"]}
        summaries = [fact.get("summary_ru", "") for fact in candidate["facts"]]

        self.assertTrue({"locations", "items", "vehicle"}.issubset(kinds))
        self.assertTrue(any("тюрьм" in summary for summary in summaries))
        self.assertTrue(any("автобус" in summary for summary in summaries))
        self.assertTrue(any(
            "пусковую установку со слезоточивым газом" in summary
            for summary in summaries
        ))
        self.assertTrue(all(summaries))
        self.assertFalse(any(
            summary.strip().lower() in {
                "prison landmark", "prisoner bus", "shank",
                "scanner wand", "prison props"
            }
            for summary in summaries
        ))


if __name__ == "__main__":
    unittest.main()
