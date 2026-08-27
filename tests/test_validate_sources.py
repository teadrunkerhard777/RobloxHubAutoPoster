import unittest

import validate_sources


class ValidateSourcesTests(unittest.TestCase):
    def test_project_registry_is_consistent(self):
        games = validate_sources.load_json(validate_sources.GAMES_FILE)
        sources = validate_sources.load_json(validate_sources.SOURCES_FILE)
        names = {game["name"] for game in games}

        errors = validate_sources.validate_registry(
            games,
            sources,
        )
        errors.extend(validate_sources.validate_content_files(names))

        self.assertEqual(errors, [])

    def test_rejects_missing_official_source(self):
        games = [
            {
                "name": "Example Game",
                "universe_id": 1,
            }
        ]

        errors = validate_sources.validate_registry(
            games,
            {},
        )

        self.assertTrue(any("Нет источников" in error for error in errors))


if __name__ == "__main__":
    unittest.main()
