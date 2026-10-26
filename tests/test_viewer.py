import http.client
import json
import os
import sys
import tempfile
import threading
import unittest
import unittest.mock
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "understand-first" / "scripts"))

import viewer

LEDGER = """stage: 3
stage-since: 2026-10-01
primary-language: PHP

## Code dial
- PHP: rung 2, clean streak 1
- TypeScript: rung 1, clean streak 0

# Concept ledger

### idempotency
- status: shaky
- last verified: 2026-10-24
- in the learner's words: doing it twice is safe
- recall question: what makes a retry safe?
- applied in PHP: a dispatched-at column per recipient
- applied in TypeScript: an idempotency key header
- examples:
  - email digest (PR 101): send first, record last
  - webhook (PR 117): skip stored ids
"""
WORK = """### PR 449462: bulk messages sent in batch jobs
- kind: walked through
- date: 2026-10-27
- source: PR 449462
- understanding: partly
- problem: a retry of the whole send re-emailed people who already got it
- solution: the parent job only plans; small batch jobs send and mark recipients dispatched
- concepts:
  - idempotency: a redelivered batch skips recipients already dispatched
  - batching: the unit of retry became 50 recipients
- gaps: what happens when the parent fails while enqueuing batches

### Renew the wildcard certificate
- kind: built
- date: 2026-10-20
- understanding: maybe
- problem: the local certificate expired
- solution: issued a new one and replaced the encrypted files
- concepts:
  - certificate-chains: the intermediate must be replaced with the leaf
"""
EVENT = json.dumps({"date": "2026-10-24", "time": "13:56", "event": "gate-retry", "concept": "idempotency", "note": ""})


