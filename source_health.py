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
