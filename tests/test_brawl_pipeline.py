import ast
import re
import unittest
from contextlib import redirect_stdout
from difflib import SequenceMatcher
from io import StringIO
from pathlib import Path
from types import SimpleNamespace

from bs4 import BeautifulSoup
from colorama import Fore, Style

PROJECT_ROOT = Path(__file__).parents[1]


def load_members(file_name, function_names, constant_names=()):
    """
    Загружает выбранные функции и константы
    без запуска всего скрипта.

    Brawl-скрипты выполняют pipeline на верхнем уровне:
    читают JSON, обращаются к сети и печатают результат.
    Извлечение нужных узлов через AST позволяет
    проверить их без этих побочных действий.
    """

    path = PROJECT_ROOT / file_name
    source = path.read_text(encoding="utf-8")
    tree = ast.parse(source)
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

    # re и SequenceMatcher используются функциями сопоставления.
    # Передаём их явно, не выполняя все импорты рабочего скрипта.
    namespace = {
        "Fore": Fore,
        "re": re,
        "SequenceMatcher": SequenceMatcher,
        "Style": Style,
    }
    isolated_module = ast.Module(
        body=selected_nodes,
        type_ignores=[],
    )

    # Выполняются только выбранные узлы локального файла проекта.
    # Внешние данные и произвольный пользовательский код не используются.
    exec(  # noqa: S102
        compile(isolated_module, str(path), "exec"),
        namespace,
    )

    return namespace


def load_function(file_name, function_name):
    """Возвращает одну изолированно загруженную функцию."""

    namespace = load_members(
        file_name,
        {function_name},
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

print_russian_article_status = load_function(
    "brawl_post.py",
    "print_russian_article_status",
)

russian_matching_namespace = load_members(
    "brawl_monitor.py",
    {
        "normalize_article_title",
        "find_russian_article",
        "enrich_articles_with_russian_versions",
    },
    {
        "RU_TITLE_MATCH_THRESHOLD",
        "RU_TITLE_MATCH_MARGIN",
    },
)

find_russian_article = russian_matching_namespace["find_russian_article"]
enrich_articles_with_russian_versions = russian_matching_namespace[
    "enrich_articles_with_russian_versions"
]

russian_archive_namespace = load_members(
    "brawl_monitor.py",
    {
        "get_article_category",
        "fetch_russian_articles",
    },
    {
        "BASE_URL",
        "RU_BLOG_URL",
    },
)

fetch_russian_articles = russian_archive_namespace["fetch_russian_articles"]


class BrawlPipelineTests(unittest.TestCase):
    def test_collects_russian_articles_and_skips_pagination_and_duplicates(self):
        html = """
        <html>
          <a href="/en/games/brawlstars/ru/blog/release-notes/test-ru/">
            Русская статья
          </a>
          <a href="/en/games/brawlstars/ru/blog/release-notes/test-ru/">
            Русская статья
          </a>
          <a href="/en/games/brawlstars/ru/blog/page/2/">2</a>
        </html>
        """

        def fake_get(url, timeout):
            self.assertEqual(url, russian_archive_namespace["RU_BLOG_URL"])
            self.assertEqual(timeout, 15)

            return SimpleNamespace(
                status_code=200,
                content=html.encode("utf-8"),
            )

        russian_archive_namespace["requests"] = SimpleNamespace(get=fake_get)
        russian_archive_namespace["BeautifulSoup"] = BeautifulSoup

        articles = fetch_russian_articles()

        self.assertEqual(
            articles,
            [
                {
                    "title": "Русская статья",
                    "url": (
                        "https://supercell.com/en/games/brawlstars/"
                        "ru/blog/release-notes/test-ru/"
                    ),
                    "category": "release-notes",
                }
            ],
        )

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

    def test_old_candidate_without_russian_fields_is_supported(self):
        old_article = {
            "title": "Old article",
            "category": "community",
            "score": 3,
        }
        old_data = {
            "high_priority_articles": [old_article],
            "medium_priority_articles": [],
        }

        high_articles, _ = get_news_candidates(old_data)
        output = StringIO()

        with redirect_stdout(output):
            print_russian_article_status(high_articles[0])

        self.assertIn("Русская версия пока не найдена", output.getvalue())

    def test_matches_similar_russian_article_in_same_category(self):
        article = {
            "title": "Brawl Stars Championship 2026 Format",
            "category": "esports",
        }
        russian_article = {
            "title": "Brawl Stars Championship 2026: формат",
            "url": "https://example.com/ru/championship-2026",
            "category": "esports",
        }

        match = find_russian_article(
            article,
            [russian_article],
        )

        self.assertEqual(match, russian_article)

    def test_does_not_match_article_from_other_category(self):
        article = {
            "title": "Brawl Stars Championship 2026 Format",
            "category": "esports",
        }
        russian_article = {
            "title": "Brawl Stars Championship 2026 Format",
            "url": "https://example.com/ru/championship-2026",
            "category": "release-notes",
        }

        match = find_russian_article(
            article,
            [russian_article],
        )

        self.assertIsNone(match)

    def test_low_similarity_does_not_create_false_match(self):
        article = {
            "title": "New Brawler and Hypercharge Guide",
            "category": "release-notes",
        }
        russian_article = {
            "title": "Формат мирового финала 2026",
            "url": "https://example.com/ru/world-finals",
            "category": "release-notes",
        }

        match = find_russian_article(
            article,
            [russian_article],
        )

        self.assertIsNone(match)

    def test_missing_russian_article_adds_not_found_fields(self):
        article = {
            "title": "New Brawler Guide",
            "category": "release-notes",
        }

        enriched = enrich_articles_with_russian_versions(
            [article],
            [],
        )

        self.assertFalse(enriched[0]["ru_found"])
        self.assertIsNone(enriched[0]["ru_title"])
        self.assertIsNone(enriched[0]["ru_url"])

    def test_found_russian_article_adds_url_title_and_content(self):
        article = {
            "title": "Brawl Stars Championship 2026 Format",
            "category": "esports",
        }
        russian_article = {
            "title": "Brawl Stars Championship 2026: формат",
            "url": "https://example.com/ru/championship-2026",
            "category": "esports",
        }

        # Сетевую загрузку заменяем локальными данными.
        # Так тест проверяет pipeline без внешнего запроса.
        russian_matching_namespace["fetch_article_text"] = lambda url: [
            russian_article["title"],
            "Русский текст статьи",
        ]
        russian_matching_namespace["clean_article_content"] = lambda content, title: [
            text for text in content if text != title
        ]

        enriched = enrich_articles_with_russian_versions(
            [article],
            [russian_article],
        )

        self.assertTrue(enriched[0]["ru_found"])
        self.assertEqual(enriched[0]["ru_title"], russian_article["title"])
        self.assertEqual(enriched[0]["ru_url"], russian_article["url"])
        self.assertEqual(enriched[0]["ru_clean_content"], ["Русский текст статьи"])

    def test_low_article_does_not_require_russian_search(self):
        low_article = {
            "title": "Low",
            "priority": "low",
        }

        high_articles, medium_articles = split_articles_by_priority([low_article])

        self.assertEqual(high_articles, [])
        self.assertEqual(medium_articles, [])
        self.assertNotIn("ru_found", low_article)


if __name__ == "__main__":
    unittest.main()
