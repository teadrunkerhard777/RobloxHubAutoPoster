import ast
import unittest
from datetime import date
from pathlib import Path

VERIFY_NEWS_PATH = Path(__file__).parents[1] / "verify_news.py"


def load_article_used_on_another_day():
    tree = ast.parse(VERIFY_NEWS_PATH.read_text(encoding="utf-8"))
    node = next(
        item
        for item in tree.body
        if isinstance(item, ast.FunctionDef)
        and item.name == "article_used_on_another_day"
    )
    namespace = {}
    exec(  # noqa: S102
        compile(
            ast.Module(body=[node], type_ignores=[]), str(VERIFY_NEWS_PATH), "exec"
        ),
        namespace,
    )
    return namespace["article_used_on_another_day"]


article_used_on_another_day = load_article_used_on_another_day()


class NewsHistoryTests(unittest.TestCase):
    def test_article_used_on_previous_day_is_not_repeated(self):
        url = "https://official.example/update"
        history = [
            {
                "url": url,
                "selected_date": "2026-08-26",
            }
        ]

        self.assertTrue(
            article_used_on_another_day(
                url,
                history,
                date(2026, 8, 27),
            )
        )

    def test_same_day_retry_is_allowed(self):
        url = "https://official.example/update"
        history = [
            {
                "url": url,
                "selected_date": "2026-08-27",
            }
        ]

        self.assertFalse(
            article_used_on_another_day(
                url,
                history,
                date(2026, 8, 27),
            )
        )


if __name__ == "__main__":
    unittest.main()
