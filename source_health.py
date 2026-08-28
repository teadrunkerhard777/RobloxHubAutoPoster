"""Единые статусы и агрегированная диагностика новостных источников."""

FOUND_VERIFIED = "FOUND_VERIFIED"
FOUND_REJECTED = "FOUND_REJECTED"
SOURCE_UNAVAILABLE = "SOURCE_UNAVAILABLE"
SOURCE_STALE = "SOURCE_STALE"
EXTRACTION_FAILED = "EXTRACTION_FAILED"
NO_NEW_CONTENT = "NO_NEW_CONTENT"
ALREADY_USED = "ALREADY_USED"


def summarize_source_health(candidates):
    """Считает этапы потери материалов по diagnostics всех игр."""

    diagnostics = [
        diagnostic
        for candidate in candidates
        for diagnostic in candidate.get("source_diagnostics", [])
    ]

    return {
        "sources_checked": len(diagnostics),
        "available": sum(
            diagnostic.get("available") is True for diagnostic in diagnostics
        ),
        "unavailable": sum(
            diagnostic.get("result_code") == SOURCE_UNAVAILABLE
            for diagnostic in diagnostics
        ),
        "stale": sum(
            diagnostic.get("result_code") == SOURCE_STALE for diagnostic in diagnostics
        ),
        "publications_found": sum(
            diagnostic.get("article_found") is True for diagnostic in diagnostics
        ),
        "extraction_success": sum(
            diagnostic.get("extraction_success") is True for diagnostic in diagnostics
        ),
        "extraction_failed": sum(
            diagnostic.get("result_code") == EXTRACTION_FAILED
            for diagnostic in diagnostics
        ),
        "verification_passed": sum(
            diagnostic.get("result_code") == FOUND_VERIFIED
            for diagnostic in diagnostics
        ),
        "verification_rejected": sum(
            diagnostic.get("result_code")
            in {
                FOUND_REJECTED,
                SOURCE_STALE,
                EXTRACTION_FAILED,
                ALREADY_USED,
            }
            for diagnostic in diagnostics
        ),
    }


def print_source_health_report(candidates, title="NEWS SOURCE HEALTH"):
    """Печатает общий health и короткий маршрут каждого источника."""

    summary = summarize_source_health(candidates)

    print()
    print(f"=== {title} ===")
    print()
    print("Источников проверено:", summary["sources_checked"])
    print("Работают:", summary["available"])
    print("Недоступны:", summary["unavailable"])
    print("Устарели:", summary["stale"])
    print()
    print("Публикаций найдено:", summary["publications_found"])
    print("Extraction успешен:", summary["extraction_success"])
    print("Extraction failed:", summary["extraction_failed"])
    print("Прошли verification:", summary["verification_passed"])
    print("Отклонены verification:", summary["verification_rejected"])

    for candidate in candidates:
        print()
        print(candidate.get("game", "?"))

        for diagnostic in candidate.get("source_diagnostics", []):
            code = diagnostic.get("result_code", NO_NEW_CONTENT)
            marker = "✓" if code == FOUND_VERIFIED else "✗"
            print(
                f"  {marker} {diagnostic.get('source_type', '?')}: "
                f"{code} — {diagnostic.get('reason', '')}"
            )


def configured_automated_routes(config):
    """Returns only routes the pipeline can actually inspect for dated content."""

    routes = ["official_game_description"]
    if config.get("roblox_group_id"):
        routes.append("official_roblox_group")
    elif config.get("roblox_creator_url"):
        routes.append("official_roblox_creator")
    if config.get("news_url"):
        routes.append("official_news_website")
    if config.get("youtube_feed_url"):
        routes.append("official_youtube_feed")
    return routes


def summarize_pool_health(candidates, source_registry):
    """Reports configured and live-working routes separately for each pool."""

    by_game = {candidate.get("game"): candidate for candidate in candidates}
    result = {"active": [], "legacy": []}

    for game, config in source_registry.items():
        pool = config.get("pool", "legacy")
        routes = configured_automated_routes(config)
        diagnostics = by_game.get(game, {}).get("source_diagnostics", [])
        working_types = {
            item.get("source_type")
            for item in diagnostics
            if item.get("available") is True
        }
        result.setdefault(pool, []).append(
            {
                "game": game,
                "routes": routes,
                "working_routes": [route for route in routes if route in working_types],
            }
        )

    return result


def print_pool_health_report(candidates, source_registry):
    summary = summarize_pool_health(candidates, source_registry)
    print()
    print("=== ACTIVE ROBLOX NEWS POOL ===")
    for entry in summary.get("active", []):
        print()
        print(entry["game"])
        print("sources:", len(entry["routes"]))
        print("working:", len(entry["working_routes"]))

    active = summary.get("active", [])
    legacy = summary.get("legacy", [])
    print()
    print("Active games:", len(active))
    print("Active source routes:", sum(len(entry["routes"]) for entry in active))
    print("Working routes:", sum(len(entry["working_routes"]) for entry in active))
    print("Legacy games:", len(legacy))
    print("Legacy routes:", sum(len(entry["routes"]) for entry in legacy))
