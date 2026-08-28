import ast
import os
import unittest
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

from post_hashtags import add_post_hashtags

PROJECT_ROOT = Path(__file__).parents[1]


def load_morning_functions():
    """
    Загружает только утренние функции без запуска генератора.

    generate_posts.py на верхнем уровне работает с реальными
    JSON-файлами. AST-изоляция позволяет проверить очередь,
    news/fallback-развилку и тексты без побочных изменений.
    """

    path = PROJECT_ROOT / "generate_posts.py"
    tree = ast.parse(path.read_text(encoding="utf-8"))
    function_names = {
        "build_post",
        "fit_telegram_caption",
        "find_post",
        "build_news_action",
        "generate_morning_post",
        "is_verified_fallback_tip",
        "build_morning_fallback",
        "generate_morning_fallback",
        "mark_roblox_news_scheduled",
        "schedule_morning_post",
        "resolve_news_header",
    }
    constant_names = {
        "LOCAL_TIMEZONE",
        "ROBLOX_NEWS_HOUR",
        "MORNING_FALLBACK_MAX_TIPS",
        "MORNING_FALLBACK_MIN_TIPS",
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
        "datetime": datetime,
        "timedelta": timedelta,
        "timezone": timezone,
        "os": os,
    }
    isolated_module = ast.Module(
        body=selected_nodes,
        type_ignores=[],
    )

    # Выполняются только выбранные функции локального проекта.
    # Рабочая очередь и история советов не читаются и не пишутся.
    exec(  # noqa: S102
        compile(isolated_module, str(path), "exec"),
        namespace,
    )

    return namespace


morning_namespace = load_morning_functions()
build_morning_fallback = morning_namespace["build_morning_fallback"]
generate_morning_fallback = morning_namespace["generate_morning_fallback"]
generate_morning_post = morning_namespace["generate_morning_post"]
schedule_morning_post = morning_namespace["schedule_morning_post"]
fit_telegram_caption = morning_namespace["fit_telegram_caption"]
mark_roblox_news_scheduled = morning_namespace["mark_roblox_news_scheduled"]


