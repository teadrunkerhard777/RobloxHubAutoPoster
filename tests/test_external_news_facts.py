import unittest

from datetime import datetime, timezone

from external_news_facts import (
    extract_external_facts,
    is_fresh_article
)


NOW = datetime(
    2026,
    8,
    16,
    12,
    0,
    tzinfo=timezone.utc
)


class ExternalNewsFactsTests(unittest.TestCase):
    def test_rejects_old_article(self):
        article = {
            "success": True,
            "url": "https://example.com/old",
            "published_at": (
                "2026-08-06T22:02:43Z"
            )
        }

        self.assertFalse(
            is_fresh_article(
                article,
                now=NOW
            )
        )

    def test_rejects_article_without_date(self):
        article = {
            "success": True,
            "url": "https://example.com/no-date",
            "published_at": None
        }

        self.assertFalse(
            is_fresh_article(
                article,
                now=NOW
            )
        )

    def test_extracts_adopt_me_pet_and_task(self):
        article = {
            "success": True,
            "url": (
                "https://www.playadopt.me/"
                "news/stray-case"
            ),
            "title": (
                "Tux & Shepherd on the "
                "Stray Case Notes! - Adopt Me!"
            ),
            "published_at": (
                "2026-08-14T15:00:00.000Z"
            ),
            "text": (
                "Bring the Mysterious Stranger "
                "6 Bundles of Forks in exchange "
                "for 75 Bucks.\n"
                "🐶 Chihuahua - Hatch from the "
                "Basic & Crystal Egg -\n"
                "Ultra Rare"
            )
        }

        facts = extract_external_facts(
            "Adopt Me!",
            article,
            now=NOW
        )

        summaries = [
            fact["summary_ru"]
            for fact in facts
        ]

        self.assertEqual(
            len(facts),
            3
        )
        self.assertTrue(
            any(
                "Chihuahua" in summary
                and "Ultra Rare" in summary
                for summary in summaries
            )
        )
        self.assertTrue(
            any(
                "6 связок" in summary
                and "75 Bucks" in summary
                for summary in summaries
            )
        )

    def test_skips_stale_blox_fruits_facts(self):
        article = {
            "success": True,
            "url": (
                "https://gamerrobot.com/"
                "blogs/news/the-balance-log"
            ),
            "title": "The Balance Log",
            "published_at": (
                "2026-08-06T22:02:43Z"
            ),
            "text": (
                "The Summer PvP Patch Notes "
                "- Balance Patch 001"
            )
        }

        self.assertEqual(
            extract_external_facts(
                "Blox Fruits",
                article,
                now=NOW
            ),
            []
        )


if __name__ == "__main__":
    unittest.main()
