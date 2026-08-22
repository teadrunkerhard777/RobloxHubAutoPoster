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

    def test_extracts_backpack_storage_and_releaser_details(self):
        article = {
            "success": True,
            "url": "https://www.playadopt.me/news/backpack-storage",
            "title": "Backpack Storage & Releaser Refresh! - Adopt Me!",
            "published_at": "2026-08-21T15:05:00.000Z",
            "text": (
                "New Releaser Pets!\n"
                "There are two new Legendary pets to collect from "
                "Basic & Crystal Eggs:\n"
                "🥝 Kiwi Kiwi -\nLegendary\n"
                "🍓 Strawberry Tortle -\nLegendary\n"
                "Backpack Storage!\n"
                "Storage gives you a new space to place your items "
                "outside of your backpack.\n"
                "You can move items between your Backpack and Storage.\n"
                "You can select multiple items and move them all at once!\n"
                "Storage Tabs let you organize your Storage."
            )
        }

        facts = extract_external_facts(
            "Adopt Me!",
            article,
            now=datetime(2026, 8, 23, 8, tzinfo=timezone.utc)
        )
        summaries = [fact["summary_ru"] for fact in facts]

        self.assertTrue(any(
            "Kiwi Kiwi" in summary
            and "Strawberry Tortle" in summary
            and "легендар" in summary
            for summary in summaries
        ))
        self.assertTrue(any(
            "Backpack Storage" in summary
            and "несколько" in summary
            for summary in summaries
        ))
        self.assertLessEqual(len(facts), 5)
        self.assertGreater(facts[0]["value"], 6)

    def test_rejects_pet_simulator_title_only_article(self):
        article = {
            "success": True,
            "url": "https://www.biggames.io/post/pet-simulator-99-update-90",
            "title": "Lucky Block Breakout!",
            "published_at": "2026-08-22",
            "text": "Lucky Block Breakout!"
        }

        self.assertEqual(
            extract_external_facts(
                "Pet Simulator 99",
                article,
                now=datetime(2026, 8, 23, 8, tzinfo=timezone.utc)
            ),
            []
        )

    def test_keeps_title_only_article_when_title_is_concrete(self):
        article = {
            "success": True,
            "url": "https://example.com/new-prison-landmark",
            "title": "New Prison Landmark",
            "published_at": "2026-08-22",
            "text": "New Prison Landmark"
        }

        facts = extract_external_facts(
            "Brookhaven",
            article,
            now=datetime(2026, 8, 23, 8, tzinfo=timezone.utc)
        )

        self.assertTrue(facts)
        self.assertTrue(any(
            fact["kind"] == "official_article"
            for fact in facts
        ))


if __name__ == "__main__":
    unittest.main()
