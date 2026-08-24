import ast
import unittest
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from tempfile import TemporaryDirectory

from image_library import select_daily_image

PROJECT_ROOT = Path(__file__).parents[1]


def load_members(file_name, function_names, constant_names):
    """
    Загружает только тестируемые части скрипта.

    generate_posts.py и app.py выполняют рабочий pipeline
    на верхнем уровне. AST позволяет проверить расписание
    без изменения posts.json и без отправки в Telegram.
    """

    path = PROJECT_ROOT / file_name
    tree = ast.parse(path.read_text(encoding="utf-8"))
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
        "datetime": datetime,
        "timedelta": timedelta,
        "timezone": timezone,
    }
    isolated_module = ast.Module(
        body=selected_nodes,
        type_ignores=[],
    )

    # Выполняются только выбранные локальные функции и константы.
    # Сетевые запросы и рабочие JSON при этом не затрагиваются.
    exec(  # noqa: S102
        compile(isolated_module, str(path), "exec"),
        namespace,
    )

    return namespace


generate_namespace = load_members(
    "generate_posts.py",
    {
        "build_post",
        "find_post",
        "schedule_image_posts",
        "schedule_brawl_post",
    },
    {
        "LOCAL_TIMEZONE",
        "IMAGE_POST_HOURS",
        "IMAGE_DIRECTORY",
        "IMAGE_HISTORY_FILE",
        "ROBLOX_NEWS_HOUR",
        "BRAWL_POST_HOUR",
        "TIPS_POST_HOUR",
        "MYTH_POST_HOUR",
    },
)

schedule_image_posts = generate_namespace["schedule_image_posts"]
schedule_brawl_post = generate_namespace["schedule_brawl_post"]

app_namespace = load_members(
    "app.py",
    {
        "is_image_post",
        "should_publish_post",
    },
    {
        "LOCAL_TIMEZONE",
        "IMAGE_PUBLISH_HOURS",
    },
)

should_publish_post = app_namespace["should_publish_post"]
local_timezone = app_namespace["LOCAL_TIMEZONE"]


