import subprocess
import sys


STEPS = [
    "generate_news.py",
    "verify_news.py",
    "build_news_post.py",
    "format_news_ru.py",
    "generate_posts.py"
]


def run_step(filename):
    print()
    print("=" * 50)
    print(f"Запуск: {filename}")
    print("=" * 50)

    result = subprocess.run(
        [sys.executable, filename],
        check=False
    )

    if result.returncode != 0:
        print()
        print(
            f"ОШИБКА: {filename} завершился "
            f"с кодом {result.returncode}"
        )

        raise SystemExit(
            result.returncode
        )

    print(
        f"Готово: {filename}"
    )


for step in STEPS:
    run_step(step)


print()
print("=" * 50)
print("Ежедневная очередь Roblox Hub подготовлена.")
print("=" * 50)
print()
print("Результат: posts.json")
