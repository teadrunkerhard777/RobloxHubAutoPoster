import unittest
from datetime import date

from brawl_article_state import (
    get_pending_brawl_articles,
    get_untracked_recent_articles,
    mark_brawl_articles_scheduled,
    reconcile_brawl_article_state,
    register_brawl_articles,
)

ARTICLE_URL = "https://supercell.com/bsc-2027"


def make_article(article_date="2026-08-24"):
    return {
        "url": ARTICLE_URL,
        "title": "First Look at BSC 2027",
        "ru_title": "Первый взгляд на BSC 2027",
        "date": article_date,
        "priority": "medium",
        "official": True,
        "is_relevant": True,
    }


class BrawlArticleStateTests(unittest.TestCase):
    def test_discovered_but_unscheduled_remains_eligible_next_monitor_run(self):
        state = register_brawl_articles(
            {"articles": {}},
            [make_article()],
            [],
            today=date(2026, 8, 25),
        )

        state = reconcile_brawl_article_state(
            state,
            [],
            today=date(2026, 8, 26),
        )

        self.assertEqual(state["articles"][ARTICLE_URL]["status"], "pending")
        self.assertEqual(
            get_pending_brawl_articles(state, date(2026, 8, 26)), [make_article()]
        )

    def test_known_monitor_url_without_publication_can_still_be_scheduled(self):
        monitor_articles = [make_article()]
        lifecycle = {"articles": {}}

        recovered = get_untracked_recent_articles(
            monitor_articles,
            lifecycle,
            today=date(2026, 8, 25),
        )
        lifecycle = register_brawl_articles(
            lifecycle,
            recovered,
            [],
            today=date(2026, 8, 25),
        )
        mark_brawl_articles_scheduled(
            lifecycle,
            {ARTICLE_URL},
            "2026-08-26-brawl-12",
        )

        entry = lifecycle["articles"][ARTICLE_URL]
        self.assertEqual(recovered, monitor_articles)
        self.assertEqual(entry["status"], "scheduled")
        self.assertEqual(entry["scheduled_post_id"], "2026-08-26-brawl-12")

    def test_published_article_is_not_scheduled_again(self):
        published_post = {
            "id": "2026-08-26-brawl-12",
            "status": "published",
            "source": "brawl_pipeline",
            "brawl_article_url": ARTICLE_URL,
            "published_at": "2026-08-26T12:00:10+05:00",
            "text": "Первый взгляд на BSC 2027",
        }
        state = register_brawl_articles(
            {"articles": {}},
            [make_article()],
            [published_post],
            today=date(2026, 8, 26),
        )

        mark_brawl_articles_scheduled(
            state,
            {ARTICLE_URL},
            "2026-08-27-brawl-12",
        )
        reconcile_brawl_article_state(
            state,
            [],
            today=date(2026, 9, 30),
        )

        self.assertEqual(state["articles"][ARTICLE_URL]["status"], "published")
        self.assertEqual(get_pending_brawl_articles(state, date(2026, 8, 26)), [])

    def test_stale_pending_article_is_dropped(self):
        state = register_brawl_articles(
            {"articles": {}},
            [make_article("2026-08-01")],
            [],
            today=date(2026, 8, 31),
        )

        self.assertEqual(state["articles"][ARTICLE_URL]["status"], "stale")
        self.assertEqual(get_pending_brawl_articles(state, date(2026, 8, 31)), [])

    def test_empty_new_articles_does_not_erase_valid_pending_article(self):
        state = register_brawl_articles(
            {"articles": {}},
            [make_article()],
            [],
            today=date(2026, 8, 25),
        )

        state = register_brawl_articles(
            state,
            [],
            [],
            today=date(2026, 8, 26),
        )

        self.assertEqual(
            get_pending_brawl_articles(state, date(2026, 8, 26)), [make_article()]
        )
