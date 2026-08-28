import random

from post_headings import HITS_HEADING, USEFUL_TIPS_HEADING

CURRENT_HIT_GAMES = (
    "Steal An Egg",
    "Animal Hospital (Anomaly)",
    "+1 Speed Keyboard Escape",
    "Murder Mystery 2",
)

# Временный редакционный приоритет: новые игры должны заметно появляться
# в ближайших выпусках 15:00, а не теряться среди старой истории.
PRIORITY_TIP_GAMES = set(CURRENT_HIT_GAMES)

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
    "social",
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
    "social": "🤝",
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


def validate_tip_catalog(
    tips,
    game_names,
    minimum_per_game=15,
    minimum_by_game=None,
):
    errors = []
    known_ids = set()
    minimum_by_game = minimum_by_game or {}

    for tip in tips:
        tip_id = tip.get("id")
        if tip_id in known_ids:
            errors.append(f"Повторяется id совета: {tip_id}.")
        known_ids.add(tip_id)

        if tip.get("category") not in ALLOWED_TIP_CATEGORIES:
            errors.append(
                f"Совет {tip_id}: некорректная category " f"{tip.get('category')}."
            )

    for game in sorted(game_names):
        count = sum(tip.get("game") == game for tip in tips)
        required_count = minimum_by_game.get(game, minimum_per_game)
        if count < required_count:
            errors.append(
                f"В tips.json для {game} только {count} советов; "
                f"нужно минимум {required_count}."
            )

    return errors


def build_tips_post(selected_tips, game_emojis):
    blocks = []

    for tip in selected_tips:
        game_emoji = game_emojis.get(tip["game"], "🎮")
        tip_emoji = tip.get("emoji", TIP_CATEGORY_EMOJIS[tip["category"]])
        blocks.append(f"{game_emoji} {tip['game']}\n" f"{tip_emoji} {tip['text']}")

    text = USEFUL_TIPS_HEADING + "\n\n" + "\n\n".join(blocks) + "\n\n🎮 Roblox Hub"
    games = " + ".join(tip["game"] for tip in selected_tips)
    return games, text


def choose_tips(
    tips,
    count,
    recent_games=None,
    category_history=None,
    excluded_games=None,
    priority_games=None,
    rng=None,
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

    games = sorted({tip["game"] for tip in tips if tip["game"] not in excluded_games})

    if len(games) < count:
        raise RuntimeError(f"Не удалось выбрать {count} советов по разным играм.")

    recent_set = set(recent_games)
    fresh_games = [game for game in games if game not in recent_set]
    priority_candidates = [game for game in games if game in priority_games]
    game_pool = sorted(set(fresh_games + priority_candidates))

    if len(game_pool) < count:
        game_pool = games

    def game_weight(game):
        recent_count = recent_games.count(game)
        weight = 6.0 / (4**recent_count)
        if game in priority_games:
            weight *= 3.0
        return weight

    selected_games = _weighted_sample(game_pool, count, game_weight, rng)
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
        category_fresh = [tip for tip in unused if tip.get("category") != last_category]
        candidates = category_fresh or unused
        tip = rng.choice(candidates)
        tip["used"] = True
        selected.append(tip)

    return selected


def choose_hit_game(games=CURRENT_HIT_GAMES, recent_games=None, rng=None):
    """Выбирает игру для 19:00 без повтора соседнего выпуска."""

    if recent_games is None:
        recent_games = []
    if rng is None:
        rng = random

    candidates = list(games)
    if recent_games and len(candidates) > 1:
        candidates = [game for game in candidates if game != recent_games[-1]]

    if not candidates:
        raise RuntimeError("Нет игр для рубрики Новинки и хиты Roblox.")

    return rng.choice(candidates)


def choose_tips_for_game(tips, game, count=3, rng=None):
    """Берёт разные советы одной игры, соблюдая полный цикл used."""

    if rng is None:
        rng = random

    validate_tip_categories(tips)
    game_tips = [tip for tip in tips if tip.get("game") == game]

    if len(game_tips) < count:
        raise RuntimeError(f"Для {game} недостаточно советов: {len(game_tips)}.")

    selected = []

    while len(selected) < count:
        unused = [
            tip
            for tip in game_tips
            if not tip.get("used", False)
            and tip.get("id") not in {item.get("id") for item in selected}
        ]

        if not unused:
            # Новый цикл начинается только после полного расходования игры.
            for tip in game_tips:
                tip["used"] = False
            unused = [
                tip
                for tip in game_tips
                if tip.get("id") not in {item.get("id") for item in selected}
            ]

        tip = rng.choice(unused)
        tip["used"] = True
        selected.append(tip)

    return selected


def build_hits_post(game, description, selected_tips, game_emojis):
    """Собирает единый формат ежедневной рубрики 19:00."""

    if len(selected_tips) != 3:
        raise ValueError("Для Новинок и хитов нужно ровно три совета.")
    if any(tip.get("game") != game for tip in selected_tips):
        raise ValueError("Все советы выпуска должны относиться к выбранной игре.")
    if len({tip.get("id") for tip in selected_tips}) != 3:
        raise ValueError("Советы выпуска должны быть разными.")

    game_emoji = game_emojis.get(game, "🎮")
    tip_lines = []

    for tip in selected_tips:
        tip_emoji = tip.get("emoji", TIP_CATEGORY_EMOJIS[tip["category"]])
        tip_lines.append(f"{tip_emoji} {tip['text']}")

    text = (
        f"{HITS_HEADING}\n\n"
        f"{game_emoji} {game}\n\n"
        f"🎮 Что за игра?\n{description}\n\n"
        + "\n\n".join(tip_lines)
        + "\n\n🎮 Roblox Hub"
    )

    return game, text
