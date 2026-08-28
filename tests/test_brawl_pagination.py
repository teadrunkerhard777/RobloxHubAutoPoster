import ast
import re
import unittest
from datetime import date
from pathlib import Path
from types import SimpleNamespace
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

PROJECT_ROOT = Path(__file__).parents[1]
BRAWL_MONITOR_PATH = PROJECT_ROOT / "brawl_monitor.py"


def load_brawl_collection():
    source = BRAWL_MONITOR_PATH.read_text(encoding="utf-8")
    tree = ast.parse(source)
    names = {
        "get_article_category",
        "normalize_article_date",
        "extract_archive_article_date",
        "extract_blog_articles",
        "fetch_blog_articles",
        "build_brawl_source_health",
        "make_article_key",
        "is_recent_article",
        "find_new_articles",
    }
    selected = [
        node
        for node in tree.body
        if isinstance(node, ast.FunctionDef) and node.name in names
    ]
    namespace = {
        "ARTICLE_MONTHS": {
            "aug": 8,
            "august": 8,
        },
        "BASE_URL": "https://supercell.com",
        "BLOG_PAGE_URLS": (),
        "BRAWL_NEWS_MAX_AGE_DAYS": 7,
        "BeautifulSoup": BeautifulSoup,
        "date": date,
        "re": re,
        "requests": requests,
        "urljoin": urljoin,
    }
    exec(  # noqa: S102
        compile(
            ast.Module(body=selected, type_ignores=[]), str(BRAWL_MONITOR_PATH), "exec"
        ),
        namespace,
    )
    return namespace


COLLECTION = load_brawl_collection()


def article_card(path, title, published_date):
    return f"""
    <div data-test-class="archived-article">
      <p data-test-id="publish-date-text">{published_date}</p>
      <a href="{path}">{title}</a>
    </div>
    """


class BrawlPaginationTests(unittest.TestCase):
    def test_collects_page_one_and_two_deduplicates_and_sorts(self):
        page_one = article_card(
            "/en/games/brawlstars/blog/release-notes/release/",
            "Release Notes",
            "3 Aug 2026",
        ) + article_card(
            "/en/games/brawlstars/blog/community/community-event/",
            "Community Event",
            "6 Aug 2026",
        )
        page_two = article_card(
            "/en/games/brawlstars/blog/community/community-event/",
            "Community Event",
            "6 Aug 2026",
        ) + article_card(
            "/en/games/brawlstars/blog/news/older-event/",
            "Older Event",
            "1 Aug 2026",
        )

        def fake_get(url, timeout):
            html = page_one if url.endswith("page/1/") else page_two
            return SimpleNamespace(status_code=200, content=html.encode("utf-8"))

        COLLECTION["requests"] = SimpleNamespace(
            get=fake_get,
            RequestException=requests.RequestException,
        )
        articles, health = COLLECTION["fetch_blog_articles"](
            ["https://example/page/1/", "https://example/page/2/"]
        )

        self.assertEqual(len(health), 2)
        self.assertEqual(len(articles), 3)
        self.assertEqual(articles[0]["title"], "Community Event")
        self.assertEqual(articles[-1]["title"], "Older Event")
        self.assertEqual(articles[0]["category"], "community")

    def test_failure_of_one_page_does_not_break_collection(self):
        good_html = article_card(
            "/en/games/brawlstars/blog/community/fresh/",
            "Fresh Community Article",
            "6 Aug 2026",
        )

        def fake_get(url, timeout):
            if url.endswith("page/1/"):
                raise requests.RequestException("temporary failure")
            return SimpleNamespace(status_code=200, content=good_html.encode("utf-8"))

        COLLECTION["requests"] = SimpleNamespace(
            get=fake_get,
            RequestException=requests.RequestException,
        )
        articles, health = COLLECTION["fetch_blog_articles"](
            ["https://example/page/1/", "https://example/page/2/"]
        )

        self.assertEqual(len(articles), 1)
        self.assertFalse(health[0]["available"])
        self.assertTrue(health[1]["available"])

    def test_old_article_does_not_become_new_again(self):
        article = {
            "title": "Already processed",
            "url": "https://supercell.com/article/already-processed/",
        }

        result = COLLECTION["find_new_articles"](
            [article],
            [{"url": article["url"]}],
            today=date(2026, 8, 27),
        )

        self.assertEqual(result, [])

    def test_old_unseen_pagination_article_is_not_new(self):
        article = {
            "title": "Old page two article",
            "url": "https://supercell.com/article/old-page-two/",
            "date": "2026-08-01",
        }

        result = COLLECTION["find_new_articles"](
            [article],
            [],
            today=date(2026, 8, 27),
        )

        self.assertEqual(result, [])

    def test_article_without_russian_version_is_reported_as_translated(self):
        health = COLLECTION["build_brawl_source_health"](
            [{"available": True}],
            [{"url": "https://supercell.com/article/official/"}],
            [
                {
                    "priority": "medium",
                    "ru_found": False,
                    "translated": True,
                    "is_relevant": True,
                    "source_available": True,
                    "extraction_success": True,
                }
            ],
        )

        self.assertEqual(health["verification_passed"], 1)
        self.assertEqual(health["verification_rejected"], 0)


if __name__ == "__main__":
    unittest.main()
