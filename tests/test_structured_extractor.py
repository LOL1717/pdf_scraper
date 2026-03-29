import unittest

import structured_extractor


class StructuredExtractorTests(unittest.TestCase):
    def test_empty_structure(self):
        out = structured_extractor.extract_structured_data({})
        self.assertIn("metadata", out)
        self.assertEqual(out["tables"], [])

    def test_extract_meaningful_table_and_result(self):
        data = {
            "metadata": {"title": "Test Paper", "authors": ["A", "B"], "year": 2025},
            "text": [
                "We address the problem of noisy extraction.",
                "Objective: evaluate our model on the XYZ dataset.",
                "Baseline methods include Method-A and Method-B.",
            ],
            "tables": [
                {
                    "caption": "Main results",
                    "columns": ["Method", "Accuracy (%)"],
                    "rows": [["Method-A", "81.2 %"], ["Method-B", "83.5%"]],
                }
            ],
        }

        out = structured_extractor.extract_structured_data(data)
        self.assertEqual(out["metadata"]["title"], "Test Paper")
        self.assertEqual(len(out["tables"]), 1)
        self.assertEqual(out["results"]["best_method"], "Method-B")
        self.assertIn("accuracy", out["experiment"]["metrics"])


if __name__ == "__main__":
    unittest.main()