class ImageScheduleTests(unittest.TestCase):
    def test_schedules_four_unique_daily_image_slots(self):
        posts = []
        images = [
            "images/16-00/first.jpg",
            "images/16-00/second.jpg",
            "images/16-00/third.jpg",
            "images/16-00/fourth.jpg",
        ]

        def fake_selector(directory, history_filename, exclude_paths):
            self.assertEqual(directory, "images/16-00")
            self.assertEqual(history_filename, "image_history.json")

            return next(
                image_path for image_path in images if image_path not in exclude_paths
            )

        added = schedule_image_posts(
            posts,
            date(2026, 8, 24),
            image_selector=fake_selector,
        )

        self.assertEqual(added, 4)
        self.assertEqual(
            [post["id"] for post in posts],
            [
                "2026-08-24-image-11",
                "2026-08-24-image-14",
                "2026-08-24-image-17",
                "2026-08-24-image-21",
            ],
        )
        self.assertEqual(
            [datetime.fromisoformat(post["publish_at"]).hour for post in posts],
            [11, 14, 17, 21],
        )
        self.assertTrue(
            all(
                datetime.fromisoformat(post["publish_at"]).utcoffset()
                == timedelta(hours=5)
                for post in posts
            )
        )
        self.assertEqual(
            len({post["image_path"] for post in posts}),
            4,
        )

    def test_only_new_image_hours_are_scheduled(self):
        self.assertEqual(generate_namespace["IMAGE_POST_HOURS"], (11, 14, 17, 21))
        self.assertNotIn(12, generate_namespace["IMAGE_POST_HOURS"])
        self.assertNotIn(22, generate_namespace["IMAGE_POST_HOURS"])
        self.assertNotIn(16, generate_namespace["IMAGE_POST_HOURS"])

    def test_repeated_generation_does_not_duplicate_image_posts(self):
        posts = []
        images = iter(
            [
                "images/16-00/first.jpg",
                "images/16-00/second.jpg",
                "images/16-00/third.jpg",
                "images/16-00/fourth.jpg",
            ]
        )

        schedule_image_posts(
            posts,
            date(2026, 8, 24),
            image_selector=lambda **kwargs: next(images),
        )

        def unexpected_selector(**kwargs):
            self.fail("Для существующих слотов selector вызываться не должен")

        added = schedule_image_posts(
            posts,
            date(2026, 8, 24),
            image_selector=unexpected_selector,
        )

        self.assertEqual(added, 0)
        self.assertEqual(len(posts), 4)

    def test_selector_cannot_repeat_one_image_inside_day(self):
        posts = []

        added = schedule_image_posts(
            posts,
            date(2026, 8, 24),
            image_selector=lambda **kwargs: "images/16-00/same.jpg",
        )

        self.assertEqual(added, 1)
        self.assertEqual(
            [post["image_path"] for post in posts],
            ["images/16-00/same.jpg"],
        )

    def test_image_posts_publish_in_each_configured_hour(self):
        for publish_hour in (11, 14, 17, 21):
            with self.subTest(publish_hour=publish_hour):
                post = {
                    "publish_at": datetime(
                        2026,
                        8,
                        24,
                        publish_hour,
                        0,
                        tzinfo=local_timezone,
                    ).isoformat(),
                    "status": "pending",
                    "image_path": "images/16-00/test.jpg",
                }
                now = datetime(
                    2026,
                    8,
                    24,
                    publish_hour,
                    30,
                    tzinfo=local_timezone,
                )

                self.assertTrue(should_publish_post(post, now))

    def test_image_post_does_not_publish_outside_its_hour(self):
        post = {
            "publish_at": "2026-08-24T11:00:00+05:00",
            "status": "pending",
            "image_path": "images/16-00/test.jpg",
        }
        outside_window = datetime(
            2026,
            8,
            24,
            16,
            0,
            tzinfo=local_timezone,
        )

        self.assertFalse(should_publish_post(post, outside_window))

    def test_old_image_hours_are_not_publishable(self):
        for old_hour in (12, 22):
            with self.subTest(old_hour=old_hour):
                post = {
                    "publish_at": datetime(
                        2026,
                        8,
                        24,
                        old_hour,
                        0,
                        tzinfo=local_timezone,
                    ).isoformat(),
                    "status": "pending",
                    "image_path": "images/16-00/legacy.jpg",
                }
                now = datetime(
                    2026,
                    8,
                    24,
                    old_hour,
                    15,
                    tzinfo=local_timezone,
                )

                self.assertFalse(should_publish_post(post, now))

    def test_published_image_does_not_publish_twice_in_same_window(self):
        post = {
            "publish_at": "2026-08-24T17:00:00+05:00",
            "status": "published",
            "image_path": "images/16-00/test.jpg",
        }
        repeated_run = datetime(
            2026,
            8,
            24,
            17,
            30,
            tzinfo=local_timezone,
        )

        self.assertFalse(should_publish_post(post, repeated_run))

    def test_published_text_post_is_not_sent_again(self):
        post = {
            "publish_at": "2026-08-24T12:00:00+05:00",
            "status": "published",
            "text": "Уже опубликованный Brawl Stars пост",
        }
        repeated_run = datetime(
            2026,
            8,
            24,
            12,
            30,
            tzinfo=local_timezone,
        )

        self.assertFalse(should_publish_post(post, repeated_run))

    def test_overdue_text_post_keeps_existing_behavior(self):
        post = {
            "publish_at": "2026-08-24T10:00:00+05:00",
            "status": "pending",
            "text": "Обычный текстовый пост",
        }
        later_run = datetime(
            2026,
            8,
            24,
            16,
            0,
            tzinfo=local_timezone,
        )

        self.assertTrue(should_publish_post(post, later_run))

    def test_image_library_excludes_images_already_used_today(self):
        with TemporaryDirectory() as temporary_directory:
            directory = Path(temporary_directory)
            history_filename = directory / "history.json"

            for index in range(4):
                (directory / f"image-{index}.jpg").touch()

            selected_images = []

            for _ in range(4):
                image_path = select_daily_image(
                    directory=directory,
                    history_filename=history_filename,
                    exclude_paths=selected_images,
                )
                selected_images.append(image_path)

            no_repeated_image = select_daily_image(
                directory=directory,
                history_filename=history_filename,
                exclude_paths=selected_images,
            )

            self.assertEqual(len(set(selected_images)), 4)
            self.assertIsNone(no_repeated_image)

    def test_text_schedule_uses_required_daily_hours(self):
        self.assertEqual(generate_namespace["ROBLOX_NEWS_HOUR"], 10)
        self.assertEqual(generate_namespace["BRAWL_POST_HOUR"], 12)
        self.assertEqual(generate_namespace["TIPS_POST_HOUR"], 15)
        self.assertEqual(generate_namespace["MYTH_POST_HOUR"], 19)

        for publish_hour in (10, 12, 15, 19):
            with self.subTest(publish_hour=publish_hour):
                post = {
                    "publish_at": datetime(
                        2026,
                        8,
                        24,
                        publish_hour,
                        0,
                        tzinfo=local_timezone,
                    ).isoformat(),
                    "status": "pending",
                    "text": "Текстовый пост",
                }
                now = datetime(
                    2026,
                    8,
                    24,
                    publish_hour,
                    5,
                    tzinfo=local_timezone,
                )

                self.assertTrue(should_publish_post(post, now))

    def test_complete_schedule_has_expected_order(self):
        text_hours = (
            generate_namespace["ROBLOX_NEWS_HOUR"],
            generate_namespace["BRAWL_POST_HOUR"],
            generate_namespace["TIPS_POST_HOUR"],
            generate_namespace["MYTH_POST_HOUR"],
        )
        all_hours = sorted(
            text_hours + generate_namespace["IMAGE_POST_HOURS"],
        )

        self.assertEqual(all_hours, [10, 11, 12, 14, 15, 17, 19, 21])

    def test_brawl_post_is_scheduled_at_twelve(self):
        posts = []

        added = schedule_brawl_post(
            posts,
            date(2026, 8, 24),
            data_loader=lambda: {"prepared": True},
            final_post_builder=lambda data: "Готовый Brawl Stars пост",
        )

        self.assertEqual(added, 1)
        self.assertEqual(len(posts), 1)
        self.assertEqual(posts[0]["id"], "2026-08-24-brawl-12")
        self.assertEqual(posts[0]["source"], "brawl_pipeline")
        self.assertEqual(posts[0]["status"], "pending")
        self.assertEqual(
            datetime.fromisoformat(posts[0]["publish_at"]).hour,
            12,
        )

    def test_brawl_schedule_uses_real_final_post_builder(self):
        article = {
            "priority": "medium",
            "ru_found": True,
            "ru_title": "НОВОСТЬ BRAWL STARS",
            "ru_clean_content": [
                "Официальный русский абзац содержит все важные подробности."
            ],
        }
        brawl_data = {
            "high_priority_articles": [],
            "medium_priority_articles": [article],
            "new_buffs": [],
            "new_nerfs": [],
        }
        posts = []

        added = schedule_brawl_post(
            posts,
            date(2026, 8, 24),
            data_loader=lambda: brawl_data,
        )

        self.assertEqual(added, 1)
        self.assertIn("💥 BRAWL STARS | ROBLOX HUB", posts[0]["text"])
        self.assertIn("Официальный русский абзац", posts[0]["text"])

    def test_brawl_none_does_not_create_slot(self):
        posts = []

        added = schedule_brawl_post(
            posts,
            date(2026, 8, 24),
            data_loader=dict,
            final_post_builder=lambda data: None,
        )

        self.assertEqual(added, 0)
        self.assertEqual(posts, [])

    def test_repeated_generation_does_not_duplicate_brawl_post(self):
        posts = []
        target_date = date(2026, 8, 24)

        schedule_brawl_post(
            posts,
            target_date,
            data_loader=dict,
            final_post_builder=lambda data: "Готовый Brawl Stars пост",
        )

        def unexpected_builder(data):
            self.fail("Для существующего Brawl ID генератор вызываться не должен")

        added = schedule_brawl_post(
            posts,
            target_date,
            data_loader=dict,
            final_post_builder=unexpected_builder,
        )

        self.assertEqual(added, 0)
        self.assertEqual(len(posts), 1)

    def test_published_brawl_post_is_not_created_again(self):
        posts = [
            {
                "id": "2026-08-24-brawl-12",
                "publish_at": "2026-08-24T12:00:00+05:00",
                "status": "published",
                "text": "Уже опубликовано",
            }
        ]

        added = schedule_brawl_post(
            posts,
            date(2026, 8, 24),
            data_loader=lambda: self.fail("JSON не должен читаться повторно"),
            final_post_builder=lambda data: self.fail(
                "Опубликованный Brawl не должен пересобираться"
            ),
        )

        self.assertEqual(added, 0)
        self.assertEqual(len(posts), 1)

    def test_existing_legacy_text_at_twelve_is_preserved(self):
        legacy_post = {
            "id": "2026-08-24-12",
            "publish_at": "2026-08-24T12:00:00+05:00",
            "status": "pending",
            "text": "Существующая публикация",
        }
        posts = [legacy_post.copy()]

        added = schedule_brawl_post(
            posts,
            date(2026, 8, 24),
            data_loader=dict,
            final_post_builder=lambda data: "Новый Brawl-пост",
        )

        self.assertEqual(added, 0)
        self.assertEqual(posts, [legacy_post])

    def test_brawl_failure_does_not_change_other_posts(self):
        existing_post = {
            "id": "2026-08-24-10",
            "publish_at": "2026-08-24T10:00:00+05:00",
            "status": "pending",
            "text": "Roblox новости",
        }
        posts = [existing_post.copy()]

        def broken_loader():
            raise ValueError("Повреждённый Brawl JSON")

        added = schedule_brawl_post(
            posts,
            date(2026, 8, 24),
            data_loader=broken_loader,
            final_post_builder=lambda data: "Не будет вызван",
        )

        self.assertEqual(added, 0)
        self.assertEqual(posts, [existing_post])

    def test_workflows_run_preparation_and_all_publish_slots(self):
        autopost_workflow = (PROJECT_ROOT / ".github/workflows/autopost.yml").read_text(
            encoding="utf-8"
        )
        prepare_workflow = (
            PROJECT_ROOT / ".github/workflows/prepare-daily.yml"
        ).read_text(encoding="utf-8")
        prepare_script = (PROJECT_ROOT / "prepare_daily_posts.py").read_text(
            encoding="utf-8"
        )

        # UTC cron сохраняет локальную timezone UTC+5:
        # 05, 06, 07, 09, 10, 12, 14 и 16 UTC соответствуют
        # 10, 11, 12, 14, 15, 17, 19 и 21 часам проекта.
        self.assertIn('cron: "0 5,6,7,9,10,12,14,16 * * *"', autopost_workflow)
        self.assertIn('cron: "0 4 * * *"', prepare_workflow)
        self.assertIn("group: roblox-hub-autopost", autopost_workflow)
        self.assertIn('"brawl_monitor.py"', prepare_script)
        self.assertIn("ROBLOX_HUB_SKIP_BRAWL", prepare_script)
        self.assertIn("data/brawl_latest_changes.json", prepare_workflow)
        self.assertIn("data/brawl_monitor_state.json", prepare_workflow)


if __name__ == "__main__":
    unittest.main()