class MorningFallbackTests(unittest.TestCase):
    def make_tip(self, tip_id, game, text, source="verified_core_mechanic"):
        """Создаёт локальный проверенный совет в формате tips.json."""

        return {
            "id": tip_id,
            "game": game,
            "text": text,
            "source": source,
            "category": "strategy",
        }

    def test_fresh_news_creates_regular_morning_post(self):
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
            date(2026, 8, 25),
            news_text=news_text,
            fallback_builder=lambda: self.fail(
                "При свежей новости fallback вызываться не должен"
            ),
        )

        self.assertEqual((added, updated), (1, 0))
        self.assertEqual(posts[0]["source"], "auto_verified")
        self.assertEqual(posts[0]["rubric"], "Выпуск дня")
        self.assertIn("🎮 ROBLOX HUB — СЕГОДНЯ", posts[0]["text"])
        self.assertIn("Проверенная свежая новость.", posts[0]["text"])
        self.assertEqual(
            posts[0]["image_path"],
            "assets/news_headers/roblox_news_header.png",
        )

    def test_url_history_is_consumed_only_after_real_scheduling(self):
        article_url = "https://example.com/fresh-news"
        generated = {
            "items": [
                {
                    "game": "Brookhaven",
                    "external_article_url": article_url,
                }
            ],
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

    def test_no_fresh_news_creates_fallback_at_ten(self):
        posts = []
        fallback_text = "Проверенный полезный fallback"

        added, updated = schedule_morning_post(
            posts,
            date(2026, 8, 25),
            news_text=None,
            fallback_builder=lambda: fallback_text,
        )

        self.assertEqual((added, updated), (1, 0))
        self.assertEqual(posts[0]["id"], "2026-08-25-10")
        self.assertEqual(posts[0]["source"], "verified_fallback")
        self.assertEqual(posts[0]["rubric"], "Утренний выпуск")
        self.assertEqual(posts[0]["text"], fallback_text)
        self.assertEqual(
            posts[0]["image_path"],
            "assets/news_headers/roblox_news_header.png",
        )
        self.assertEqual(
            datetime.fromisoformat(posts[0]["publish_at"]).hour,
            10,
        )

    def test_missing_roblox_header_keeps_text_only_slot(self):
        posts = []

        added, updated = schedule_morning_post(
            posts,
            date(2026, 8, 25),
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
            date(2026, 8, 25),
            news_text=long_text,
            header_checker=lambda path: True,
        )

        caption = posts[0]["text"]
        self.assertLessEqual(len(caption), 1024)
        self.assertTrue(caption.endswith("🎮 Roblox Hub"))
        self.assertNotIn("важ…", caption)

    def test_fallback_contains_at_least_two_different_games(self):
        tips = [
            self.make_tip(1, "99 Nights in the Forest", "Проверенный совет один."),
            self.make_tip(2, "Steal a Brainrot", "Проверенный совет два."),
            self.make_tip(3, "Blox Fruits", "Проверенный совет три."),
        ]

        fallback_text = build_morning_fallback(tips)

        self.assertIn("99 Nights in the Forest", fallback_text)
        self.assertIn("Steal a Brainrot", fallback_text)
        self.assertIn("Blox Fruits", fallback_text)
        self.assertEqual(len({tip["game"] for tip in tips}), 3)

    def test_fallback_does_not_present_tips_as_fresh_news(self):
        tips = [
            self.make_tip(1, "Brookhaven", "Проверенная игровая механика."),
            self.make_tip(2, "Adopt Me!", "Проверенный игровой совет."),
        ]

        fallback_text = build_morning_fallback(tips)

        self.assertIn("без крупных подтверждённых обновлений", fallback_text)
        self.assertNotIn("Сегодня в игре появилось", fallback_text)
        self.assertNotIn("свежее обновление", fallback_text.casefold())

    def test_fallback_uses_only_verified_local_tips(self):
        verified_tips = [
            self.make_tip(1, "RIVALS", "Первый проверенный локальный совет."),
            self.make_tip(2, "Blox Fruits", "Второй проверенный локальный совет."),
        ]
        unverified_tip = self.make_tip(
            3,
            "Unknown Game",
            "Непроверенный текст.",
            source="external_rumor",
        )

        fallback_text = build_morning_fallback([*verified_tips, unverified_tip])

        for tip in verified_tips:
            self.assertIn(tip["text"], fallback_text)

        self.assertNotIn(unverified_tip["text"], fallback_text)
        self.assertNotIn(unverified_tip["game"], fallback_text)

    def test_repeated_run_does_not_duplicate_fallback_or_rotate_tips(self):
        posts = []
        builder_calls = 0

        def fallback_builder():
            nonlocal builder_calls
            builder_calls += 1
            return "Один стабильный fallback"

        schedule_morning_post(
            posts,
            date(2026, 8, 25),
            news_text=None,
            fallback_builder=fallback_builder,
        )
        added, updated = schedule_morning_post(
            posts,
            date(2026, 8, 25),
            news_text=None,
            fallback_builder=fallback_builder,
        )

        self.assertEqual((added, updated), (0, 0))
        self.assertEqual(builder_calls, 1)
        self.assertEqual(len(posts), 1)

    def test_published_morning_post_is_never_rebuilt(self):
        posts = [
            {
                "id": "2026-08-25-10",
                "publish_at": "2026-08-25T10:00:00+05:00",
                "status": "published",
                "source": "verified_fallback",
                "text": "Уже опубликовано",
            }
        ]

        added, updated = schedule_morning_post(
            posts,
            date(2026, 8, 25),
            news_text=None,
            fallback_builder=lambda: self.fail(
                "Published-пост не должен пересобираться"
            ),
        )

        self.assertEqual((added, updated), (0, 0))
        self.assertEqual(posts[0]["text"], "Уже опубликовано")

    def test_missing_external_news_still_uses_local_fallback(self):
        morning_namespace["load_json"] = lambda filename, default=None: default
        news_text = generate_morning_post()
        tips = [
            self.make_tip(1, "Brookhaven", "Локальный совет Brookhaven."),
            self.make_tip(2, "Adopt Me!", "Локальный совет Adopt Me!"),
        ]

        fallback_text = generate_morning_fallback(
            tip_selector=lambda count: tips,
        )

        self.assertIsNone(news_text)
        self.assertIn(tips[0]["text"], fallback_text)
        self.assertIn(tips[1]["text"], fallback_text)

    def test_two_tip_fallback_is_used_when_three_are_unavailable(self):
        calls = []
        tips = [
            self.make_tip(1, "Brookhaven", "Локальный совет Brookhaven."),
            self.make_tip(2, "Adopt Me!", "Локальный совет Adopt Me!"),
        ]

        def tip_selector(count):
            calls.append(count)

            if count == 3:
                raise RuntimeError("Недостаточно разных игр")

            return tips

        fallback_text = generate_morning_fallback(tip_selector=tip_selector)

        self.assertEqual(calls, [3, 2])
        self.assertIn(tips[0]["text"], fallback_text)
        self.assertIn(tips[1]["text"], fallback_text)

    def test_insufficient_tips_create_minimal_safe_post(self):
        def unavailable_tips(count):
            raise RuntimeError("Проверенных советов недостаточно")

        fallback_text = generate_morning_fallback(tip_selector=unavailable_tips)
        posts = []
        added, updated = schedule_morning_post(
            posts,
            date(2026, 8, 25),
            news_text=None,
            fallback_builder=lambda: fallback_text,
        )

        self.assertEqual((added, updated), (1, 0))
        self.assertIn(
            "Сегодня без подтверждённых игровых новостей.",
            posts[0]["text"],
        )
        self.assertIn("Следим за обновлениями", posts[0]["text"])


if __name__ == "__main__":
    unittest.main()
