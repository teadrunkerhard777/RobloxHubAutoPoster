import re

from datetime import datetime, timezone


MAX_ARTICLE_AGE_DAYS = 3


def parse_published_at(value):
    if not value:
        return None

    normalized = value.strip()

    if normalized.endswith("Z"):
        normalized = (
            normalized[:-1]
            + "+00:00"
        )

    try:
        result = datetime.fromisoformat(
            normalized
        )
    except ValueError:
        return None

    if result.tzinfo is None:
        result = result.replace(
            tzinfo=timezone.utc
        )

    return result.astimezone(
        timezone.utc
    )


def get_article_age_days(
    article,
    now=None
):
    published_at = parse_published_at(
        article.get(
            "published_at"
        )
    )

    if published_at is None:
        return None

    if now is None:
        now = datetime.now(
            timezone.utc
        )
    elif now.tzinfo is None:
        now = now.replace(
            tzinfo=timezone.utc
        )

    age = (
        now.astimezone(timezone.utc)
        - published_at
    )

    return age.total_seconds() / 86400


def is_fresh_article(
    article,
    now=None,
    max_age_days=MAX_ARTICLE_AGE_DAYS
):
    if not article:
        return False

    if article.get("success") is not True:
        return False

    if not article.get("url"):
        return False

    age_days = get_article_age_days(
        article,
        now=now
    )

    if age_days is None:
        return False

    # Небольшой допуск на часы серверов,
    # но не на статьи из далёкого будущего.
    return (
        age_days >= -1
        and age_days <= max_age_days
    )


def make_external_fact(
    article,
    text,
    summary_ru,
    kind,
    value
):
    return {
        "text": text,
        "summary_ru": summary_ru,
        "kind": kind,
        "value": value,
        "specific": True,
        "reason": (
            "Факт из официальной новостной статьи"
        ),
        "is_new_line": True,
        "source_url": article["url"]
    }


def clean_article_title(
    game,
    title
):
    result = title.strip()

    if game == "Adopt Me!":
        result = re.sub(
            r"\s*-\s*Adopt Me!\s*$",
            "",
            result,
            flags=re.IGNORECASE
        )

    result = re.sub(
        r"\s+Notes!?\s*$",
        "",
        result,
        flags=re.IGNORECASE
    )

    return result.strip()


def build_title_fact(
    game,
    article
):
    title = clean_article_title(
        game,
        article.get(
            "title",
            ""
        )
    )

    if not title:
        return None

    if game == "Blox Fruits":
        patch_match = re.search(
            r"(.+?)\s+Patch Notes\s*-\s*"
            r"Balance Patch\s*(\d+)",
            article.get("text", ""),
            flags=re.IGNORECASE
        )

        if patch_match:
            patch_name = patch_match.group(
                1
            ).strip()
            patch_number = patch_match.group(
                2
            )

            summary = (
                "В Blox Fruits вышел "
                f"балансный патч {patch_name} "
                f"#{patch_number}."
            )
        else:
            summary = (
                "Blox Fruits опубликовала "
                f"новость «{title}»."
            )

    elif game == "Adopt Me!":
        summary = (
            "В Adopt Me! вышло обновление "
            f"«{title}»."
        )

    else:
        summary = (
            f"В {game} вышло обновление "
            f"«{title}»."
        )

    return make_external_fact(
        article=article,
        text=title,
        summary_ru=summary,
        kind="official_article",
        value=7
    )


def extract_adopt_me_facts(
    article
):
    text = article.get(
        "text",
        ""
    )

    facts = []

    pet_match = re.search(
        r"(?:🐶\s*)?"
        r"([A-Za-z][A-Za-z ]+?)\s*-\s*"
        r"Hatch from the\s+(.+?)\s*-\s*\n"
        r"([A-Za-z ]+)",
        text,
        flags=re.IGNORECASE
    )

    if pet_match:
        pet_name = pet_match.group(1).strip()
        egg_names = pet_match.group(2).strip()
        rarity = pet_match.group(3).strip()

        facts.append(
            make_external_fact(
                article=article,
                text=pet_match.group(0).strip(),
                summary_ru=(
                    f"Из {egg_names} теперь можно "
                    f"получить питомца {pet_name} "
                    f"редкости {rarity}."
                ),
                kind="pets",
                value=8
            )
        )

    task_match = re.search(
        r"Bring the Mysterious Stranger\s+"
        r"(\d+) Bundles of Forks\s+"
        r"in exchange for\s+(\d+) Bucks",
        text,
        flags=re.IGNORECASE
    )

    if task_match:
        bundle_count = task_match.group(1)
        bucks_count = task_match.group(2)

        facts.append(
            make_external_fact(
                article=article,
                text=task_match.group(0),
                summary_ru=(
                    "У Mysterious Stranger можно "
                    f"обменять {bundle_count} связок "
                    f"вилок на {bucks_count} Bucks."
                ),
                kind="quests",
                value=8
            )
        )

    return facts


def extract_external_facts(
    game,
    article,
    now=None
):
    if not is_fresh_article(
        article,
        now=now
    ):
        return []

    facts = []

    title_fact = build_title_fact(
        game,
        article
    )

    if title_fact:
        facts.append(
            title_fact
        )

    if game == "Adopt Me!":
        facts.extend(
            extract_adopt_me_facts(
                article
            )
        )

    facts.sort(
        key=lambda item: item["value"],
        reverse=True
    )

    return facts
