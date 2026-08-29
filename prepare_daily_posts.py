import json
import os
import subprocess
import sys
from datetime import datetime, timezone

STEPS = [
    "validate_sources.py",
    "fetch_external_news.py",
    "fetch_secondary_news.py",
    "generate_news.py",
    "verify_news.py",
    "build_news_post.py",
    "format_news_ru.py",
    "brawl_monitor.py",
    "generate_posts.py",
]

# Brawl зависит от доступности официального сайта Supercell.
# Его временная ошибка не должна останавливать подготовку
# основной Roblox-очереди и постов с картинками.
OPTIONAL_STEPS = {"brawl_monitor.py"}
BRAWL_LATEST_CHANGES_FILE = "data/brawl_latest_changes.json"
BRAWL_PENDING_MAX_AGE_DAYS = 7


def has_fresh_pending_brawl_news(
    filename=BRAWL_LATEST_CHANGES_FILE,
    today=None,
    max_age_days=BRAWL_PENDING_MAX_AGE_DAYS,
):
    """Checks whether a previously verified Brawl article is still pending.

    A temporary monitor failure must not discard an official article that was
    already selected after the previous day's 12:00 slot. Only explicitly
    unscheduled, official and still-fresh HIGH/MEDIUM candidates are allowed
    through this recovery path; arbitrary stale latest-changes data is not.
    """

    if today is None:
        today = datetime.now(timezone.utc).date()

    try:
        with open(filename, encoding="utf-8") as file:
            data = json.load(file)
    except (OSError, ValueError, TypeError):
        return False

    seen_urls = set()
    for field in (
        "high_priority_articles",
        "medium_priority_articles",
        "new_articles",
    ):
        for article in data.get(field, []):
            url = article.get("url")
            if not url or url in seen_urls:
                continue
            seen_urls.add(url)

            if article.get("scheduled") is True:
                continue
            if article.get("official", True) is not True:
                continue
            if article.get("priority") not in {"high", "medium"}:
                continue

            try:
                published_date = datetime.fromisoformat(
                    str(article.get("date", "")).replace("Z", "+00:00")
                ).date()
            except (TypeError, ValueError):
                continue

            age_days = (today - published_date).days
            if 0 <= age_days <= max_age_days:
                return True

    return False


def run_step(filename, optional=False, environment_overrides=None):
    """Запускает один этап и локализует сбой необязательного шага."""

    print()
    print("=" * 50)
    print(f"Запуск: {filename}")
    print("=" * 50)

    environment = os.environ.copy()
    environment.update(environment_overrides or {})

    result = subprocess.run(
        [sys.executable, filename],
        check=False,
        env=environment,
    )

    if result.returncode != 0:
        print()
        print(f"ОШИБКА: {filename} завершился " f"с кодом {result.returncode}")

        if optional:
            print(
                "Необязательный Brawl-этап пропущен; " "основная сборка продолжается."
            )
            return False

        raise SystemExit(result.returncode)

    print(f"Готово: {filename}")
    return True


brawl_monitor_available = True

for step in STEPS:
    environment_overrides = None

    # Если Supercell был недоступен, обычные старые данные не используем.
    # Исключение — уже проверенная свежая pending-новость: она должна дойти
    # до следующего свободного 12:00 даже после временного сбоя монитора.
    if (
        step == "generate_posts.py"
        and not brawl_monitor_available
        and not has_fresh_pending_brawl_news()
    ):
        environment_overrides = {"ROBLOX_HUB_SKIP_BRAWL": "1"}

    step_succeeded = run_step(
        step,
        optional=step in OPTIONAL_STEPS,
        environment_overrides=environment_overrides,
    )

    if step == "brawl_monitor.py":
        brawl_monitor_available = step_succeeded


print()
print("=" * 50)
print("Ежедневная очередь Roblox Hub подготовлена.")
print("=" * 50)
print()
print("Результат: posts.json")
