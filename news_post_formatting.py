import re


def _enumeration_parts(text):
    if ":" in text:
        body = text.split(":", 1)[1]
    else:
        match = re.search(r"\bдобавили\s+(.+)", text, flags=re.IGNORECASE)
        if not match:
            return []
        body = match.group(1)

    body = body.strip().rstrip(".")
    return [part.strip() for part in re.split(r",\s*|\s+и\s+", body) if part.strip()]


def compact_long_enumeration(text, fact):
    parts = _enumeration_parts(text)

    if len(parts) <= 5:
        return text

    lower = text.lower()

    if fact.get("kind") == "items":
        grouped = []

        if "наручник" in lower:
            grouped.append("наручники")
        if "сканирующ" in lower or "сканер" in lower:
            grouped.append("сканеры")
        if "прожектор" in lower:
            grouped.append("прожектор")
        if "сигнализац" in lower:
            grouped.append("сигнализацию")

        if len(grouped) >= 3:
            audience = "Для смотрителя " if "для смотрителя" in lower else "В игре "
            return (
                f"{audience}добавили новые инструменты и оборудование: "
                f"{', '.join(grouped)} и другое."
            )

    kept = parts[:4]
    prefix = text.split(":", 1)[0] if ":" in text else "Добавили"
    return f"{prefix}: {', '.join(kept)} и другое."


def format_fact_paragraph(fact, text):
    text = compact_long_enumeration(text.strip(), fact)
    kind = fact.get("kind", "")
    lower = text.lower()

    # Специализированный extractor уже выбрал нейтральный маркер списка.
    # Не ставим перед ним второй emoji из общей таблицы категорий.
    if text.startswith("🔹"):
        return text

    if kind == "locations":
        text = text.replace("новая локация — тюрьма", "новая локация, тюрьма")

    if kind == "vehicle" and "тюремный автобус" in lower:
        return "🚌 Ещё появился тюремный автобус."

    emoji = None

    if kind == "items":
        emoji = "👮" if "смотрителя" in lower else "🧰"
    elif kind == "mechanics_storage":
        emoji = "🎒"
    elif kind == "vehicle":
        emoji = "🚗"
    elif kind == "quests":
        emoji = "🎯"
    elif kind == "event":
        emoji = "🎉"

    if emoji and not text.startswith(emoji):
        return f"{emoji} {text}"

    return text


def join_fact_paragraphs(paragraphs):
    return "\n\n".join(
        paragraph.strip() for paragraph in paragraphs if paragraph and paragraph.strip()
    )
