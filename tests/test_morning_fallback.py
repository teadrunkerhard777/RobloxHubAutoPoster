import ast
import os
import unittest
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

from post_hashtags import add_post_hashtags
from post_headings import ROBLOX_NEWS_HEADING

PROJECT_ROOT = Path(__file__).parents[1]


def load_morning_functions():
    """Loads morning functions without executing the queue generator."""

    path = PROJECT_ROOT / "generate_posts.py"
    tree = ast.parse(path.read_text(encoding="utf-8"))
    function_names = {
        "build_post",
        "fit_telegram_caption",
        "find_post",
        "build_news_action",
        "generate_morning_post",
        "mark_roblox_news_scheduled",
        "schedule_morning_post",
        "resolve_news_header",
    }
    constant_names = {
        "LOCAL_TIMEZONE",
        "ROBLOX_NEWS_HOUR",
        "ROBLOX_NEWS_HEADER_PATH",
        "TELEGRAM_CAPTION_MAX_CHARS",
        "GAME_EMOJIS",
    }
    selected_nodes = []

    for node in tree.body:
        if isinstance(node, ast.FunctionDef) and node.name in function_names:
            selected_nodes.append(node)
        elif isinstance(node, ast.Assign):
            assigned_names = {
                target.id for target in node.targets if isinstance(target, ast.Name)
            }
            if assigned_names.intersection(constant_names):
                selected_nodes.append(node)

    namespace = {
        "add_post_hashtags": add_post_hashtags,
        "ROBLOX_NEWS_HEADING": ROBLOX_NEWS_HEADING,
        "datetime": datetime,
        "timedelta": timedelta,
        "timezone": timezone,
        "os": os,
    }
    isolated_module = ast.Module(body=selected_nodes, type_ignores=[])

    # Выполняются только выбранные функции локального проекта.
    # Рабочая очередь и история новостей не читаются и не пишутся.
    exec(  # noqa: S102
        compile(isolated_module, str(path), "exec"),
        namespace,
    )

    return namespace


morning_namespace = load_morning_functions()
generate_morning_post = morning_namespace["generate_morning_post"]
schedule_morning_post = morning_namespace["schedule_morning_post"]
mark_roblox_news_scheduled = morning_namespace["mark_roblox_news_scheduled"]


