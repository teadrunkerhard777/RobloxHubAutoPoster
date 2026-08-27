import ast
import json
import random
import unittest
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

from post_hashtags import add_post_hashtags
from tips_rotation import (
    CURRENT_HIT_GAMES,
    build_hits_post,
    choose_hit_game,
    choose_tips_for_game,
)

PROJECT_ROOT = Path(__file__).parents[1]


def load_schedule_members():
    path = PROJECT_ROOT / "generate_posts.py"
    tree = ast.parse(path.read_text(encoding="utf-8"))
    function_names = {
        "build_post",
        "find_post",
        "remove_pending_legacy_myth",
        "schedule_hits_post",
    }
    constant_names = {"LOCAL_TIMEZONE", "HITS_POST_HOUR"}
    nodes = []

    for node in tree.body:
        if isinstance(node, ast.FunctionDef) and node.name in function_names:
            nodes.append(node)
        elif isinstance(node, ast.Assign):
            names = {
                target.id for target in node.targets if isinstance(target, ast.Name)
            }
            if names & constant_names:
                nodes.append(node)

    namespace = {
        "add_post_hashtags": add_post_hashtags,
        "datetime": datetime,
        "timedelta": timedelta,
        "timezone": timezone,
    }
    exec(  # noqa: S102
        compile(ast.Module(body=nodes, type_ignores=[]), str(path), "exec"),
        namespace,
    )
    return namespace


SCHEDULE = load_schedule_members()


class HitsRotationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tips = json.loads((PROJECT_ROOT / "tips.json").read_text(encoding="utf-8"))

    def test_myth_generator_is_no_longer_scheduled(self):
        source = (PROJECT_ROOT / "generate_posts.py").read_text(encoding="utf-8")
        self.assertNotIn("def generate_myth_post", source)
        self.assertNotIn('rubric="Миф или правда"', source)

    def test_games_rotate_without_adjacent_repeat(self):
        history = []
        for _ in range(20):
            game = choose_hit_game(
                recent_games=history, rng=random.Random(len(history))
            )
            if history:
                self.assertNotEqual(game, history[-1])
            history.append(game)

    def test_post_contains_three_distinct_tips_from_selected_game(self):
        tips = json.loads(json.dumps(self.tips, ensure_ascii=False))
        game = CURRENT_HIT_GAMES[0]
        selected = choose_tips_for_game(tips, game, count=3, rng=random.Random(4))
        _, text = build_hits_post(
            game,
            "Короткое описание механики.",
            selected,
            {game: "🥚"},
        )

        self.assertEqual(len(selected), 3)
        self.assertEqual(len({tip["id"] for tip in selected}), 3)
        self.assertTrue(all(tip["game"] == game for tip in selected))
        self.assertTrue(text.startswith("🔥 НОВИНКИ И ХИТЫ ROBLOX"))
        self.assertIn("🎮 Что за игра?", text)
        self.assertTrue(text.endswith("🎮 Roblox Hub"))

    def test_tip_does_not_repeat_before_game_pool_is_exhausted(self):
        tips = json.loads(json.dumps(self.tips, ensure_ascii=False))
        game = CURRENT_HIT_GAMES[1]
        releases = [
            choose_tips_for_game(tips, game, count=3, rng=random.Random(seed))
            for seed in range(4)
        ]
        ids = [tip["id"] for release in releases for tip in release]
        self.assertEqual(len(ids), len(set(ids)))

    def test_schedule_creates_one_hits_post_and_is_idempotent(self):
        posts = []
        target = date(2026, 8, 28)

        def generator():
            return CURRENT_HIT_GAMES[0], "🔥 НОВИНКИ И ХИТЫ ROBLOX\n\nТест"

        first = SCHEDULE["schedule_hits_post"](posts, target, generator)
        second = SCHEDULE["schedule_hits_post"](posts, target, generator)

        self.assertEqual((first, second), (1, 0))
        self.assertEqual(len(posts), 1)
        self.assertEqual(posts[0]["rubric"], "Новинки и хиты Roblox")
        self.assertEqual(datetime.fromisoformat(posts[0]["publish_at"]).hour, 19)
        self.assertTrue(posts[0]["text"].endswith("#Roblox #StealAnEgg #НовинкиRoblox"))

    def test_pending_current_myth_is_replaced_without_duplicate(self):
        target = date(2026, 8, 28)
        posts = [
            {
                "id": "2026-08-28-19",
                "publish_at": "2026-08-28T19:00:00+05:00",
                "rubric": "Миф или правда",
                "status": "pending",
            }
        ]

        added = SCHEDULE["schedule_hits_post"](
            posts,
            target,
            lambda: (CURRENT_HIT_GAMES[2], "🔥 НОВИНКИ И ХИТЫ ROBLOX"),
        )

        self.assertEqual(added, 1)
        self.assertEqual(len(posts), 1)
        self.assertEqual(posts[0]["rubric"], "Новинки и хиты Roblox")
        self.assertNotIn("Миф или правда", {post["rubric"] for post in posts})

    def test_published_legacy_myth_is_not_changed(self):
        target = date(2026, 8, 28)
        published = {
            "id": "2026-08-28-19",
            "publish_at": "2026-08-28T19:00:00+05:00",
            "rubric": "Миф или правда",
            "status": "published",
            "text": "Архивный опубликованный текст",
        }
        posts = [dict(published)]

        added = SCHEDULE["schedule_hits_post"](
            posts,
            target,
            lambda: (CURRENT_HIT_GAMES[0], "Не должен использоваться"),
        )

        self.assertEqual(added, 0)
        self.assertEqual(posts, [published])


if __name__ == "__main__":
    unittest.main()
