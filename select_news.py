import json

PUBLISH_SCORE = 8
REVIEW_SCORE = 4


def load_json(filename, default):
    try:
        with open(filename, "r", encoding="utf-8") as file:
            return json.load(file)
    except FileNotFoundError:
        return default


def save_json(filename, data):
    with open(filename, "w", encoding="utf-8") as file:
        json.dump(data, file, ensure_ascii=False, indent=2)


def classify_candidate(candidate):
    score = candidate.get("score", 0)

    if score >= PUBLISH_SCORE:
        return "strong"

    if score >= REVIEW_SCORE:
        return "needs_verification"

    return "weak"


candidates = load_json("news_candidates.json", [])


selected_news = []


for candidate in candidates:
    category = classify_candidate(candidate)

    selected = {
        "game": candidate["game"],
        "universe_id": candidate["universe_id"],
        "updated_at": candidate["updated_at"],
        "score": candidate["score"],
        "confidence": candidate["confidence"],
        "selection_status": category,
        "description_changed": candidate["description_changed"],
        "added_lines": candidate["added_lines"],
        "keywords_in_added": candidate["keywords_in_added"],
        "keywords_in_description": candidate["keywords_in_description"],
        "sources": candidate["sources"],
    }

    selected_news.append(selected)


selected_news.sort(key=lambda item: item["score"], reverse=True)


save_json("selected_news.json", selected_news)


strong = [item for item in selected_news if item["selection_status"] == "strong"]

needs_verification = [
    item for item in selected_news if item["selection_status"] == "needs_verification"
]

weak = [item for item in selected_news if item["selection_status"] == "weak"]


print(f"Всего кандидатов: " f"{len(selected_news)}")

print(f"Сильных: " f"{len(strong)}")

print(f"Нужна проверка: " f"{len(needs_verification)}")

print(f"Слабых: " f"{len(weak)}")


print()
print("Рейтинг:")


for item in selected_news:
    print(
        f"{item['score']:>2} | " f"{item['selection_status']:<18} | " f"{item['game']}"
    )
