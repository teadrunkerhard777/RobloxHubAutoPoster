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
    },
    {
        "LOCAL_TIMEZONE",
        "IMAGE_POST_HOURS",
        "IMAGE_DIRECTORY",
        "IMAGE_HISTORY_FILE",
    },
)

schedule_image_posts = generate_namespace["schedule_image_posts"]

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
    def test_schedules_three_unique_daily_image_slots(self):
        posts = []
        images = [
            "images/16-00/first.jpg",
            "images/16-00/second.jpg",
            "images/16-00/third.jpg",
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

        self.assertEqual(added, 3)
        self.assertEqual(
            [post["id"] for post in posts],
            [
                "2026-08-24-image-12",
                "2026-08-24-image-17",
                "2026-08-24-image-22",
            ],
        )
        self.assertEqual(
            [datetime.fromisoformat(post["publish_at"]).hour for post in posts],
            [12, 17, 22],
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
            3,
        )

    def test_old_sixteen_hour_slot_is_not_scheduled(self):
        self.assertEqual(generate_namespace["IMAGE_POST_HOURS"], (12, 17, 22))
        self.assertNotIn(16, generate_namespace["IMAGE_POST_HOURS"])

    def test_repeated_generation_does_not_duplicate_image_posts(self):
        posts = []
        images = iter(
            [
                "images/16-00/first.jpg",
                "images/16-00/second.jpg",
                "images/16-00/third.jpg",
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
        self.assertEqual(len(posts), 3)

    def test_image_posts_publish_in_each_configured_hour(self):
        for publish_hour in (12, 17, 22):
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
            "publish_at": "2026-08-24T12:00:00+05:00",
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

            for index in range(3):
                (directory / f"image-{index}.jpg").touch()

            selected_images = []

            for _ in range(3):
                image_path = select_daily_image(
                    directory=directory,
                    history_filename=history_filename,
                    exclude_paths=selected_images,
                )
                selected_images.append(image_path)

            no_fourth_image = select_daily_image(
                directory=directory,
                history_filename=history_filename,
                exclude_paths=selected_images,
            )

            self.assertEqual(len(set(selected_images)), 3)
            self.assertIsNone(no_fourth_image)

    def test_workflows_run_preparation_and_all_publish_slots(self):
        autopost_workflow = (PROJECT_ROOT / ".github/workflows/autopost.yml").read_text(
            encoding="utf-8"
        )
        prepare_workflow = (
            PROJECT_ROOT / ".github/workflows/prepare-daily.yml"
        ).read_text(encoding="utf-8")

        # UTC cron сохраняет локальную timezone UTC+5:
        # 05, 07, 10, 12, 13 и 17 UTC соответствуют
        # 10, 12, 15, 17, 18 и 22 часам проекта.
        self.assertIn('cron: "0 5,7,10,12,13,17 * * *"', autopost_workflow)
        self.assertIn('cron: "0 4 * * *"', prepare_workflow)
        self.assertIn("group: roblox-hub-autopost", autopost_workflow)


if __name__ == "__main__":
    unittest.main()
