import ast
import re
import unittest
from contextlib import redirect_stdout
from datetime import date
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
        "date": date,
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
        "normalize_article_date",
        "normalize_article_title",
        "find_article_by_title_similarity",
        "print_russian_match_debug",
        "find_russian_article",
        "enrich_articles_with_russian_versions",
    },
    {
        "ARTICLE_MONTHS",
        "DEBUG_RU_MATCHING",
        "RU_TITLE_MATCH_THRESHOLD",
        "RU_TITLE_MATCH_MARGIN",
    },
)

find_russian_article = russian_matching_namespace["find_russian_article"]
normalize_article_date = russian_matching_namespace["normalize_article_date"]
enrich_articles_with_russian_versions = russian_matching_namespace[
    "enrich_articles_with_russian_versions"
]

russian_archive_namespace = load_members(
    "brawl_monitor.py",
    {
        "get_article_category",
        "normalize_article_date",
        "extract_archive_article_date",
        "fetch_russian_articles",
    },
    {
        "ARTICLE_MONTHS",
        "BASE_URL",
        "RU_BLOG_URL",
    },
)

fetch_russian_articles = russian_archive_namespace["fetch_russian_articles"]

russian_preview_namespace = load_members(
    "brawl_post.py",
    {
        "select_news_content",
        "build_article_news_preview",
        "print_generation_result",
    },
    {
        "NEWS_MAX_BLOCKS",
        "NEWS_MAX_CHARS",
        "NEWS_MIN_BLOCK_LENGTH",
        "NEWS_SHORT_HEADING_MAX_CHARS",
        "NEWS_DAY_STAGE_PATTERN",
        "NEWS_SERVICE_PREFIXES",
    },
)

select_news_content = russian_preview_namespace["select_news_content"]
build_article_news_preview = russian_preview_namespace["build_article_news_preview"]
print_generation_result = russian_preview_namespace["print_generation_result"]


