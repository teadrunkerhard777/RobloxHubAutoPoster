import ast
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from external_news_facts import (
    MAX_ARTICLE_AGE_DAYS,
    SECONDARY_NEWS_MAX_AGE_DAYS,
    classify_news_event,
    contains_rumor_signal,
    extract_external_facts,
    get_article_age_days,
    has_game_news_meaning,
)
from news_post_formatting import format_fact_paragraph, join_fact_paragraphs
from source_health import (
    ALREADY_USED,
    EXTRACTION_FAILED,
    FOUND_REJECTED,
    FOUND_VERIFIED,
    NO_NEW_CONTENT,
    SOURCE_STALE,
    SOURCE_UNAVAILABLE,
)

PROJECT_ROOT = Path(__file__).parents[1]
NOW = datetime(2026, 8, 28, 8, 0, tzinfo=timezone.utc)
LOCAL_TIMEZONE = timezone(timedelta(hours=5))


def load_verify_functions():
    path = PROJECT_ROOT / "verify_news.py"
    tree = ast.parse(path.read_text(encoding="utf-8"))
    names = {
        "article_used_on_another_day",
        "articles_describe_same_news",
        "evaluate_external_result",
    }
    nodes = [
        node
        for node in tree.body
        if isinstance(node, ast.FunctionDef) and node.name in names
    ]
    namespace = {
        "ALREADY_USED": ALREADY_USED,
        "EXTRACTION_FAILED": EXTRACTION_FAILED,
        "FOUND_REJECTED": FOUND_REJECTED,
        "FOUND_VERIFIED": FOUND_VERIFIED,
        "LOCAL_TIMEZONE": LOCAL_TIMEZONE,
        "MAX_ARTICLE_AGE_DAYS": MAX_ARTICLE_AGE_DAYS,
        "NO_NEW_CONTENT": NO_NEW_CONTENT,
        "SECONDARY_NEWS_MAX_AGE_DAYS": SECONDARY_NEWS_MAX_AGE_DAYS,
        "SOURCE_STALE": SOURCE_STALE,
        "SOURCE_UNAVAILABLE": SOURCE_UNAVAILABLE,
        "contains_rumor_signal": contains_rumor_signal,
        "classify_news_event": classify_news_event,
        "extract_external_facts": extract_external_facts,
        "get_article_age_days": get_article_age_days,
        "has_game_news_meaning": has_game_news_meaning,
        "re": __import__("re"),
    }
    exec(  # noqa: S102
        compile(ast.Module(body=nodes, type_ignores=[]), str(path), "exec"), namespace
    )
    return namespace


def load_format_functions():
    path = PROJECT_ROOT / "format_news_ru.py"
    tree = ast.parse(path.read_text(encoding="utf-8"))
    names = {
        "normalize_game_name",
        "extract_update_number",
        "extract_event_name",
        "extract_name_before_dash",
        "translate_fact",
        "build_item",
        "select_news_items",
    }
    constants = {"GAME_NAMES", "GAME_EMOJIS", "MAX_NEWS_ITEMS"}
    nodes = []
    for node in tree.body:
        if isinstance(node, ast.FunctionDef) and node.name in names:
            nodes.append(node)
        elif isinstance(node, ast.Assign):
            assigned = {
                target.id for target in node.targets if isinstance(target, ast.Name)
            }
            if assigned.intersection(constants):
                nodes.append(node)

    namespace = {
        "re": __import__("re"),
        "format_fact_paragraph": format_fact_paragraph,
        "join_fact_paragraphs": join_fact_paragraphs,
    }
    exec(  # noqa: S102
        compile(ast.Module(body=nodes, type_ignores=[]), str(path), "exec"), namespace
    )
    return namespace


VERIFY = load_verify_functions()
FORMAT = load_format_functions()


