import ast
import json
import unittest
from datetime import date, datetime
from pathlib import Path
from tempfile import TemporaryDirectory

PROJECT_ROOT = Path(__file__).parents[1]


def load_pending_checker():
    """Loads the helper without executing the daily subprocess pipeline."""

    path = PROJECT_ROOT / "prepare_daily_posts.py"
    tree = ast.parse(path.read_text(encoding="utf-8"))
    function = next(
        node
        for node in tree.body
        if isinstance(node, ast.FunctionDef)
        and node.name == "has_fresh_pending_brawl_news"
    )
    namespace = {
        "BRAWL_LATEST_CHANGES_FILE": "data/brawl_latest_changes.json",
        "BRAWL_PENDING_MAX_AGE_DAYS": 7,
        "date": date,
        "datetime": datetime,
        "json": json,
    }
    exec(  # noqa: S102
        compile(ast.Module(body=[function], type_ignores=[]), str(path), "exec"),
        namespace,
    )
    return namespace["has_fresh_pending_brawl_news"]


has_fresh_pending_brawl_news = load_pending_checker()


class PrepareDailyPostsTests(unittest.TestCase):
    def test_fresh_official_medium_article_survives_monitor_failure(self):
        with TemporaryDirectory() as directory:
            latest_path = Path(directory) / "latest.json"
            latest_path.write_text(
                json.dumps(
                    {
                        "medium_priority_articles": [
                            {
                                "url": "https://supercell.com/bsc-2027",
                                "date": "2026-08-24",
                                "priority": "medium",
                                "official": True,
                                "scheduled": False,
                            }
                        ]
                    }
                ),
                encoding="utf-8",
            )

            self.assertTrue(
                has_fresh_pending_brawl_news(
                    latest_path,
                    today=date(2026, 8, 28),
                )
            )

    def test_scheduled_or_stale_article_is_not_recovered(self):
        cases = (
            {"scheduled": True, "date": "2026-08-24"},
            {"scheduled": False, "date": "2026-07-01"},
        )

        for override in cases:
            with self.subTest(override=override), TemporaryDirectory() as directory:
                latest_path = Path(directory) / "latest.json"
                article = {
                    "url": "https://supercell.com/bsc-2027",
                    "priority": "medium",
                    "official": True,
                    **override,
                }
                latest_path.write_text(
                    json.dumps({"medium_priority_articles": [article]}),
                    encoding="utf-8",
                )

                self.assertFalse(
                    has_fresh_pending_brawl_news(
                        latest_path,
                        today=date(2026, 8, 28),
                    )
                )

    def test_colorama_is_declared_for_github_actions(self):
        requirements = (PROJECT_ROOT / "requirements.txt").read_text(encoding="utf-8")

        self.assertIn("colorama==0.4.6", requirements.splitlines())
