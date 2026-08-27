import unittest

from source_health import (
    EXTRACTION_FAILED,
    FOUND_VERIFIED,
    NO_NEW_CONTENT,
    SOURCE_UNAVAILABLE,
    summarize_source_health,
)


class SourceHealthTests(unittest.TestCase):
    def test_counts_source_failures_and_extraction_separately(self):
        candidates = [
            {
                "source_diagnostics": [
                    {
                        "result_code": FOUND_VERIFIED,
                        "available": True,
                        "article_found": True,
                        "extraction_success": True,
                    },
                    {
                        "result_code": EXTRACTION_FAILED,
                        "available": True,
                        "article_found": True,
                        "extraction_success": False,
                    },
                    {
                        "result_code": SOURCE_UNAVAILABLE,
                        "available": False,
                        "article_found": False,
                        "extraction_success": False,
                    },
                    {
                        "result_code": NO_NEW_CONTENT,
                        "available": True,
                        "article_found": False,
                        "extraction_success": False,
                    },
                ]
            }
        ]

        result = summarize_source_health(candidates)

        self.assertEqual(result["sources_checked"], 4)
        self.assertEqual(result["unavailable"], 1)
        self.assertEqual(result["publications_found"], 2)
        self.assertEqual(result["extraction_success"], 1)
        self.assertEqual(result["extraction_failed"], 1)
        self.assertEqual(result["verification_passed"], 1)

    def test_extraction_failed_differs_from_no_new_content(self):
        candidates = [
            {
                "source_diagnostics": [
                    {
                        "result_code": EXTRACTION_FAILED,
                        "available": True,
                        "article_found": True,
                    },
                    {
                        "result_code": NO_NEW_CONTENT,
                        "available": True,
                        "article_found": False,
                    },
                ]
            }
        ]

        result = summarize_source_health(candidates)

        self.assertEqual(result["extraction_failed"], 1)
        self.assertEqual(result["publications_found"], 1)


if __name__ == "__main__":
    unittest.main()
