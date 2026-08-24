import random


PRIORITY_TIP_GAMES = {
    "Steal a Brainrot",
    "99 Nights in the Forest"
}

ALLOWED_TIP_CATEGORIES = {
    "survival",
    "combat",
    "economy",
    "collection",
    "exploration",
    "items",
    "mechanics",
    "strategy",
    "building",
    "social"
}

TIP_CATEGORY_EMOJIS = {
    "survival": "🔥",
    "combat": "⚔️",
    "economy": "💰",
    "collection": "📋",
    "exploration": "🔍",
    "items": "🎒",
    "mechanics": "⚙️",
    "strategy": "🎯",
    "building": "🏗️",
    "social": "🤝"
}


def _weighted_sample(values, count, weight_for, rng):
    remaining = list(values)
    selected = []

    while remaining and len(selected) < count:
        weights = [max(float(weight_for(value)), 0.0) for value in remaining]
        total = sum(weights)

        if total <= 0:
            index = rng.randrange(len(remaining))
        else:
            target = rng.random() * total
            index = len(remaining) - 1

            for candidate_index, weight in enumerate(weights):
                target -= weight
                if target <= 0:
                    index = candidate_index
                    break

        selected.append(remaining.pop(index))

    return selected


def _last_category(category_history, game):
    value = category_history.get(game)

    if isinstance(value, list):
        return value[-1] if value else None

    return value


def validate_tip_categories(tips):
    for tip in tips:
        category = tip.get("category")

        if category not in ALLOWED_TIP_CATEGORIES:
            raise ValueError(
                f"У совета {tip.get('id')} некорректная category: {category}"
            )


def validate_tip_catalog(tips, game_names, minimum_per_game=15):
    errors = []
    known_ids = set()

    for tip in tips:
        tip_id = tip.get("id")
        if tip_id in known_ids:
            errors.append(f"Повторяется id совета: {tip_id}.")
        known_ids.add(tip_id)

        if tip.get("category") not in ALLOWED_TIP_CATEGORIES:
            errors.append(
                f"Совет {tip_id}: некорректная category "
                f"{tip.get('category')}."
            )

    for game in sorted(game_names):
        count = sum(tip.get("game") == game for tip in tips)
        if count < minimum_per_game:
            errors.append(
                f"В tips.json для {game} только {count} советов; "
                f"нужно минимум {minimum_per_game}."
            )

    return errors


def build_tips_post(selected_tips, game_emojis):
    blocks = []

    for tip in selected_tips:
        game_emoji = game_emojis.get(tip["game"], "🎮")
        category_emoji = TIP_CATEGORY_EMOJIS[tip["category"]]
        blocks.append(
            f"{game_emoji} {tip['game']}\n"
            f"{category_emoji} {tip['text']}"
        )

    text = (
        "💡 ПОЛЕЗНО ЗНАТЬ\n\n"
        + "\n\n".join(blocks)
        + "\n\n🎮 Roblox Hub"
    )
    games = " + ".join(tip["game"] for tip in selected_tips)
    return games, text


def choose_tips(
    tips,
    count,
    recent_games=None,
    category_history=None,
    excluded_games=None,
    priority_games=None,
    rng=None
):
    if recent_games is None:
        recent_games = []
    if category_history is None:
        category_history = {}
    if excluded_games is None:
        excluded_games = set()
    if priority_games is None:
        priority_games = PRIORITY_TIP_GAMES
    if rng is None:
        rng = random

    validate_tip_categories(tips)

    games = sorted({
        tip["game"]
        for tip in tips
        if tip["game"] not in excluded_games
    })

    if len(games) < count:
        raise RuntimeError(
            f"Не удалось выбрать {count} советов по разным играм."
        )

    recent_set = set(recent_games)
    fresh_games = [game for game in games if game not in recent_set]
    game_pool = fresh_games if len(fresh_games) >= count else games

    def game_weight(game):
        recent_count = recent_games.count(game)
        weight = 6.0 / (4 ** recent_count)
        if game in priority_games:
            weight *= 3.0
        return weight

    selected_games = _weighted_sample(
        game_pool,
        count,
        game_weight,
        rng
    )
    selected = []

    for game in selected_games:
        game_tips = [tip for tip in tips if tip["game"] == game]
        unused = [tip for tip in game_tips if not tip.get("used", False)]

        # Каждый совет игры должен пройти полный круг. Сбрасываем used
        # только когда у конкретной игры не осталось вариантов.
        if not unused:
            for tip in game_tips:
                tip["used"] = False
            unused = list(game_tips)

        last_category = _last_category(category_history, game)
        category_fresh = [
            tip
            for tip in unused
            if tip.get("category") != last_category
        ]
        candidates = category_fresh or unused
        tip = rng.choice(candidates)
        tip["used"] = True
        selected.append(tip)

    return selected
