import unittest
from unittest.mock import patch

import requests

import fetch_external_news


class FetchExternalNewsTests(unittest.TestCase):
    @patch("fetch_external_news.fetch_page")
    def test_unavailable_youtube_feed_does_not_break_pipeline(self, fetch_page):
        fetch_page.side_effect = requests.RequestException("HTTP 404")

        result = fetch_external_news.collect_youtube_feed(
            "Grow a Garden",
            {
                "youtube_feed_url": "https://youtube.example/missing",
                "youtube_match_terms": ["grow a garden"],
            },
        )

        self.assertFalse(result["success"])
        self.assertIsNone(result["latest_article"])
        self.assertIn("404", result["error"])

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

        result = fetch_external_news.extract_page_data(html, "https://example.com/news")

        self.assertEqual(result["title"], "Fresh Update")
        self.assertEqual(result["published_at"], "2026-08-19T08:00:00Z")
        self.assertEqual(
            [link["url"] for link in result["links"]],
            ["https://example.com/news", "https://example.com/news/fresh-update"],
        )

    def test_finds_latest_blox_fruits_article(self):
        result = fetch_external_news.find_latest_article_url(
            "Blox Fruits",
            "https://gamerrobot.com/blogs/news",
            [
                {"text": "News", "url": ("https://gamerrobot.com/blogs/news")},
                {
                    "text": "Read more",
                    "url": ("https://gamerrobot.com/" "blogs/news/the-balance-log"),
                },
            ],
        )

        self.assertEqual(
            result, ("https://gamerrobot.com/" "blogs/news/the-balance-log")
        )

    def test_finds_latest_adopt_me_article(self):
        result = fetch_external_news.find_latest_article_url(
            "Adopt Me!",
            "https://www.playadopt.me/news",
            [
                {"text": "Skip", "url": ("https://www.playadopt.me/news#main")},
                {
                    "text": "Read More",
                    "url": ("https://www.playadopt.me/news/" "tux-and-shepherd"),
                },
            ],
        )

        self.assertEqual(result, ("https://www.playadopt.me/news/" "tux-and-shepherd"))

    def test_finds_latest_brookhaven_article(self):
        result = fetch_external_news.find_latest_article_url(
            "Brookhaven",
            "https://www.brookhavenrp.com/",
            [
                {
                    "text": "Home",
                    "url": "https://www.brookhavenrp.com/",
                },
                {
                    "text": "Brookhaven Update August 14, 2026",
                    "url": (
                        "https://www.brookhavenrp.com/"
                        "posts/brookhaven-update-august-14-2026"
                    ),
                },
            ],
        )

        self.assertEqual(
            result,
            ("https://www.brookhavenrp.com/" "posts/brookhaven-update-august-14-2026"),
        )

    def test_finds_latest_blade_ball_article(self):
        result = fetch_external_news.find_latest_article_url(
            "Blade Ball",
            "https://bladeball.com/blogs/news",
            [
                {
                    "text": "Release notes",
                    "url": (
                        "https://bladeball.com/blogs/news/"
                        "blade-ball-v2-0-release-notes"
                    ),
                }
            ],
        )

        self.assertEqual(
            result,
            ("https://bladeball.com/blogs/news/" "blade-ball-v2-0-release-notes"),
        )

    def test_finds_latest_pet_simulator_99_article(self):
        result = fetch_external_news.find_latest_article_url(
            "Pet Simulator 99",
            "https://www.biggames.io/post",
            [
                {
                    "text": "Other game",
                    "url": "https://www.biggames.io/post/pets-go-update-1",
                },
                {
                    "text": "Latest PS99 update",
                    "url": (
                        "https://www.biggames.io/" "post/pet-simulator-99-update-87"
                    ),
                },
            ],
        )

        self.assertEqual(
            result,
            ("https://www.biggames.io/" "post/pet-simulator-99-update-87"),
        )

    def test_infers_date_from_feed_link(self):
        result = fetch_external_news.infer_published_at_from_links(
            "https://voldex.com/news/brookhaven-event",
            [
                {
                    "text": "19 June 2026 Brookhaven event",
                    "url": "https://voldex.com/news/brookhaven-event",
                }
            ],
        )

        self.assertEqual(result, "2026-06-19")

    def test_infers_english_month_first_date_from_brookhaven_link(self):
        article_url = (
            "https://www.brookhavenrp.com/" "posts/brookhaven-update-august-14-2026"
        )
        result = fetch_external_news.infer_published_at_from_links(
            article_url,
            [
                {
                    "text": "Brookhaven Update August 14, 2026",
                    "url": article_url,
                }
            ],
        )

        self.assertEqual(result, "2026-08-14")

    @patch("fetch_external_news.fetch_page")
    def test_collects_dated_youtube_entry_with_content(self, fetch_page):
        fetch_page.return_value = """<?xml version="1.0"?>
        <feed xmlns="http://www.w3.org/2005/Atom"
              xmlns:yt="http://www.youtube.com/xml/schemas/2015"
              xmlns:media="http://search.yahoo.com/mrss/">
          <title>Dress To Impress</title>
          <author><name>Dress To Impress</name></author>
          <entry>
            <yt:videoId>fresh123</yt:videoId>
            <title>Dress To Impress Summer Event Trailer</title>
            <published>2026-08-20T12:00:00+00:00</published>
            <media:group>
              <media:description>
                A new Dress To Impress event launches this week.
              </media:description>
            </media:group>
          </entry>
        </feed>"""

        result = fetch_external_news.collect_youtube_feed(
            "Dress To Impress",
            {
                "youtube_feed_url": "https://youtube.example/feed",
                "youtube_channel_name": "Dress To Impress",
                "youtube_match_terms": ["dress to impress", "dti"],
            },
        )

        self.assertTrue(result["success"])
        self.assertEqual(
            result["latest_article"]["published_at"],
            "2026-08-20T12:00:00+00:00",
        )
        self.assertIn(
            "A new Dress To Impress event",
            result["latest_article"]["text"],
        )

    @patch("fetch_external_news.fetch_page")
    def test_collects_feed_and_latest_article(self, fetch_page):
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

        fetch_page.side_effect = [feed_html, article_html]

        results = fetch_external_news.collect_external_news(
            {"Adopt Me!": {"news_url": ("https://www.playadopt.me/news")}}
        )

        article = results[0]["latest_article"]

        self.assertTrue(article["success"])
        self.assertEqual(article["title"], "Latest Update")
        self.assertEqual(article["published_at"], "2026-08-19")
        self.assertIn("A new pet is available.", article["text"])


if __name__ == "__main__":
    unittest.main()
