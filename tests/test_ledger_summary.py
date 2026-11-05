import unittest

import ledger_summary

HEADER = """stage: 2
stage-since: 2026-10-26
primary-language: PHP
viewer: on

## Code dial
- PHP: rung 1, clean streak 0
- Python: rung 1, clean streak 0

# Concept ledger
"""


def concept(name, status, words="in my words", recall="a recall question", examples=1):
    entry = (
        f"### {name}\n- status: {status}\n- last verified: 2026-10-24\n"
        f"- in the learner's words: {words}\n- recall question: {recall}\n"
        "- examples:\n"
    )
    for number in range(examples):
        entry += (
            f"  - example {number} | what: {'x' * 400} | where: y | why: z\n"
            "    lang: PHP\n    code: a.php:1\n    >> $code;\n"
        )
    return entry


def concept_applied_in(name, languages):
    applied_lines = "".join(f"- applied in {language}: how it looks there\n" for language in languages)
    return concept(name, "learning").replace("- examples:\n", applied_lines + "- examples:\n")


def ledger_of(*concepts):
    return HEADER + "\n".join(concepts)


class LedgerSummaryTest(unittest.TestCase):
    def test_keeps_the_header_and_code_dial(self):
        summary = ledger_summary.summarise(ledger_of(concept("idempotency", "learning")))
        self.assertIn("stage: 2", summary)
        self.assertIn("primary-language: PHP", summary)
        self.assertIn("- PHP: rung 1, clean streak 0", summary)

    def test_lists_every_concept_with_its_status(self):
        concepts = ledger_of(concept("idempotency", "learning"), concept("checkpointing", "solid"))
        summary = ledger_summary.summarise(concepts)
        self.assertIn("idempotency", summary)
        self.assertIn("checkpointing", summary)
        self.assertRegex(summary, r"idempotency.*learning")
        self.assertRegex(summary, r"checkpointing.*solid")

    def test_leaves_out_examples_and_code_snapshots(self):
        summary = ledger_summary.summarise(ledger_of(concept("idempotency", "learning", examples=3)))
        self.assertNotIn("example 0", summary)
        self.assertNotIn("a.php:1", summary)

    def test_keeps_words_and_recall_question_for_concepts_still_being_learned(self):
        learning = concept("idempotency", "learning", words="same twice", recall="what stops a resend?")
        summary = ledger_summary.summarise(ledger_of(learning))
        self.assertIn("same twice", summary)
        self.assertIn("what stops a resend?", summary)

    def test_shortens_concepts_that_are_getting_it_or_solid_to_one_short_line(self):
        solid = concept("checkpointing", "solid", words="saves progress", recall="why?")
        summary = ledger_summary.summarise(ledger_of(solid))
        self.assertNotIn("saves progress", summary)
        self.assertNotIn("why?", summary)

    def test_says_where_the_full_entries_are(self):
        summary = ledger_summary.summarise(ledger_of(concept("idempotency", "learning")))
        self.assertIn("full entry", summary.lower())

    def test_a_large_ledger_stays_under_the_budget_with_every_concept_present(self):
        names = [f"concept-{number}" for number in range(120)]
        statuses = {name: "getting it" if number % 2 else "learning" for number, name in enumerate(names)}
        big = ledger_of(*[concept(name, status, examples=4) for name, status in statuses.items()])
        summary = ledger_summary.summarise(big)
        self.assertLess(len(summary), ledger_summary.DEFAULT_BUDGET_CHARACTERS)
        for name in names:
            self.assertIn(name, summary)

    def test_a_ledger_with_no_concepts_still_gives_the_header(self):
        self.assertIn("stage: 2", ledger_summary.summarise(HEADER))

    def test_the_summary_never_exceeds_the_budget_it_is_given(self):
        for budget in (600, 1500, 3000):
            for count in (1, 30, 400):
                with self.subTest(budget=budget, count=count):
                    big = ledger_of(*[concept(f"concept-{n}", "learning" if n % 3 else "solid") for n in range(count)])
                    self.assertLessEqual(len(ledger_summary.summarise(big, budget)), budget)

    def test_when_names_have_to_be_dropped_it_says_how_many_and_where_to_look(self):
        big = ledger_of(*[concept(f"concept-{n}", "solid") for n in range(400)])
        summary = ledger_summary.summarise(big, 1500)
        self.assertRegex(summary, r"\+\d+ more")
        self.assertIn("400 concepts", summary)

    def test_learning_concepts_are_kept_before_solid_ones_when_space_runs_out(self):
        concepts = [concept(f"solid-{n}", "solid") for n in range(200)] + [concept("still-learning", "learning")]
        self.assertIn("still-learning", ledger_summary.summarise(ledger_of(*concepts), 1200))

    def test_one_very_long_entry_does_not_strip_the_others(self):
        long_entry = concept("a", "learning", words="x" * 20000)
        summary = ledger_summary.summarise(ledger_of(long_entry, concept("b", "learning", words="kept")))
        self.assertIn("kept", summary)
        self.assertLess(len(summary), 2000)

    def test_control_characters_are_removed(self):
        summary = ledger_summary.summarise(ledger_of(concept("a", "learning", words="bad\x01\x0c\x1b[31m\ttext")))
        self.assertNotRegex(summary, r"[\x00-\x08\x0b-\x1f\x7f]")
        self.assertNotIn("\t", summary)

    def test_unreadable_bytes_in_the_file_still_give_a_summary(self):
        text = ledger_of(concept("idempotency", "learning")).encode() + b"\xff\xfe"
        self.assertIn("idempotency", ledger_summary.summarise_bytes(text, 3000))

    def test_a_large_file_with_no_concepts_says_so_loudly(self):
        summary = ledger_summary.summarise(HEADER + "## idempotency\n" + "text " * 2000)
        self.assertIn("WARNING", summary)

    def test_warns_about_a_language_used_in_a_concept_but_missing_from_the_code_dial(self):
        summary = ledger_summary.summarise(ledger_of(concept_applied_in("idempotency", ["PHP", "Go"])))
        self.assertIn("WARNING: used in the ledger but not in the code dial: Go", summary)

    def test_warns_how_many_examples_have_no_language_line(self):
        untagged = "  - a | what: w | where: x | why: y\n    code: a.json:1\n    > {}\n"
        tagged = "  - b | what: w | where: x | why: y\n    lang: PHP\n    code: b.php:1\n    > $b;\n"
        examples = untagged + untagged + tagged
        summary = ledger_summary.summarise(HEADER + "### c\n- status: learning\n- examples:\n" + examples)
        self.assertIn("WARNING: 2 examples have no lang: line", summary)

    def test_does_not_warn_when_every_example_has_a_language_line(self):
        tagged = "  - b | what: w | where: x | why: y\n    lang: PHP\n    code: b.php:1\n    > $b;\n"
        summary = ledger_summary.summarise(HEADER + "### c\n- status: learning\n- examples:\n" + tagged)
        self.assertNotIn("have no lang: line", summary)

    def test_does_not_warn_when_every_used_language_is_in_the_code_dial(self):
        summary = ledger_summary.summarise(ledger_of(concept_applied_in("idempotency", ["php", "Python"])))
        self.assertNotIn("not in the code dial", summary)


if __name__ == "__main__":
    unittest.main()
