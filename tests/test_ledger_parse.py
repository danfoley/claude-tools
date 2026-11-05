import unittest

import ledger_parse
from statuses import canonical_status

BODY = "\n## Code dial\n- PHP: rung 1, clean streak 0\n\n# Concept ledger\n\n### a\n- status: Learning \n"


class LedgerParseTest(unittest.TestCase):
    def test_a_byte_order_mark_does_not_hide_the_stage(self):
        header = ledger_parse.parse_ledger("﻿stage: 3\n" + BODY)["header"]
        self.assertEqual(header["stage"], "3")

    def test_windows_line_endings_give_the_same_result(self):
        unix = ledger_parse.parse_ledger("stage: 3\n" + BODY)
        windows = ledger_parse.parse_ledger(("stage: 3\n" + BODY).replace("\n", "\r\n"))
        self.assertEqual(unix, windows)

    def test_a_header_line_without_a_space_after_the_colon_is_read(self):
        self.assertEqual(ledger_parse.parse_ledger("stage:3\n" + BODY)["header"]["stage"], "3")

    def test_line_separator_characters_inside_text_do_not_split_lines(self):
        text = "stage: 3\n" + BODY + "- in the learner's words: one two\x0cthree\n"
        self.assertEqual(ledger_parse.parse_ledger(text)["concepts"][0]["words"], "one two\x0cthree")

    def test_status_is_read_case_and_space_insensitively(self):
        self.assertEqual(ledger_parse.parse_ledger("stage: 3\n" + BODY)["concepts"][0]["status"], "learning")
        self.assertEqual(canonical_status(" Getting It "), "getting it")

    def test_each_example_carries_its_language_or_an_empty_string(self):
        examples = (
            "- examples:\n"
            "  - tagged | what: w | where: x | why: y\n    lang: Rust\n    code: a.rs:1\n    > fn a() {}\n"
            "  - untagged | what: w | where: x | why: y\n    code: b.php:1\n    > $b;\n"
        )
        concept = ledger_parse.parse_ledger("stage: 3\n" + BODY + examples)["concepts"][0]
        self.assertEqual(concept["exampleLanguages"], ["Rust", ""])
        self.assertEqual(concept["exampleCode"][0]["path"], "a.rs")


if __name__ == "__main__":
    unittest.main()
