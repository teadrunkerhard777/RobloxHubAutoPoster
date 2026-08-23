import json
import random
from pathlib import Path

IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}


def load_history(filename):
    try:
        with open(filename, "r", encoding="utf-8") as file:
            return json.load(file)
    except FileNotFoundError:
        return []


def save_history(filename, history):
    with open(filename, "w", encoding="utf-8") as file:
        json.dump(history, file, ensure_ascii=False, indent=2)


def find_images(directory):
    image_directory = Path(directory)

    if not image_directory.exists():
        return []

    return sorted(
        path.as_posix()
        for path in image_directory.rglob("*")
        if path.is_file() and path.suffix.lower() in IMAGE_EXTENSIONS
    )


def select_daily_image(
    directory,
    history_filename,
    exclude_paths=None,
):
    images = find_images(directory)

    if not images:
        return None

    history = load_history(history_filename)

    # Некоторые изображения уже могут быть запланированы
    # в других слотах того же дня. Не возвращаем их повторно,
    # даже если общий исторический цикл закончился.
    excluded_images = set(exclude_paths or [])
    eligible_images = [
        image_path for image_path in images if image_path not in excluded_images
    ]

    if not eligible_images:
        return None

    # Удаляем из истории файлы, которых больше нет в папке.
    history = [image_path for image_path in history if image_path in images]

    unused_images = [
        image_path for image_path in eligible_images if image_path not in history
    ]

    # После полного цикла начинаем новый, снова без повторов.
    if not unused_images:
        # Исключённые картинки сохраняем в истории,
        # потому что они уже используются сегодня.
        history = [
            image_path for image_path in history if image_path in excluded_images
        ]
        unused_images = eligible_images

    selected_image = random.choice(unused_images)

    history.append(selected_image)

    save_history(history_filename, history)

    return selected_image
