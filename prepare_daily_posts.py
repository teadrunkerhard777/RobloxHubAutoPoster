import os
import subprocess
import sys

STEPS = [
    "validate_sources.py",
    "fetch_external_news.py",
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

    # Если Supercell был недоступен, не позволяем общему
    # генератору использовать старый Brawl latest changes.
    if step == "generate_posts.py" and not brawl_monitor_available:
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