class ViewerTest(unittest.TestCase):
    def setUp(self):
        self.directory = Path(tempfile.mkdtemp())
        (self.directory / "ledger.md").write_text(LEDGER)
        (self.directory / "events.jsonl").write_text(EVENT + "\n")
        (self.directory / "work.md").write_text(WORK)
        self.server = viewer.ViewerServer(self.directory, 0)
        threading.Thread(target=self.server.serve_forever, daemon=True).start()
        self.addCleanup(self.stop_server)

    def stop_server(self):
        self.server.shutdown()
        self.server.server_close()

    def request(self, method, path, body=None, headers=None):
        connection = http.client.HTTPConnection("127.0.0.1", self.server.server_port, timeout=5)
        connection.request(method, path, body=body, headers=headers or {})
        response = connection.getresponse()
        return response.status, response.read().decode()

    def act(self, payload, token=None, extra_headers=None):
        headers = {"Content-Type": "application/json", "X-Token": token or self.server.token}
        headers.update(extra_headers or {})
        status, text = self.request("POST", "/api/action", json.dumps(payload), headers)
        return status, json.loads(text)

    def ledger_text(self):
        return (self.directory / "ledger.md").read_text()

    def logged_events(self):
        return viewer.parse_events((self.directory / "events.jsonl").read_text())

    def test_state_reports_the_ledger_and_the_events(self):
        status, text = self.request("GET", "/api/state")
        state = json.loads(text)
        self.assertEqual(status, 200)
        self.assertEqual((state["stage"], state["language"], state["statsMode"]), (3, "PHP", "terminal"))
        self.assertEqual(state["dial"], [
            {"language": "PHP", "rung": 2, "streak": 1},
            {"language": "TypeScript", "rung": 1, "streak": 0},
        ])
        self.assertEqual(state["concepts"][0]["examples"], 2)
        self.assertEqual(state["eventCount"], 1)

    def test_state_carries_the_text_of_each_concept_example(self):
        _, text = self.request("GET", "/api/state")
        concept = json.loads(text)["concepts"][0]
        self.assertEqual(concept["exampleNotes"], [
            "email digest (PR 101): send first, record last",
            "webhook (PR 117): skip stored ids",
        ])

    def test_state_reports_how_a_concept_was_applied_in_each_language(self):
        _, text = self.request("GET", "/api/state")
        concept = json.loads(text)["concepts"][0]
        self.assertEqual(concept["applied"], {
            "PHP": "a dispatched-at column per recipient",
            "TypeScript": "an idempotency key header",
        })
        self.assertEqual(concept["words"], "doing it twice is safe")

    def test_state_includes_each_piece_of_work_with_its_concepts(self):
        _, text = self.request("GET", "/api/state")
        work = json.loads(text)["work"]
        self.assertEqual([item["title"] for item in work], ["PR 449462: bulk messages sent in batch jobs", "Renew the wildcard certificate"])
        first = work[0]
        self.assertEqual((first["kind"], first["date"], first["understanding"]), ("walked through", "2026-10-27", "partly"))
        self.assertEqual(first["solution"], "the parent job only plans; small batch jobs send and mark recipients dispatched")
        self.assertEqual(first["gaps"], "what happens when the parent fails while enqueuing batches")
        self.assertEqual(first["concepts"], [
            {"name": "idempotency", "use": "a redelivered batch skips recipients already dispatched"},
            {"name": "batching", "use": "the unit of retry became 50 recipients"},
        ])

    def test_an_unknown_understanding_level_reads_as_not_assessed(self):
        _, text = self.request("GET", "/api/state")
        self.assertEqual(json.loads(text)["work"][1]["understanding"], "not assessed")

    def test_work_skipped_on_override_keeps_its_skipped_level(self):
        skipped = "\n### Hurried change\n- kind: built\n- date: 2026-10-28\n- understanding: skipped\n- gaps: skipped on override: in a hurry\n"
        (self.directory / "work.md").write_text(WORK + skipped)
        _, text = self.request("GET", "/api/state")
        last = json.loads(text)["work"][-1]
        self.assertEqual((last["understanding"], last["gaps"]), ("skipped", "skipped on override: in a hurry"))

    def test_without_a_work_log_the_state_has_no_work(self):
        (self.directory / "work.md").unlink()
        _, text = self.request("GET", "/api/state")
        self.assertEqual(json.loads(text)["work"], [])

    def test_a_request_for_another_host_is_refused(self):
        status, _ = self.request("GET", "/api/state", headers={"Host": "evil.example"})
        self.assertEqual(status, 403)

    def test_the_page_carries_the_token(self):
        status, page = self.request("GET", "/")
        self.assertEqual(status, 200)
        self.assertIn(self.server.token, page)
        self.assertNotIn("__TOKEN__", page)

    def test_a_change_without_the_token_is_refused_and_changes_nothing(self):
        status, _ = self.act({"action": "stage-down"}, token="wrong")
        self.assertEqual(status, 403)
        self.assertEqual(self.ledger_text(), LEDGER)

    def test_a_change_from_another_origin_is_refused(self):
        status, _ = self.act({"action": "stage-down"}, extra_headers={"Origin": "https://evil.example"})
        self.assertEqual(status, 403)
        status, _ = self.act({"action": "stage-down"}, extra_headers={"Sec-Fetch-Site": "cross-site"})
        self.assertEqual(status, 403)
        self.assertEqual(self.ledger_text(), LEDGER)

    def test_going_back_a_stage_edits_the_header_and_logs_it(self):
        status, answer = self.act({"action": "stage-down"})
        self.assertEqual(status, 200)
        self.assertEqual(answer["state"]["stage"], 2)
        self.assertIn("stage: 2\n", self.ledger_text())
        self.assertEqual(self.logged_events()[-1]["event"], "stage-down")
        self.assertIn("idempotency", self.ledger_text())

    def test_a_stage_cannot_go_up_or_below_one(self):
        self.assertEqual(self.act({"action": "stage-down", "to": 5})[0], 400)
        self.assertEqual(self.act({"action": "stage-down", "to": 0})[0], 400)
        self.assertEqual(self.ledger_text(), LEDGER)

    def test_reset_needs_confirmation(self):
        self.assertEqual(self.act({"action": "reset-stage"})[0], 400)
        self.assertEqual(self.act({"action": "reset-stage", "confirm": True})[0], 200)
        self.assertIn("stage: 1\n", self.ledger_text())

    def test_the_dial_goes_down_one_rung_and_stops_at_one(self):
        self.assertEqual(self.act({"action": "dial-down", "language": "PHP"})[0], 200)
        self.assertIn("- PHP: rung 1, clean streak 0", self.ledger_text())
        self.assertEqual(self.act({"action": "dial-down", "language": "PHP"})[0], 400)

    def test_a_language_change_is_logged_with_its_language(self):
        self.act({"action": "dial-down", "language": "PHP"})
        self.act({"action": "add-language", "language": "Rust"})
        logged = self.logged_events()
        self.assertEqual([(event["event"], event["language"]) for event in logged[-2:]], [("dial-down", "PHP"), ("setting-changed", "Rust")])

    def test_the_concepts_do_not_change_when_a_language_is_added(self):
        before = json.loads(self.request("GET", "/api/state")[1])["concepts"]
        self.act({"action": "add-language", "language": "Rust"})
        after = json.loads(self.request("GET", "/api/state")[1])["concepts"]
        self.assertEqual(before, after)

    def test_a_language_is_added_at_rung_one_and_bad_names_are_refused(self):
        self.assertEqual(self.act({"action": "add-language", "language": "Rust"})[0], 200)
        self.assertIn("- Rust: rung 1, clean streak 0", self.ledger_text())
        self.assertEqual(self.act({"action": "add-language", "language": "bad: name\n- x"})[0], 400)

    def test_the_primary_language_changes_and_is_added_to_the_dial(self):
        self.assertEqual(self.act({"action": "set-language", "language": "Python"})[0], 200)
        self.assertIn("primary-language: Python\n", self.ledger_text())
        self.assertIn("- Python: rung 1, clean streak 0", self.ledger_text())

    def test_an_unknown_action_is_refused(self):
        self.assertEqual(self.act({"action": "delete-everything"})[0], 400)

    def test_the_command_line_makes_the_same_change_as_the_page(self):
        with unittest.mock.patch.dict(os.environ, {"UNDERSTAND_FIRST_DATA": str(self.directory)}):
            self.assertEqual(viewer.main(["viewer.py", "act", '{"action": "stage-down"}']), 0)
            self.assertEqual(viewer.main(["viewer.py", "act", '{"action": "stage-down", "to": 9}']), 1)
            self.assertEqual(viewer.main(["viewer.py", "act", "not json"]), 2)
        self.assertIn("stage: 2\n", self.ledger_text())

    def test_publishing_to_a_hosted_page_cannot_be_turned_on_from_the_page(self):
        self.assertEqual(self.act({"action": "stats-mode-dashboard"})[0], 400)
        self.assertNotIn("stats-mode: dashboard", self.ledger_text())
        with unittest.mock.patch.dict(os.environ, {"UNDERSTAND_FIRST_DATA": str(self.directory)}):
            self.assertEqual(viewer.main(["viewer.py", "act", '{"action": "stats-mode-dashboard"}']), 0)
        self.assertIn("stats-mode: dashboard", self.ledger_text())

    def test_a_missing_header_line_is_inserted_after_the_primary_language(self):
        updated = viewer.set_header_line(LEDGER, "stats-mode", "dashboard")
        self.assertIn("primary-language: PHP\nstats-mode: dashboard\n", updated)


if __name__ == "__main__":
    unittest.main()
