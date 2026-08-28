import unittest

from fetch_secondary_news import fetch_secondary_news, parse_feed


def make_feed(publisher="PCGamesN", title="Brookhaven Bank Update", description=None):
    if description is None:
        description = "The Roblox update adds a new bank location and rewards."
    return f"""<?xml version="1.0"?>
    <rss><channel><item>
      <title>{title} - {publisher}</title>
      <link>https://example.com/brookhaven-bank</link>
      <pubDate>Thu, 27 Aug 2026 10:00:00 GMT</pubDate>
      <source>{publisher}</source>
      <description>{description}</description>
    </item></channel></rss>"""


class SecondaryNewsTests(unittest.TestCase):
    def test_major_gaming_media_with_concrete_content_is_discovered(self):
        articles = parse_feed("Brookhaven", make_feed())
        self.assertEqual(len(articles), 1)
        self.assertEqual(articles[0]["source_tier"], "B")
        self.assertEqual(articles[0]["publisher"], "PCGamesN")

    def test_unapproved_or_community_source_is_not_used(self):
        self.assertEqual(parse_feed("Brookhaven", make_feed("Fan Wiki")), [])

    def test_rumor_is_discovery_only_and_not_a_candidate(self):
        feed = make_feed(
            title="Brookhaven leaked Bank Update",
            description="A datamine allegedly reveals a possible Roblox event.",
        )
        self.assertEqual(parse_feed("Brookhaven", feed), [])

    def test_evergreen_guide_is_not_misclassified_as_news(self):
        feed = make_feed(
            title="How to get pets in Brookhaven RP",
            description="A complete Roblox guide to the best pets and rewards.",
        )
        self.assertEqual(parse_feed("Brookhaven", feed), [])

    def test_failure_of_one_game_does_not_stop_other_games(self):
        class Response:
            def __init__(self, text):
                self.text = text

            def raise_for_status(self):
                return None

        def requester(url, **kwargs):
            if "Broken" in url:
                return Response("not xml")
            return Response(make_feed())

        results = fetch_secondary_news(
            games=[{"name": "Broken"}, {"name": "Brookhaven"}],
            requester=requester,
        )
        self.assertEqual(len(results), 2)
        self.assertFalse(results[0]["success"])
        self.assertTrue(results[1]["success"])
        self.assertIsNotNone(results[1]["latest_article"])


if __name__ == "__main__":
    unittest.main()