class BrawlPipelineTests(unittest.TestCase):
    def test_collects_russian_articles_and_skips_pagination_and_duplicates(self):
        html = """
        <html>
          <div data-test-class="archived-article">
            <p data-test-id="publish-date-text">3 авг. 2026 г.</p>
            <a href="/en/games/brawlstars/ru/blog/release-notes/test-ru/">
              Русская статья
            </a>
            <a href="/en/games/brawlstars/ru/blog/release-notes/test-ru/">
              Русская статья
            </a>
          </div>
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
                    "date": "2026-08-03",
                    "archive_index": 0,
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

    def test_matches_different_titles_by_category_and_date(self):
        article = {
            "title": "Release Notes June 2026",
            "category": "release-notes",
            "date": "2026-08-03",
        }
        russian_article = {
            "title": "Информация о версии: июнь 2026 г.",
            "url": "https://example.com/ru/release-notes-june",
            "category": "release-notes",
            "date": "2026-08-03",
        }

        match = find_russian_article(
            article,
            [russian_article],
        )

        self.assertEqual(match, russian_article)

    def test_same_category_with_different_dates_does_not_match(self):
        article = {
            "title": "Identical Release Notes Title",
            "category": "release-notes",
            "date": "2026-08-03",
        }
        russian_article = {
            "title": "Identical Release Notes Title",
            "url": "https://example.com/ru/other-date",
            "category": "release-notes",
            "date": "2026-08-04",
        }

        match = find_russian_article(
            article,
            [russian_article],
        )

        self.assertIsNone(match)

    def test_same_date_with_different_category_does_not_match(self):
        article = {
            "title": "Release Notes June 2026",
            "category": "release-notes",
            "date": "2026-08-03",
        }
        russian_article = {
            "title": "Release Notes June 2026",
            "url": "https://example.com/ru/esports",
            "category": "esports",
            "date": "2026-08-03",
        }

        match = find_russian_article(
            article,
            [russian_article],
        )

        self.assertIsNone(match)

    def test_missing_date_uses_title_similarity_fallback(self):
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

    def test_multiple_articles_on_same_date_remain_ambiguous(self):
        article = {
            "title": "English release article",
            "category": "release-notes",
            "date": "2026-08-03",
        }
        russian_articles = [
            {
                "title": "Первая русская статья",
                "url": "https://example.com/ru/first",
                "category": "release-notes",
                "date": "2026-08-03",
                "archive_index": 0,
            },
            {
                "title": "Вторая русская статья",
                "url": "https://example.com/ru/second",
                "category": "release-notes",
                "date": "2026-08-03",
                "archive_index": 1,
            },
        ]

        match = find_russian_article(
            article,
            russian_articles,
        )

        self.assertIsNone(match)

    def test_archive_index_resolves_same_date_tie(self):
        article = {
            "title": "English release article",
            "category": "release-notes",
            "date": "2026-08-03",
            "archive_index": 1,
        }
        expected_article = {
            "title": "Вторая русская статья",
            "url": "https://example.com/ru/second",
            "category": "release-notes",
            "date": "2026-08-03",
            "archive_index": 1,
        }
        russian_articles = [
            {
                "title": "Первая русская статья",
                "url": "https://example.com/ru/first",
                "category": "release-notes",
                "date": "2026-08-03",
                "archive_index": 0,
            },
            expected_article,
        ]

        match = find_russian_article(
            article,
            russian_articles,
        )

        self.assertEqual(match, expected_article)

    def test_unrecognized_article_date_returns_none(self):
        self.assertIsNone(normalize_article_date("когда-нибудь в августе"))
        self.assertIsNone(normalize_article_date("2026-02-31"))

    def test_normalizes_russian_month_names(self):
        date_variants = (
            "3 авг. 2026 г.",
            "3 августа 2026 г.",
        )

        for date_text in date_variants:
            with self.subTest(date_text=date_text):
                self.assertEqual(
                    normalize_article_date(date_text),
                    "2026-08-03",
                )

    def test_normalizes_english_article_dates(self):
        date_variants = (
            "Aug 3, 2026",
            "August 3, 2026",
            "3 Aug 2026",
        )

        for date_text in date_variants:
            with self.subTest(date_text=date_text):
                self.assertEqual(
                    normalize_article_date(date_text),
                    "2026-08-03",
                )

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

    def test_high_article_with_russian_content_builds_preview(self):
        official_text = "Событие начнётся 24 августа 2026 года и принесёт 10 наград."
        article = {
            "priority": "high",
            "ru_found": True,
            "ru_title": "Новое событие Brawl Stars",
            "ru_clean_content": [official_text],
        }

        preview = build_article_news_preview(article)

        self.assertIsNotNone(preview)
        self.assertIn("🔥 HIGH", preview)
        self.assertIn(article["ru_title"], preview)
        self.assertIn(official_text, preview)
        self.assertIn("Источник: Supercell", preview)

    def test_medium_article_builds_backup_preview(self):
        article = {
            "priority": "medium",
            "ru_found": True,
            "ru_title": "Запасная новость Brawl Stars",
            "ru_clean_content": [
                "В официальной статье подробно описано новое игровое событие."
            ],
        }

        preview = build_article_news_preview(article)

        self.assertIsNotNone(preview)
        self.assertIn("🟡 MEDIUM", preview)

    def test_article_without_russian_version_does_not_build_preview(self):
        article = {
            "priority": "high",
            "ru_found": False,
            "ru_clean_content": [
                "Этот текст не должен использоваться без найденной русской версии."
            ],
        }

        self.assertIsNone(build_article_news_preview(article))

    def test_empty_russian_content_does_not_build_preview(self):
        article = {
            "priority": "high",
            "ru_found": True,
            "ru_title": "Пустая статья",
            "ru_clean_content": [],
        }

        self.assertIsNone(build_article_news_preview(article))

    def test_short_service_and_title_blocks_are_removed(self):
        useful_block = "Официальный содержательный абзац сохраняется без переписывания."
        article = {
            "priority": "high",
            "ru_found": True,
            "ru_title": "Заголовок русской статьи",
            "ru_clean_content": [
                "Заголовок русской статьи",
                "Короткая строка",
                "Поделиться этой новостью в социальных сетях",
                useful_block,
            ],
        }

        selected = select_news_content(article)

        self.assertEqual(selected, [useful_block])

    def test_news_content_respects_block_limit(self):
        blocks = [
            f"Содержательный официальный блок номер {index} с подробностями."
            for index in range(1, 7)
        ]
        article = {
            "priority": "high",
            "ru_found": True,
            "ru_title": "Новость",
            "ru_clean_content": blocks,
        }

        selected = select_news_content(article)

        self.assertEqual(
            len(selected),
            russian_preview_namespace["NEWS_MAX_BLOCKS"],
        )
        self.assertEqual(selected, blocks[:2])

    def test_news_content_respects_total_character_limit(self):
        blocks = [
            "А" * 300,
            "Б" * 300,
            "В" * 300,
        ]
        article = {
            "priority": "high",
            "ru_found": True,
            "ru_title": "Новость",
            "ru_clean_content": blocks,
        }

        selected = select_news_content(article)
        selected_length = len("\n\n".join(selected))

        self.assertEqual(selected, blocks[:1])
        self.assertLessEqual(
            selected_length,
            russian_preview_namespace["NEWS_MAX_CHARS"],
        )

    def test_russian_day_stage_is_removed(self):
        useful_block = "В первый день игроки смогут получить особую награду."
        article = {
            "priority": "medium",
            "ru_found": True,
            "ru_title": "Кубок Старр",
            "ru_clean_content": [
                "День 2 | Создание эмблемы.",
                useful_block,
            ],
        }

        self.assertEqual(select_news_content(article), [useful_block])

    def test_english_day_stage_is_removed(self):
        useful_block = "Официальный русский абзац содержит подробности события."
        article = {
            "priority": "high",
            "ru_found": True,
            "ru_title": "Новость",
            "ru_clean_content": [
                "Day 2 | Create your club badge.",
                useful_block,
            ],
        }

        self.assertEqual(select_news_content(article), [useful_block])

    def test_regular_paragraph_with_day_word_is_preserved(self):
        useful_block = "В этот день игроки получат десять особых наград."
        article = {
            "priority": "medium",
            "ru_found": True,
            "ru_title": "Новость",
            "ru_clean_content": [useful_block],
        }

        self.assertEqual(select_news_content(article), [useful_block])

    def test_short_heading_without_sentence_is_removed(self):
        useful_block = "Участники события смогут создать собственную эмблему клуба."
        article = {
            "priority": "medium",
            "ru_found": True,
            "ru_title": "Новость",
            "ru_clean_content": [
                "Создание клубной эмблемы",
                useful_block,
            ],
        }

        self.assertEqual(select_news_content(article), [useful_block])

    def test_medium_preview_counts_as_news_material(self):
        article = {
            "priority": "medium",
            "ru_found": True,
            "ru_title": "Запасная новость",
            "ru_clean_content": [
                "Официальная статья подробно рассказывает об игровом событии."
            ],
        }
        preview = build_article_news_preview(article)
        output = StringIO()

        with redirect_stdout(output):
            print_generation_result(None, [preview])

        self.assertIn("✓ Есть новостной материал для выпуска", output.getvalue())
        self.assertNotIn("Пост сегодня не требуется", output.getvalue())

    def test_high_preview_counts_as_news_material(self):
        article = {
            "priority": "high",
            "ru_found": True,
            "ru_title": "Основная новость",
            "ru_clean_content": [
                "Официальная статья подробно рассказывает о новом бойце."
            ],
        }
        preview = build_article_news_preview(article)
        output = StringIO()

        with redirect_stdout(output):
            print_generation_result(None, [preview])

        self.assertIn("✓ Есть новостной материал для выпуска", output.getvalue())
        self.assertNotIn("Пост сегодня не требуется", output.getvalue())

    def test_no_balance_or_news_material_does_not_require_post(self):
        output = StringIO()

        with redirect_stdout(output):
            print_generation_result(None, [])

        self.assertIn("Новых материалов нет.", output.getvalue())
        self.assertIn("Пост сегодня не требуется.", output.getvalue())

    def test_old_json_without_russian_fields_does_not_build_preview(self):
        old_article = {
            "title": "Old article",
            "priority": "high",
        }

        self.assertIsNone(build_article_news_preview(old_article))

    def test_low_article_does_not_build_russian_preview(self):
        low_article = {
            "priority": "low",
            "ru_found": True,
            "ru_title": "LOW статья",
            "ru_clean_content": [
                "Даже содержательный русский текст LOW статьи игнорируется."
            ],
        }

        self.assertIsNone(build_article_news_preview(low_article))


if __name__ == "__main__":
    unittest.main()
