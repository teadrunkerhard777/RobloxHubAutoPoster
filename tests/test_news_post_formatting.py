import unittest

from news_post_formatting import (
    compact_long_enumeration,
    format_fact_paragraph,
    join_fact_paragraphs
)


class NewsPostFormattingTests(unittest.TestCase):
    def test_compacts_long_item_enumeration(self):
        fact = {"kind": "items"}
        text = (
            "Для смотрителя добавили пусковую установку со "
            "слезоточивым газом, сканирующую палочку, сканер "
            "безопасности, наручники, пистолет, прожектор и "
            "сигнализацию."
        )

        compact = compact_long_enumeration(text, fact)

        self.assertEqual(
            compact,
            "Для смотрителя добавили новые инструменты и "
            "оборудование: наручники, сканеры, прожектор, "
            "сигнализацию и другое."
        )
        self.assertNotIn("пистолет", compact)
        self.assertNotIn("пусковую установку", compact)

    def test_joins_game_facts_as_short_paragraphs(self):
        paragraphs = [
            format_fact_paragraph(
                {"kind": "locations"},
                "В игре появилась новая локация — тюрьма."
            ),
            format_fact_paragraph(
                {"kind": "items"},
                "Для смотрителя добавили новые инструменты."
            ),
            format_fact_paragraph(
                {"kind": "vehicle"},
                "В игру добавили тюремный автобус."
            )
        ]

        block = join_fact_paragraphs(paragraphs)

        self.assertEqual(len(block.split("\n\n")), 3)
        self.assertIn("\n\n👮 ", block)
        self.assertTrue(block.endswith("🚌 Ещё появился тюремный автобус."))
        self.assertNotIn(". 👮", block)


if __name__ == "__main__":
    unittest.main()
