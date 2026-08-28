import ast
import unittest
from pathlib import Path

from brawl_news_formatter import contains_rumor_signal, has_concrete_brawl_news

BRAWL_MONITOR_PATH = Path(__file__).parents[1] / "brawl_monitor.py"


def load_evaluate_article():
    """
    Загружает только функцию evaluate_article().

    Сам brawl_monitor.py нельзя импортировать в тесте напрямую:
    при импорте монитор сразу загружает блог и обновляет JSON-файлы.
    Извлечение функции через AST позволяет проверить реальную логику
    оценки без сетевых запросов и побочных изменений состояния.
    """

    source = BRAWL_MONITOR_PATH.read_text(encoding="utf-8")
    tree = ast.parse(source)

    evaluate_node = next(
        node
        for node in tree.body
        if isinstance(node, ast.FunctionDef) and node.name == "evaluate_article"
    )

    isolated_module = ast.Module(
        body=[evaluate_node],
        type_ignores=[],
    )
    namespace = {
        "contains_rumor_signal": contains_rumor_signal,
        "has_concrete_brawl_news": has_concrete_brawl_news,
    }

    # Выполняется только один узел функции из локального файла проекта.
    # Внешние данные и произвольный пользовательский код сюда не попадают.
    exec(  # noqa: S102
        compile(isolated_module, str(BRAWL_MONITOR_PATH), "exec"),
        namespace,
    )

    return namespace["evaluate_article"]


evaluate_article = load_evaluate_article()


class EvaluateArticlePriorityTests(unittest.TestCase):
    def test_high_priority_for_score_six_or_more(self):
        article = {
            "category": "release-notes",
            "clean_content": ["New game mode announced"],
        }

        evaluation = evaluate_article(article)

        self.assertEqual(evaluation["score"], 6)
        self.assertEqual(evaluation["priority"], "high")
        self.assertTrue(evaluation["is_relevant"])

    def test_medium_priority_for_score_from_three_to_five(self):
        article = {
            "category": "other",
            "clean_content": ["A new hypercharge is coming"],
        }

        evaluation = evaluate_article(article)

        self.assertEqual(evaluation["score"], 4)
        self.assertEqual(evaluation["priority"], "medium")
        self.assertTrue(evaluation["is_relevant"])

    def test_low_priority_for_score_below_three(self):
        article = {
            "category": "esports",
            "clean_content": [],
        }

        evaluation = evaluate_article(article)

        self.assertEqual(evaluation["score"], 2)
        self.assertEqual(evaluation["priority"], "low")
        self.assertFalse(evaluation["is_relevant"])

    def test_rumor_is_rejected_even_if_it_contains_high_priority_words(self):
        article = {
            "category": "release-notes",
            "title": "Leaked new brawler and balance changes",
            "clean_content": ["A datamine allegedly reveals a new game mode."],
        }

        evaluation = evaluate_article(article)

        self.assertFalse(evaluation["is_relevant"])
        self.assertEqual(evaluation["score"], 0)
        self.assertEqual(evaluation["rejection_reason"], "rumor_or_leak")

    def test_as_many_as_possible_is_not_a_rumor_signal(self):
        article = {
            "category": "esports",
            "title": "First Look at BSC 2027",
            "clean_content": [
                "The team will answer as many community questions as possible."
            ],
        }

        self.assertFalse(contains_rumor_signal(article))


if __name__ == "__main__":
    unittest.main()
