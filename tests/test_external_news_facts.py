import unittest
from datetime import datetime, timezone

from external_news_facts import (
    NEWS_MAX_AGE_DAYS,
    SECONDARY_NEWS_MAX_AGE_DAYS,
    contains_rumor_signal,
    extract_external_facts,
    is_fresh_article,
    is_news_event,
)

NOW = datetime(2026, 8, 16, 12, 0, tzinfo=timezone.utc)


class ExternalNewsFactsTests(unittest.TestCase):
    def test_tier_b_event_article_extracts_two_to_four_concrete_facts(self):
        article = {
            "success": True,
            "source_tier": "B",
            "publisher": "Sportskeeda",
            "url": "https://example.com/adopt-me-moonlight-event",
            "title": "Adopt Me launches new Moonlight event",
            "published_at": "2026-09-04T18:27:00Z",
            "text": (
                "The Moonlight event is now live.\n"
                "Players can collect Moon Tokens by completing nightly tasks.\n"
                "New Luna Fox pet can be unlocked for 500 Moon Tokens.\n"
                "The event ends on September 12, 2026."
            ),
        }

        facts = extract_external_facts(
            "Adopt Me!",
            article,
            now=datetime(2026, 9, 5, 8, tzinfo=timezone.utc),
        )
        summaries = [fact["summary_ru"] for fact in facts]

        self.assertEqual(len(facts), 4)
        self.assertIn("🎉 В Adopt Me! началось событие Moonlight.", summaries)
        self.assertTrue(any("Moon Tokens" in value for value in summaries))
        self.assertTrue(any("Luna Fox" in value for value in summaries))
        self.assertTrue(any("September 12, 2026" in value for value in summaries))
        self.assertFalse(any("новое событие" in value.lower() for value in summaries))

    def test_tier_b_adopt_me_event_keeps_current_article_details(self):
        article = {
            "success": True,
            "source_tier": "B",
            "publisher": "Sportskeeda",
            "url": "https://www.sportskeeda.com/roblox-news/"
            "adopt-me-fairytale-castle-update-patch-notes",
            "title": "Adopt Me Fairytale Castle update patch notes",
            "published_at": "2026-09-04T18:27:00Z",
            "text": (
                "Adopt Me Fairytale Castle update patch notes\n"
                "Fairytale Castle - 8,000 Bucks\n"
                "Ballet Swan - 600 Robux - Legendary\n"
                "Added an offer button to allow players to suggest items "
                "on listings in the Trading Hub."
            ),
        }

        facts = extract_external_facts(
            "Adopt Me!",
            article,
            now=datetime(2026, 9, 5, 8, tzinfo=timezone.utc),
        )
        summaries = [fact["summary_ru"] for fact in facts]

        self.assertEqual(len(facts), 4)
        self.assertIn("🎉 В Adopt Me! вышло обновление Fairytale Castle.", summaries)
        self.assertTrue(any("8,000 Bucks" in value for value in summaries))
        self.assertTrue(any("Ballet Swan" in value for value in summaries))
        self.assertTrue(any("Trading Hub" in value for value in summaries))
        self.assertFalse(any("новое событие" in value.lower() for value in summaries))

    def test_tier_b_article_with_one_detail_does_not_invent_more(self):
        article = {
            "success": True,
            "source_tier": "B",
            "publisher": "Sportskeeda",
            "url": "https://example.com/adopt-me-castle",
            "title": "Adopt Me Fairytale Castle update patch notes",
            "published_at": "2026-09-04T18:27:00Z",
            "text": "Fairytale Castle - 8,000 Bucks",
        }

        facts = extract_external_facts(
            "Adopt Me!",
            article,
            now=datetime(2026, 9, 5, 8, tzinfo=timezone.utc),
        )
        combined = " ".join(fact["summary_ru"] for fact in facts)

        self.assertEqual(len(facts), 2)
        self.assertIn("8,000 Bucks", combined)
        self.assertNotIn("Ballet Swan", combined)
        self.assertNotIn("награ", combined.lower())
        self.assertNotIn("сентябр", combined.lower())

    def test_freshness_window_is_fourteen_days(self):
        self.assertEqual(NEWS_MAX_AGE_DAYS, 14)

        article = {
            "success": True,
            "url": "https://example.com/thirteen-days-old",
            "published_at": "2026-08-03T12:00:00Z",
        }

        self.assertTrue(is_fresh_article(article, now=NOW))

    def test_rejects_article_older_than_fourteen_days(self):
        article = {
            "success": True,
            "url": "https://example.com/fifteen-days-old",
            "published_at": "2026-08-01T00:00:00Z",
        }

        self.assertFalse(is_fresh_article(article, now=NOW))

    def test_rejects_old_article(self):
        article = {
            "success": True,
            "url": "https://example.com/old",
            "published_at": ("2026-07-01T22:02:43Z"),
        }

        self.assertFalse(is_fresh_article(article, now=NOW))

    def test_rejects_article_without_date(self):
        article = {
            "success": True,
            "url": "https://example.com/no-date",
            "published_at": None,
        }

        self.assertFalse(is_fresh_article(article, now=NOW))

    def test_extracts_adopt_me_pet_and_task(self):
        article = {
            "success": True,
            "url": ("https://www.playadopt.me/" "news/stray-case"),
            "title": ("Tux & Shepherd on the " "Stray Case Notes! - Adopt Me!"),
            "published_at": ("2026-08-14T15:00:00.000Z"),
            "text": (
                "Bring the Mysterious Stranger "
                "6 Bundles of Forks in exchange "
                "for 75 Bucks.\n"
                "🐶 Chihuahua - Hatch from the "
                "Basic & Crystal Egg -\n"
                "Ultra Rare"
            ),
        }

        facts = extract_external_facts("Adopt Me!", article, now=NOW)

        summaries = [fact["summary_ru"] for fact in facts]

        self.assertEqual(len(facts), 3)
        self.assertTrue(
            any(
                "Chihuahua" in summary and "Ultra Rare" in summary
                for summary in summaries
            )
        )
        self.assertTrue(
            any(
                "6 связок" in summary and "75 Bucks" in summary for summary in summaries
            )
        )

    def test_accepts_blox_fruits_inside_fourteen_days(self):
        article = {
            "success": True,
            "url": ("https://gamerrobot.com/" "blogs/news/the-balance-log"),
            "title": "The Balance Log",
            "published_at": ("2026-08-06T22:02:43Z"),
            "text": ("The Summer PvP Patch Notes " "- Balance Patch 001"),
        }

        self.assertTrue(extract_external_facts("Blox Fruits", article, now=NOW))

    def test_balance_patch_keeps_exact_names_numbers_and_multiple_changes(self):
        article = {
            "success": True,
            "url": "https://gamerrobot.com/blogs/news/the-balance-log",
            "title": "The Balance Log",
            "published_at": "2026-08-06T22:02:43Z",
            "text": "The Summer PvP Patch Notes - Balance Patch 001",
            "structured_content": [
                {
                    "category": "Fruits",
                    "name": "Control",
                    "ability": "X",
                    "change": (
                        "Cooldown increased by 4 seconds; "
                        "hitbox size decreased by 10%."
                    ),
                },
                {
                    "category": "Systems",
                    "name": "Instinct",
                    "ability": "DODGES",
                    "change": (
                        "Dodge regeneration time decreased from 40 seconds "
                        "to 30 seconds, allowing Instinct dodges to replenish "
                        "25% faster."
                    ),
                },
                {
                    "category": "Fighting Styles",
                    "name": "Death Step",
                    "ability": "C",
                    "change": (
                        "Damage over time increased by 20%; "
                        "end-lag decreased from 0.25 seconds to 0.1 seconds."
                    ),
                },
            ],
        }

        facts = extract_external_facts("Blox Fruits", article, now=NOW)
        summaries = [fact["summary_ru"] for fact in facts]

        self.assertEqual(len(facts), 4)
        self.assertTrue(any("Control (X)" in value for value in summaries))
        self.assertTrue(
            any("4 секунд" in value and "10%" in value for value in summaries)
        )
        self.assertTrue(
            any("40 секунд" in value and "30 секунд" in value for value in summaries)
        )
        self.assertTrue(
            any("Death Step (C)" in value and "0.25" in value for value in summaries)
        )

    def test_structured_patch_deduplicates_and_limits_long_articles(self):
        categories = ["Fruits", "Systems", "Fighting Styles", "Swords", "Guns"]
        rows = [
            {
                "category": category,
                "name": f"Exact {category}",
                "ability": "Z",
                "change": "Damage increased by 10%.",
            }
            for category in categories
        ]
        rows.append(dict(rows[0]))
        article = {
            "success": True,
            "url": "https://gamerrobot.com/blogs/news/the-balance-log",
            "title": "The Balance Log",
            "published_at": "2026-08-06T22:02:43Z",
            "text": "The Summer PvP Patch Notes - Balance Patch 001",
            "structured_content": rows,
        }

        facts = extract_external_facts("Blox Fruits", article, now=NOW)
        details = [fact for fact in facts if fact["kind"] == "balance_change"]

        self.assertEqual(len(details), 3)
        self.assertEqual(len({fact["summary_ru"] for fact in details}), 3)

    def test_structured_patch_with_one_fact_does_not_invent_more(self):
        article = {
            "success": True,
            "url": "https://gamerrobot.com/blogs/news/the-balance-log",
            "title": "The Balance Log",
            "published_at": "2026-08-06T22:02:43Z",
            "text": "The Summer PvP Patch Notes - Balance Patch 001",
            "structured_content": [
                {
                    "category": "Fruits",
                    "name": "Control",
                    "ability": "X",
                    "change": "Cooldown increased by 4 seconds.",
                }
            ],
        }

        facts = extract_external_facts("Blox Fruits", article, now=NOW)

        self.assertEqual(len(facts), 2)
        self.assertEqual(
            len([fact for fact in facts if fact["kind"] == "balance_change"]), 1
        )

    def test_secondary_window_can_reach_thirty_days_explicitly(self):
        self.assertEqual(SECONDARY_NEWS_MAX_AGE_DAYS, 30)
        article = {
            "success": True,
            "url": "https://example.com/twenty-days-old",
            "title": "New event update",
            "published_at": "2026-07-27T12:00:00Z",
            "text": "A new event update adds rewards and a game mode for players.",
        }

        self.assertFalse(is_fresh_article(article, now=NOW))
        self.assertTrue(
            is_fresh_article(
                article,
                now=NOW,
                max_age_days=SECONDARY_NEWS_MAX_AGE_DAYS,
            )
        )

    def test_rumor_or_leak_is_rejected(self):
        article = {
            "success": True,
            "url": "https://example.com/leak",
            "title": "Possible leaked update",
            "published_at": "2026-08-15T12:00:00Z",
            "text": "A datamine allegedly shows a new event.",
        }

        self.assertTrue(contains_rumor_signal(article))
        self.assertEqual(extract_external_facts("Brookhaven", article, now=NOW), [])

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
            ),
        }

        facts = extract_external_facts(
            "Adopt Me!", article, now=datetime(2026, 8, 23, 8, tzinfo=timezone.utc)
        )
        summaries = [fact["summary_ru"] for fact in facts]

        self.assertTrue(
            any(
                "Kiwi Kiwi" in summary
                and "Strawberry Tortle" in summary
                and "легендар" in summary
                for summary in summaries
            )
        )
        self.assertTrue(
            any(
                "Backpack Storage" in summary and "несколько" in summary
                for summary in summaries
            )
        )
        self.assertLessEqual(len(facts), 5)
        self.assertTrue(any(fact["value"] > 6 for fact in facts))

    def test_rejects_pet_simulator_title_only_article(self):
        article = {
            "success": True,
            "url": "https://www.biggames.io/post/pet-simulator-99-update-90",
            "title": "Lucky Block Breakout!",
            "published_at": "2026-08-22",
            "text": "Lucky Block Breakout!",
        }

        self.assertEqual(
            extract_external_facts(
                "Pet Simulator 99",
                article,
                now=datetime(2026, 8, 23, 8, tzinfo=timezone.utc),
            ),
            [],
        )

    def test_keeps_title_only_article_when_title_is_concrete(self):
        article = {
            "success": True,
            "url": "https://example.com/new-prison-landmark",
            "title": "New Prison Landmark",
            "published_at": "2026-08-22",
            "text": "New Prison Landmark",
        }

        facts = extract_external_facts(
            "Brookhaven", article, now=datetime(2026, 8, 23, 8, tzinfo=timezone.utc)
        )

        self.assertTrue(facts)
        self.assertTrue(any(fact["kind"] == "official_article" for fact in facts))

    def test_extracts_big_games_update_from_split_layout(self):
        article = {
            "success": True,
            "url": "https://www.biggames.io/post/pet-simulator-99-update-90",
            "title": "Lucky Block Breakout!",
            "published_at": "2026-08-22",
            "text": (
                "Lucky Block Breakout!\n"
                "Event\n"
                "Breakout Board\n"
                "Lucky Blocks\nspawn in\nwaves\n"
                "Collect all\n13\nbrand-new\nLucky Block\npets!\n"
                "Breakout Leaderboard\nPush as deep as you can."
            ),
        }

        facts = extract_external_facts(
            "Pet Simulator 99",
            article,
            now=datetime(2026, 8, 27, 8, tzinfo=timezone.utc),
        )
        summaries = [fact["summary_ru"] for fact in facts]

        self.assertEqual(len(facts), 4)
        self.assertTrue(any("Lucky Block Breakout" in value for value in summaries))
        self.assertTrue(any("Breakout Board" in value for value in summaries))
        self.assertTrue(any("13" in value and "питом" in value for value in summaries))

    def test_rejects_empty_big_games_article(self):
        article = {
            "success": True,
            "url": "https://www.biggames.io/post/empty",
            "title": "Update",
            "published_at": "2026-08-22",
            "text": "Home Blogs Merch Contact",
        }

        self.assertEqual(
            extract_external_facts(
                "Pet Simulator 99",
                article,
                now=datetime(2026, 8, 27, 8, tzinfo=timezone.utc),
            ),
            [],
        )

    def test_brookhaven_tier_b_update_keeps_named_details(self):
        article = {
            "success": True,
            "source_tier": "B",
            "publisher": "PCGamesN",
            "url": "https://example.com/brookhaven-prison-update",
            "title": "Brookhaven Prison Update is live",
            "published_at": "2026-08-15T12:00:00Z",
            "text": (
                "The update adds a new prison landmark.\n"
                "Added prisoner bus.\n"
                "New warden tear gas launcher and pistol."
            ),
        }

        self.assertTrue(is_news_event(article))
        facts = extract_external_facts("Brookhaven", article, now=NOW)
        summaries = [fact["summary_ru"] for fact in facts]
        self.assertTrue(any("тюрьм" in summary for summary in summaries))
        self.assertTrue(any("тюремный автобус" in summary for summary in summaries))
        self.assertTrue(any("слезоточивым газом" in summary for summary in summaries))

    def test_brookhaven_official_update_keeps_convertible_details(self):
        article = {
            "success": True,
            "url": "https://www.brookhavenrp.com/posts/lavender-luxury",
            "title": "Brookhaven Update August 28, 2026: Lavender Luxury",
            "published_at": "2026-08-28",
            "text": "New vehicle pack convertible car with neon flower tail lights",
        }

        facts = extract_external_facts(
            "Brookhaven RP",
            article,
            now=datetime(2026, 8, 29, 8, tzinfo=timezone.utc),
        )
        summaries = [fact["summary_ru"] for fact in facts]
        self.assertTrue(
            any(
                "кабриолет" in summary and "неоновыми" in summary
                for summary in summaries
            )
        )


if __name__ == "__main__":
    unittest.main()