class RobloxNewsStrategyTests(unittest.TestCase):
    def make_result(self, age_days=2, *, tier="A", title="Bank Update", text=None):
        if text is None:
            text = "The Bank Update adds a new bank location and rewards for players."
        return {
            "game": "Brookhaven",
            "source_type": "official_news_website",
            "source_tier": tier,
            "success": True,
            "url": "https://official.example/news",
            "publisher": "PCGamesN" if tier == "B" else None,
            "latest_article": {
                "success": True,
                "url": "https://official.example/news/bank-update",
                "title": title,
                "published_at": (NOW - timedelta(days=age_days)).isoformat(),
                "text": text,
            },
        }

    def evaluate(self, result, history=None):
        candidate = {"game": "Brookhaven"}
        return VERIFY["evaluate_external_result"](candidate, result, history or [], NOW)

    def test_official_article_needs_no_second_confirmation(self):
        diagnostic, _, facts = self.evaluate(self.make_result())
        self.assertEqual(diagnostic["result_code"], FOUND_VERIFIED)
        self.assertTrue(diagnostic["official"])
        self.assertTrue(facts)

    def test_primary_window_is_fourteen_days(self):
        diagnostic, _, facts = self.evaluate(self.make_result(age_days=14))
        self.assertTrue(facts)
        self.assertEqual(diagnostic["freshness_window"], "primary_14_day")

    def test_fifteen_to_thirty_days_is_emergency_candidate(self):
        diagnostic, _, facts = self.evaluate(self.make_result(age_days=20))
        self.assertTrue(facts)
        self.assertEqual(diagnostic["freshness_window"], "emergency_30_day")

    def test_used_url_never_repeats_on_another_day(self):
        result = self.make_result()
        history = [
            {
                "url": result["latest_article"]["url"],
                "selected_date": "2026-08-27",
            }
        ]
        diagnostic, _, facts = self.evaluate(result, history)
        self.assertEqual(diagnostic["result_code"], ALREADY_USED)
        self.assertEqual(facts, [])

    def test_syndicated_copy_is_recognized_as_the_same_news(self):
        official = {"title": "Lucky Block Breakout!"}
        secondary = {
            "title": (
                "Pet Simulator 99 Lucky Block Breakout Update 90: "
                "Breakout Board and rewards"
            )
        }
        self.assertTrue(VERIFY["articles_describe_same_news"](official, secondary))

    def test_rumor_is_rejected(self):
        result = self.make_result(
            title="Leaked Bank Update",
            text="A datamine allegedly reveals a possible new bank event.",
        )
        diagnostic, _, facts = self.evaluate(result)
        self.assertEqual(diagnostic["result_code"], FOUND_REJECTED)
        self.assertEqual(facts, [])

    def test_tier_b_fact_is_attributed(self):
        _, _, facts = self.evaluate(self.make_result(tier="B"))
        self.assertTrue(facts)
        self.assertTrue(
            any("По данным PCGamesN" in fact["summary_ru"] for fact in facts)
        )

    def test_persisted_tier_b_reference_is_rejected_during_verification(self):
        result = self.make_result(
            tier="B",
            title="All Pets in Steal An Egg: Rarity, income, and more",
            text="A complete rarity and income reference for every existing pet.",
        )
        diagnostic, _, facts = self.evaluate(result)
        self.assertEqual(diagnostic["result_code"], FOUND_REJECTED)
        self.assertIn("guide/reference", diagnostic["reason"])
        self.assertEqual(facts, [])

    def test_official_english_fact_is_not_silently_discarded(self):
        _, _, facts = self.evaluate(self.make_result())
        candidate = {
            "game": "Brookhaven",
            "score": 6,
            "facts": facts,
            "external_news_article": {
                "url": "https://official.example/news/bank-update"
            },
        }
        item = FORMAT["build_item"](candidate)
        self.assertIsNotNone(item)
        self.assertTrue(item["text"].strip())

    def test_morning_selection_returns_one_when_only_one_is_worthy(self):
        formatted = [({}, {"game": "Brookhaven", "text": "Новость"}, False)]
        self.assertEqual(len(FORMAT["select_news_items"](formatted)), 1)

    def test_morning_selection_returns_at_most_three_different_games(self):
        formatted = [
            ({}, {"game": game, "text": game}, False)
            for game in ["Brookhaven", "RIVALS", "Adopt Me!", "Blade Ball"]
        ]
        items = FORMAT["select_news_items"](formatted)
        self.assertEqual(len(items), 3)
        self.assertEqual(len({item["game"] for item in items}), 3)

    def test_emergency_pool_is_used_only_if_primary_pool_is_empty(self):
        mixed = [
            ({}, {"game": "Old game", "text": "20 days"}, True),
            ({}, {"game": "Fresh game", "text": "2 days"}, False),
        ]
        self.assertEqual(
            [item["game"] for item in FORMAT["select_news_items"](mixed)],
            ["Fresh game"],
        )
        emergency_only = [({}, {"game": "Old game", "text": "20 days"}, True)]
        self.assertEqual(len(FORMAT["select_news_items"](emergency_only)), 1)


if __name__ == "__main__":
    unittest.main()
