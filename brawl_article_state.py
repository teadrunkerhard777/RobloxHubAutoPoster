import json
from datetime import datetime, timezone

EMPTY_STATE = {"articles": {}}


def utc_today():
    """Returns a timezone-aware date for unattended GitHub runs."""

    return datetime.now(timezone.utc).date()


def load_brawl_article_state(filename):
    """Loads durable discovery/publication state without failing first run."""

    try:
        with open(filename, encoding="utf-8") as file:
            state = json.load(file)
    except (OSError, ValueError, TypeError):
        return {"articles": {}}

    if not isinstance(state, dict) or not isinstance(state.get("articles"), dict):
        return {"articles": {}}

    return state


def save_brawl_article_state(filename, state):
    """Persists the lifecycle separately from monitor discovery history."""

    with open(filename, "w", encoding="utf-8") as file:
        json.dump(state, file, ensure_ascii=False, indent=2)


def normalize_article_date(value):
    """Returns an ISO date accepted by the Brawl freshness check."""

    if not value:
        return None

    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00")).date()
    except ValueError:
        return None


def is_article_fresh(article, today, max_age_days):
    """Uses the existing Brawl window; lifecycle never extends freshness."""

    published_date = normalize_article_date(article.get("date"))
    if published_date is None:
        return False

    age_days = (today - published_date).days
    return 0 <= age_days <= max_age_days


def is_selectable_article(article):
    """Mirrors monitor priority rules without weakening quality filters."""

    if article.get("official", True) is not True:
        return False

    priority = article.get("priority", "low")
    return priority in {"high", "medium"} or (
        priority == "low" and article.get("is_relevant") is True
    )


def find_matching_brawl_post(article, posts):
    """Finds queue/history evidence by URL, with a title migration fallback."""

    article_url = article.get("url")
    aliases = {
        str(article.get(field, "")).strip().casefold()
        for field in ("title", "ru_title", "translated_title")
        if article.get(field)
    }

    for post in posts:
        if post.get("source") != "brawl_pipeline":
            continue

        if article_url and post.get("brawl_article_url") == article_url:
            return post

        # Старые записи очереди ещё не содержат URL. Точное вхождение
        # официального EN/RU заголовка позволяет безопасно мигрировать их.
        post_text = str(post.get("text", "")).casefold()
        if any(len(alias) >= 8 and alias in post_text for alias in aliases):
            return post

    return None


def reconcile_brawl_article_state(state, posts, today=None, max_age_days=7):
    """Reconciles durable article statuses with the real Telegram queue."""

    if today is None:
        today = utc_today()

    for entry in state.get("articles", {}).values():
        article = entry.get("article", {})
        matching_post = find_matching_brawl_post(article, posts)

        if matching_post and matching_post.get("status") == "published":
            entry["status"] = "published"
            entry["published_at"] = matching_post.get("published_at")
            entry["scheduled_post_id"] = matching_post.get("id")
            continue

        if matching_post is not None:
            entry["status"] = "scheduled"
            entry["scheduled_post_id"] = matching_post.get("id")
            continue

        # Published history is durable even if old posts are pruned later.
        if entry.get("status") == "published":
            continue

        if not is_article_fresh(article, today, max_age_days):
            entry["status"] = "stale"
        elif entry.get("status") == "scheduled":
            # Если запись очереди исчезла до публикации, материал не потерян.
            entry["status"] = "pending"
            entry.pop("scheduled_post_id", None)

    return state


def register_brawl_articles(
    state,
    articles,
    posts,
    today=None,
    max_age_days=7,
):
    """Registers enriched discoveries and derives pending/published status."""

    if today is None:
        today = utc_today()

    records = state.setdefault("articles", {})

    for article in articles:
        url = article.get("url")
        if not url:
            continue

        entry = records.setdefault(url, {})
        entry.update(
            {
                "discovered": True,
                "seen": True,
                "selected": is_selectable_article(article),
                "article": article,
            }
        )

        matching_post = find_matching_brawl_post(article, posts)
        if matching_post and matching_post.get("status") == "published":
            entry["status"] = "published"
            entry["published_at"] = matching_post.get("published_at")
            entry["scheduled_post_id"] = matching_post.get("id")
        elif matching_post is not None:
            entry["status"] = "scheduled"
            entry["scheduled_post_id"] = matching_post.get("id")
        elif not is_article_fresh(article, today, max_age_days):
            entry["status"] = "stale"
        elif entry["selected"]:
            entry["status"] = "pending"
        else:
            entry["status"] = "rejected"

    return reconcile_brawl_article_state(
        state,
        posts,
        today=today,
        max_age_days=max_age_days,
    )


def get_pending_brawl_articles(state, today=None, max_age_days=7):
    """Returns full pending payloads for the generator input."""

    if today is None:
        today = utc_today()

    return [
        entry["article"]
        for entry in state.get("articles", {}).values()
        if entry.get("status") == "pending"
        and is_article_fresh(entry.get("article", {}), today, max_age_days)
    ]


def get_untracked_recent_articles(
    discovered_articles,
    state,
    today=None,
    max_age_days=7,
):
    """Recovers known monitor URLs that never entered durable lifecycle."""

    if today is None:
        today = utc_today()

    tracked_urls = set(state.get("articles", {}))
    return [
        article
        for article in discovered_articles
        if article.get("url") not in tracked_urls
        and is_article_fresh(article, today, max_age_days)
    ]


def mark_brawl_articles_scheduled(state, urls, post_id):
    """Marks selection scheduled only after a real queue record exists."""

    for url in urls:
        entry = state.get("articles", {}).get(url)
        if entry is None or entry.get("status") == "published":
            continue
        entry["status"] = "scheduled"
        entry["scheduled_post_id"] = post_id

    return state
