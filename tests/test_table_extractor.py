import io
import tempfile
import unittest
from argparse import Namespace
from contextlib import redirect_stdout
from pathlib import Path

import table_extractor


class TableExtractorTests(unittest.TestCase):
    def test_sanitize_cell(self):
        self.assertEqual(table_extractor.sanitize_cell(None), "")
        self.assertEqual(table_extractor.sanitize_cell(" a\r\n b  c "), "a b c")

    def test_clean_table_rectangular(self):
        raw = [["A", "B"], ["1"], [None, "3", "4"]]
        cleaned = table_extractor.clean_table(raw)
        self.assertEqual(cleaned, [["A", "B", ""], ["1", "", ""], ["", "3", "4"]])

    def test_preview_table_prints_rows(self):
        output = io.StringIO()
        table = [["h1", "h2"], ["v1", "v2"], ["x", "y"]]
        with redirect_stdout(output):
            table_extractor.preview_table(table, 2)
        text = output.getvalue()
        self.assertIn("preview", text)
        self.assertIn("h1", text)
        self.assertIn("... (1 more row(s))", text)

    def test_quality_filter_flags_single_blob_table(self):
        args = Namespace(
            min_rows=2,
            min_cols=2,
            min_non_empty_cells=4,
            min_alpha_ratio=0.1,
            max_single_cell_ratio=0.9,
        )
        noisy = [["very long text " * 50, ""], ["", ""]]
        ok, reason = table_extractor.is_quality_table(noisy, args)
        self.assertFalse(ok)
        self.assertIn("non_empty", reason)

    def test_gather_pdf_files_recursive(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "a.pdf").write_text("x")
            sub = root / "sub"
            sub.mkdir()
            (sub / "b.pdf").write_text("y")

            non_recursive = table_extractor.gather_pdf_files([str(root)], recursive=False)
            recursive = table_extractor.gather_pdf_files([str(root)], recursive=True)

            self.assertEqual(len(non_recursive), 1)
            self.assertEqual(len(recursive), 2)

    def test_main_rejects_invalid_numeric_args(self):
        self.assertEqual(table_extractor.main([".", "--preview-rows", "-2"]), 1)
        self.assertEqual(table_extractor.main([".", "--min-alpha-ratio", "2"]), 1)


if __name__ == "__main__":
    unittest.main()
