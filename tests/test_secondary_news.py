import unittest

from external_news_facts import is_news_event
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
    def test_sportskeeda_article_body_is_added_after_rss_discovery(self):
        feed = make_feed(
            publisher="Sportskeeda",
            title="Adopt Me launches new Moonlight event",
            description="The Moonlight event is now live with new activities.",
        )
        page = """<html><article>
        <h2>Moonlight event details</h2>
        <p>Players can collect Moon Tokens by completing nightly tasks.</p>
        <li>New Luna Fox pet - 500 Moon Tokens</li>
        </article></html>"""

        class Response:
            def __init__(self, text):
                self.text = text

            def raise_for_status(self):
                return None

        def requester(url, **kwargs):
            return Response(feed if "news.google.com" in url else page)

        results = fetch_secondary_news(
            games=[{"name": "Adopt Me!"}], requester=requester
        )
        article = results[0]["latest_article"]

        self.assertIn("Moon Tokens", article["text"])
        self.assertIn("Luna Fox", article["text"])
        self.assertEqual(
            article["content_url"],
            "https://hindi3.sportskeeda.com/roblox-news/"
            "adopt-me-launches-new-moonlight-event",
        )

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

    def test_all_pets_reference_is_rejected(self):
        feed = make_feed(
            publisher="Sportskeeda",
            title="All Pets in Steal An Egg: Rarity, income, and more",
            description="All pets with their rarity and income values.",
        )
        self.assertEqual(parse_feed("Steal An Egg", feed), [])

    def test_mm2_values_and_trading_list_is_rejected(self):
        exact_title = (
            "Roblox MM2 values list: Murder Mystery 2 weapon, "
            "knife & pet trade values"
        )
        self.assertFalse(is_news_event({"title": exact_title, "text": exact_title}))
        feed = make_feed(
            publisher="Dexerto",
            title=(
                "Roblox MM2 values list: Murder Mystery 2 weapon, "
                "knife &amp; pet trade values"
            ),
            description="A reference list for weapon and pet trading values.",
        )
        self.assertEqual(parse_feed("Murder Mystery 2", feed), [])

    def test_codes_article_is_rejected(self):
        feed = make_feed(
            title="Brookhaven RP codes and redeem codes",
            description="A fresh list of working reward codes.",
        )
        self.assertEqual(parse_feed("Brookhaven", feed), [])

    def test_tier_list_is_rejected(self):
        feed = make_feed(
            title="Brookhaven RP vehicle tier list",
            description="Every existing vehicle ranked from best to worst.",
        )
        self.assertEqual(parse_feed("Brookhaven", feed), [])

    def test_how_to_article_is_rejected(self):
        feed = make_feed(
            title="How to get every item in Brookhaven RP",
            description="A complete walkthrough for current items.",
        )
        self.assertEqual(parse_feed("Brookhaven", feed), [])

    def test_fresh_article_without_news_event_is_rejected(self):
        article = {
            "title": "Brookhaven RP explained",
            "text": "A reference overview of houses, vehicles, and roleplay systems.",
        }
        self.assertFalse(is_news_event(article))

    def test_released_update_is_accepted(self):
        feed = make_feed(
            title="Brookhaven Prison Update is live",
            description=(
                "The update adds a new prison landmark, prisoner bus, "
                "and warden tools."
            ),
        )
        self.assertEqual(len(parse_feed("Brookhaven", feed)), 1)

    def test_new_map_is_accepted(self):
        feed = make_feed(
            title="RIVALS launches new Harbor map",
            description="The update adds the Harbor map to public matches.",
        )
        self.assertEqual(len(parse_feed("RIVALS", feed)), 1)

    def test_new_event_is_accepted(self):
        feed = make_feed(
            title="Adopt Me launches new Moonlight event",
            description="The Moonlight event is now live with new activities.",
        )
        self.assertEqual(len(parse_feed("Adopt Me!", feed)), 1)

    def test_item_really_added_by_update_is_accepted(self):
        feed = make_feed(
            title="Brookhaven Bank Update adds security scanner",
            description="The released update adds a new security scanner item.",
        )
        self.assertEqual(len(parse_feed("Brookhaven", feed)), 1)

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