class MorningNewsTests(unittest.TestCase):
    def test_zero_eligible_roblox_news_creates_no_ten_oclock_post(self):
        morning_namespace["load_json"] = lambda filename, default=None: {"items": []}
        news_text = generate_morning_post()
        posts = []

        added, updated = schedule_morning_post(
            posts,
            date(2026, 9, 8),
            news_text=news_text,
        )

        self.assertIsNone(news_text)
        self.assertEqual((added, updated), (0, 0))
        self.assertEqual(posts, [])

    def test_one_eligible_roblox_news_creates_ten_oclock_post(self):
        morning_namespace["load_json"] = lambda filename, default=None: {
            "items": [
                {
                    "emoji": "🏡",
                    "game": "Brookhaven",
                    "text": "Проверенная свежая новость.",
                }
            ]
        }
        news_text = generate_morning_post()
        posts = []

        added, updated = schedule_morning_post(
            posts,
            date(2026, 9, 8),
            news_text=news_text,
        )

        self.assertEqual((added, updated), (1, 0))
        self.assertEqual(len(posts), 1)
        self.assertEqual(posts[0]["id"], "2026-09-08-10")
        self.assertEqual(posts[0]["source"], "auto_verified")
        self.assertEqual(posts[0]["rubric"], "Выпуск дня")
        self.assertIn(ROBLOX_NEWS_HEADING, posts[0]["text"])
        self.assertIn("Проверенная свежая новость.", posts[0]["text"])

    def test_old_pending_fallback_is_removed_when_news_are_absent(self):
        posts = [
            {
                "id": "2026-09-08-10",
                "publish_at": "2026-09-08T10:00:00+05:00",
                "status": "pending",
                "source": "verified_fallback",
                "text": "Старый fallback",
            }
        ]

        added, updated = schedule_morning_post(
            posts,
            date(2026, 9, 8),
            news_text=None,
        )

        self.assertEqual((added, updated), (0, 1))
        self.assertEqual(posts, [])

    def test_published_morning_post_is_never_removed(self):
        posts = [
            {
                "id": "2026-09-08-10",
                "publish_at": "2026-09-08T10:00:00+05:00",
                "status": "published",
                "source": "verified_fallback",
                "text": "Уже опубликовано",
            }
        ]

        added, updated = schedule_morning_post(
            posts,
            date(2026, 9, 8),
            news_text=None,
        )

        self.assertEqual((added, updated), (0, 0))
        self.assertEqual(posts[0]["text"], "Уже опубликовано")

    def test_tier_b_source_is_printed_after_facts_and_action(self):
        morning_namespace["load_json"] = lambda filename, default=None: {
            "items": [
                {
                    "emoji": "🐾",
                    "game": "Adopt Me!",
                    "text": "🎉 Вышло обновление.\n\n🔹 Добавлен новый дом.",
                    "player_action": "🎯 Что проверить: посмотри новый дом.",
                    "source_attribution": "Источник: Sportskeeda",
                }
            ]
        }

        post = generate_morning_post()

        self.assertIn(
            "🎯 Что проверить: посмотри новый дом.\n\nИсточник: Sportskeeda",
            post,
        )

    def test_url_history_is_consumed_only_after_real_scheduling(self):
        article_url = "https://example.com/fresh-news"
        generated = {
            "items": [{"game": "Brookhaven", "external_article_url": article_url}],
            "pipeline": [{"selected": True, "scheduled": False}],
            "summary": {"found": 1, "verified": 1, "selected": 1},
        }
        history = [
            {
                "url": article_url,
                "game": "Brookhaven",
                "selected_date": datetime.now(morning_namespace["LOCAL_TIMEZONE"])
                .date()
                .isoformat(),
            }
        ]
        saved = {}

        def load_json(filename, default=None):
            if filename == "generated_news_data_ru.json":
                return generated
            if filename == "external_news_history.json":
                return history
            return default

        morning_namespace["load_json"] = load_json
        morning_namespace["save_json"] = lambda filename, data: saved.__setitem__(
            filename, data
        )
        mark_roblox_news_scheduled(False)

        self.assertEqual(saved["external_news_history.json"], [])
        self.assertEqual(
            saved["generated_news_data_ru.json"]["summary"]["scheduled"], 0
        )

        history.clear()
        mark_roblox_news_scheduled(True)
        self.assertEqual(saved["external_news_history.json"][0]["url"], article_url)
        self.assertEqual(
            saved["generated_news_data_ru.json"]["summary"]["scheduled"], 1
        )

    def test_missing_roblox_header_keeps_news_as_text_only(self):
        posts = []

        added, updated = schedule_morning_post(
            posts,
            date(2026, 9, 8),
            news_text="Проверенный Roblox выпуск",
            header_checker=lambda path: False,
        )

        self.assertEqual((added, updated), (1, 0))
        self.assertNotIn("image_path", posts[0])
        self.assertEqual(posts[0]["text"], "Проверенный Roblox выпуск")

    def test_roblox_photo_caption_respects_telegram_limit(self):
        long_text = f"Заголовок\n\n{'важный факт ' * 200}\n\n🎮 Roblox Hub"
        posts = []

        schedule_morning_post(
            posts,
            date(2026, 9, 8),
            news_text=long_text,
            header_checker=lambda path: True,
        )

        caption = posts[0]["text"]
        self.assertLessEqual(len(caption), 1024)
        self.assertTrue(caption.endswith("🎮 Roblox Hub"))
        self.assertNotIn("важ…", caption)


if __name__ == "__main__":
    unittest.main()
