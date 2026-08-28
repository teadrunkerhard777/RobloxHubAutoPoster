import unittest

from post_headings import (
    BRAWL_NEWS_HEADING,
    HITS_HEADING,
    MYTH_OR_TRUTH_HEADING,
    ROBLOX_FALLBACK_HEADING,
    ROBLOX_NEWS_HEADING,
    USEFUL_TIPS_HEADING,
)
from tips_rotation import build_hits_post, build_tips_post


class PostHeadingTests(unittest.TestCase):
    def test_roblox_news_headings_use_plain_symmetric_text(self):
        self.assertEqual(ROBLOX_NEWS_HEADING, "🎮🎮🎮 ROBLOX HUB — СЕГОДНЯ 🎮🎮🎮")
        self.assertEqual(ROBLOX_FALLBACK_HEADING, "🎮🎮🎮 ROBLOX HUB — УТРО 🎮🎮🎮")

    def test_brawl_news_uses_new_heading(self):
        self.assertEqual(BRAWL_NEWS_HEADING, "💥💥💥 НОВОСТИ BRAWL STARS 💥💥💥")

    def test_useful_tips_heading_is_followed_by_blank_line(self):
        self.assertEqual(USEFUL_TIPS_HEADING, "💡💡💡 ПОЛЕЗНО ЗНАТЬ 💡💡💡")
        _, text = build_tips_post(
            [{"game": "RIVALS", "text": "Тест", "category": "strategy"}],
            {"RIVALS": "🔫"},
        )
        self.assertTrue(text.startswith(f"{USEFUL_TIPS_HEADING}\n\n"))
        self.assertIn("🔫 RIVALS\n🎯 Тест", text)

    def test_hits_heading_is_followed_by_blank_line(self):
        self.assertEqual(HITS_HEADING, "🔥🔥🔥 НОВИНКИ И ХИТЫ ROBLOX 🔥🔥🔥")
        tips = [
            {
                "id": index,
                "game": "RIVALS",
                "text": f"Совет {index}",
                "category": "strategy",
            }
            for index in range(1, 4)
        ]
        _, text = build_hits_post("RIVALS", "Описание.", tips, {"RIVALS": "🔫"})
        self.assertTrue(text.startswith(f"{HITS_HEADING}\n\n"))
        self.assertIn("🎮 Что за игра?\nОписание.", text)

    def test_legacy_myth_heading_is_available_in_new_style(self):
        self.assertEqual(MYTH_OR_TRUTH_HEADING, "🧠🧠🧠 МИФ ИЛИ ПРАВДА? 🧠🧠🧠")

    def test_headings_do_not_use_telegram_markup(self):
        headings = (
            ROBLOX_NEWS_HEADING,
            ROBLOX_FALLBACK_HEADING,
            BRAWL_NEWS_HEADING,
            USEFUL_TIPS_HEADING,
            HITS_HEADING,
            MYTH_OR_TRUTH_HEADING,
        )
        for heading in headings:
            self.assertNotIn("<", heading)
            self.assertNotIn("*", heading)
            self.assertNotIn("_", heading)


if __name__ == "__main__":
    unittest.main()
