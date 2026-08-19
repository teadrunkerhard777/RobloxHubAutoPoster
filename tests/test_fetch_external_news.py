import unittest

from unittest.mock import patch

import fetch_external_news


class FetchExternalNewsTests(unittest.TestCase):
    def test_extracts_article_metadata_and_internal_links(self):
        html = """
        <html>
          <head>
            <meta property="og:title" content="Fresh Update">
            <meta property="article:published_time"
                  content="2026-08-19T08:00:00Z">
          </head>
          <body>
            <a href="/news">News</a>
            <a href="/news/fresh-update">Read more</a>
            <a href="https://example.com/news/fresh-update">
              Duplicate
            </a>
            <a href="https://other.example/news">External</a>
          </body>
        </html>
        """

        result = fetch_external_news.extract_page_data(
            html,
            "https://example.com/news"
        )

        self.assertEqual(
            result["title"],
            "Fresh Update"
        )
        self.assertEqual(
            result["published_at"],
            "2026-08-19T08:00:00Z"
        )
        self.assertEqual(
            [link["url"] for link in result["links"]],
            [
                "https://example.com/news",
                "https://example.com/news/fresh-update"
            ]
        )

    def test_finds_latest_blox_fruits_article(self):
        result = (
            fetch_external_news.find_latest_article_url(
                "Blox Fruits",
                "https://gamerrobot.com/blogs/news",
                [
                    {
                        "text": "News",
                        "url": (
                            "https://gamerrobot.com/blogs/news"
                        )
                    },
                    {
                        "text": "Read more",
                        "url": (
                            "https://gamerrobot.com/"
                            "blogs/news/the-balance-log"
                        )
                    }
                ]
            )
        )

        self.assertEqual(
            result,
            (
                "https://gamerrobot.com/"
                "blogs/news/the-balance-log"
            )
        )

    def test_finds_latest_adopt_me_article(self):
        result = (
            fetch_external_news.find_latest_article_url(
                "Adopt Me!",
                "https://www.playadopt.me/news",
                [
                    {
                        "text": "Skip",
                        "url": (
                            "https://www.playadopt.me/news#main"
                        )
                    },
                    {
                        "text": "Read More",
                        "url": (
                            "https://www.playadopt.me/news/"
                            "tux-and-shepherd"
                        )
                    }
                ]
            )
        )

        self.assertEqual(
            result,
            (
                "https://www.playadopt.me/news/"
                "tux-and-shepherd"
            )
        )

    @patch("fetch_external_news.fetch_page")
    def test_collects_feed_and_latest_article(
        self,
        fetch_page
    ):
        feed_html = """
        <html>
          <body>
            <a href="/news/latest-update">Read More</a>
          </body>
        </html>
        """
        article_html = """
        <html>
          <head>
            <meta property="og:title" content="Latest Update">
          </head>
          <body>
            <time datetime="2026-08-19">August 19</time>
            <p>A new pet is available.</p>
          </body>
        </html>
        """

        fetch_page.side_effect = [
            feed_html,
            article_html
        ]

        results = (
            fetch_external_news.collect_external_news(
                {
                    "Adopt Me!": {
                        "news_url": (
                            "https://www.playadopt.me/news"
                        )
                    }
                }
            )
        )

        article = results[0][
            "latest_article"
        ]

        self.assertTrue(
            article["success"]
        )
        self.assertEqual(
            article["title"],
            "Latest Update"
        )
        self.assertEqual(
            article["published_at"],
            "2026-08-19"
        )
        self.assertIn(
            "A new pet is available.",
            article["text"]
        )


if __name__ == "__main__":
    unittest.main()
