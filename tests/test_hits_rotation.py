import ast
import json
import random
import unittest
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

from post_hashtags import add_post_hashtags
from post_headings import HITS_HEADING
from tips_rotation import (
    CURRENT_HIT_GAMES,
    HITS_WATCHLIST,
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
    constant_names = {
        "LOCAL_TIMEZONE",
        "HITS_POST_HOUR",
        "GAME_EMOJIS",
        "HITS_GAME_DESCRIPTIONS",
    }
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

    def test_requested_games_are_in_pool_and_existing_games_remain(self):
        requested_games = {
            "Steal An Egg",
            "Forsaken",
            "Dungeon Quest Reborn",
            "Cheating During Testing [BETA]",
            "Grand Blue [Early Access]",
            "Carve Wood!",
        }
        existing_games = {
            "Steal An Egg",
            "Animal Hospital (Anomaly)",
            "+1 Speed Keyboard Escape",
            "Murder Mystery 2",
        }

        self.assertTrue(requested_games.issubset(CURRENT_HIT_GAMES))
        self.assertTrue(existing_games.issubset(CURRENT_HIT_GAMES))

    def test_each_requested_game_has_description_and_three_editorial_blocks(self):
        requested_games = {
            "Steal An Egg",
            "Forsaken",
            "Dungeon Quest Reborn",
            "Cheating During Testing [BETA]",
            "Grand Blue [Early Access]",
            "Carve Wood!",
        }

        for game in requested_games:
            selected = choose_tips_for_game(
                json.loads(json.dumps(self.tips, ensure_ascii=False)),
                game,
                count=3,
                rng=random.Random(1),
            )
            self.assertEqual(len(selected), 3)
            self.assertTrue(all(tip.get("hits_featured") for tip in selected))
            _, text = build_hits_post(
                game,
                SCHEDULE["HITS_GAME_DESCRIPTIONS"][game],
                selected,
                SCHEDULE["GAME_EMOJIS"],
            )
            self.assertIn("🎮 Что за игра?", text)
            self.assertTrue(text.startswith(f"{HITS_HEADING}\n\n"))
            for tip in selected:
                self.assertEqual(text.count(tip["text"]), 1)

    def test_watchlist_is_not_part_of_publication_pool(self):
        self.assertTrue(HITS_WATCHLIST)
        self.assertTrue(set(HITS_WATCHLIST).isdisjoint(CURRENT_HIT_GAMES))

    def test_myth_generator_is_no_longer_scheduled(self):
        source = (PROJECT_ROOT / "generate_posts.py").read_text(encoding="utf-8")
        self.assertNotIn("def generate_myth_post", source)
        self.assertNotIn('rubric="Миф или правда"', source)

    def test_games_rotate_without_adjacent_repeat(self):
        history = []
        first_cycle = []
        for _ in CURRENT_HIT_GAMES:
            game = choose_hit_game(
                recent_games=history, rng=random.Random(len(history))
            )
            self.assertNotIn(game, history)
            first_cycle.append(game)
            history.append(game)

        self.assertEqual(set(first_cycle), set(CURRENT_HIT_GAMES))
        next_game = choose_hit_game(recent_games=history)
        self.assertNotEqual(next_game, history[-1])

    def test_current_post_history_selects_forsaken_next(self):
        posts = json.loads((PROJECT_ROOT / "posts.json").read_text(encoding="utf-8"))
        history = [
            post["game"]
            for post in sorted(posts, key=lambda post: post.get("publish_at", ""))
            if post.get("rubric") == "Новинки и хиты Roblox"
            and post.get("game") in CURRENT_HIT_GAMES
        ][-8:]

        self.assertEqual(choose_hit_game(recent_games=history), "Forsaken")

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
        self.assertTrue(text.startswith(f"{HITS_HEADING}\n\n"))
        self.assertIn("🎮 Что за игра?", text)
        self.assertTrue(text.endswith("🎮 Roblox Hub"))

    def test_tip_does_not_repeat_before_game_pool_is_exhausted(self):
        tips = json.loads(json.dumps(self.tips, ensure_ascii=False))
        game = CURRENT_HIT_GAMES[1]
        for tip in tips:
            if tip["game"] == game:
                tip["used"] = False
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
