import ast
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).parents[1]


def load_function(file_name, function_name):
    """
    Загружает одну функцию без запуска всего скрипта.

    Brawl-скрипты выполняют pipeline на верхнем уровне:
    читают JSON, обращаются к сети и печатают результат.
    Извлечение конкретной функции через AST позволяет
    проверить её без этих побочных действий.
    """

    path = PROJECT_ROOT / file_name
    source = path.read_text(encoding="utf-8")
    tree = ast.parse(source)

    function_node = next(
        node
        for node in tree.body
        if isinstance(node, ast.FunctionDef) and node.name == function_name
    )

    isolated_module = ast.Module(
        body=[function_node],
        type_ignores=[],
    )
    namespace = {}

    # Выполняется только выбранная функция из локального файла проекта.
    # Внешние данные и произвольный пользовательский код не используются.
    exec(  # noqa: S102
        compile(isolated_module, str(path), "exec"),
        namespace,
    )

    return namespace[function_name]


split_articles_by_priority = load_function(
    "brawl_monitor.py",
    "split_articles_by_priority",
)

get_news_candidates = load_function(
    "brawl_post.py",
    "get_news_candidates",
)


class BrawlPipelineTests(unittest.TestCase):
    def test_splits_high_medium_and_ignores_low(self):
        high_article = {"title": "High", "priority": "high"}
        medium_article = {"title": "Medium", "priority": "medium"}
        low_article = {"title": "Low", "priority": "low"}

        high_articles, medium_articles = split_articles_by_priority(
            [high_article, medium_article, low_article]
        )

        self.assertEqual(high_articles, [high_article])
        self.assertEqual(medium_articles, [medium_article])
        self.assertNotIn(low_article, high_articles)
        self.assertNotIn(low_article, medium_articles)

    def test_post_generator_reads_news_candidate_fields(self):
        high_article = {"title": "High", "priority": "high"}
        medium_article = {"title": "Medium", "priority": "medium"}
        data = {
            "high_priority_articles": [high_article],
            "medium_priority_articles": [medium_article],
        }

        high_articles, medium_articles = get_news_candidates(data)

        self.assertEqual(high_articles, [high_article])
        self.assertEqual(medium_articles, [medium_article])

    def test_old_json_without_candidate_fields_is_supported(self):
        old_data = {
            "new_buffs": [],
            "new_nerfs": [],
            "new_articles": [],
        }

        high_articles, medium_articles = get_news_candidates(old_data)

        self.assertEqual(high_articles, [])
        self.assertEqual(medium_articles, [])


if __name__ == "__main__":
    unittest.main()
