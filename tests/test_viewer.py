import http.client
import json
import os
import shutil
import socket
import subprocess
import sys
import tempfile
import threading
import time
import unittest
import unittest.mock
from pathlib import Path

import viewer

PLUGIN = Path(__file__).resolve().parents[1] / "understand-first"

LEDGER = """stage: 3
stage-since: 2026-10-01
primary-language: PHP

## Code dial
- PHP: rung 2, clean streak 1
- TypeScript: rung 1, clean streak 0

# Concept ledger

### idempotency
- status: shaky
- study: partly (2026-10-30), studied but not yet used in work
- source: Idempotent Receiver | https://example.com/irp | guide | checked 2026-10-24
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

    def test_state_shows_an_old_status_name_as_its_new_name(self):
        _, text = self.request("GET", "/api/state")
        self.assertEqual(json.loads(text)["concepts"][0]["status"], "learning")

    def test_state_lists_the_published_sources_of_a_concept(self):
        _, text = self.request("GET", "/api/state")
        self.assertEqual(json.loads(text)["concepts"][0]["sources"], [{
            "title": "Idempotent Receiver",
            "url": "https://example.com/irp",
            "kind": "guide",
            "checked": "2026-10-24",
        }])

    def test_a_source_without_a_web_link_has_no_url(self):
        source = viewer.parse_source("Local notes | javascript:alert(1) | guide | checked 2026-11-05")
        self.assertEqual(source["url"], "")

    def test_an_installed_plugin_source_is_kept_as_text_without_a_url(self):
        source = viewer.parse_source("playwright-skill | plugin:playwright-skill | plugin | checked 2026-11-05")
        self.assertEqual(source, {"title": "playwright-skill", "url": "", "kind": "plugin", "checked": "2026-11-05"})

    def test_a_plain_http_link_is_kept_as_the_url(self):
        source = viewer.parse_source("Old docs | http://example.com/docs | official | checked 2026-11-05")
        self.assertEqual(source["url"], "http://example.com/docs")

    def test_extra_separators_in_a_source_are_ignored(self):
        source = viewer.parse_source("A | https://example.com | guide | checked 2026-11-05 | stray | more")
        self.assertEqual(source["checked"], "2026-11-05")

    def test_a_source_without_a_checked_date_has_an_empty_one(self):
        source = viewer.parse_source("Spec | https://example.com | standard")
        self.assertEqual((source["kind"], source["checked"]), ("standard", ""))

    def test_a_source_with_only_a_title_still_parses(self):
        self.assertEqual(viewer.parse_source("PSR-12"), {"title": "PSR-12", "url": "", "kind": "", "checked": ""})

    def test_state_carries_the_study_estimate_of_a_concept(self):
        _, text = self.request("GET", "/api/state")
        study = json.loads(text)["concepts"][0]["study"]
        self.assertEqual(study, "partly (2026-10-30), studied but not yet used in work")

    def test_state_carries_the_text_of_each_concept_example(self):
        _, text = self.request("GET", "/api/state")
        concept = json.loads(text)["concepts"][0]
        self.assertEqual(concept["exampleNotes"], [
            "email digest (PR 101): send first, record last",
            "webhook (PR 117): skip stored ids",
        ])

    def test_an_example_carries_its_code_snapshot_with_line_numbers_and_highlights(self):
        note = "digest (PR 101) | what: sends | where: the send then the delete | why: safe"
        ledger_lines = [
            "### idempotency",
            "- examples:",
            f"  - {note}",
            "    code: services/Notifier.php:41",
            "    > $this->sender->send($mail);",
            "    >> $this->messages->deleteClaimed($ids);",
        ]
        concept = viewer.parse_concepts(ledger_lines)[0]
        self.assertEqual(concept["exampleNotes"], [note])
        self.assertEqual(concept["exampleCode"], [{
            "path": "services/Notifier.php",
            "start": 41,
            "lines": [
                {"text": "$this->sender->send($mail);", "highlight": False},
                {"text": "$this->messages->deleteClaimed($ids);", "highlight": True},
            ],
        }])

    def test_an_example_without_a_snapshot_has_no_code(self):
        concept = viewer.parse_concepts(["### idempotency", "- examples:", "  - digest | where: somewhere"])[0]
        self.assertEqual(concept["exampleCode"], [None])

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
        titles = ["PR 449462: bulk messages sent in batch jobs", "Renew the wildcard certificate"]
        self.assertEqual([item["title"] for item in work], titles)
        first = work[0]
        self.assertEqual(
            (first["kind"], first["date"], first["understanding"]), ("walked through", "2026-10-27", "partly")
        )
        self.assertEqual(
            first["solution"], "the parent job only plans; small batch jobs send and mark recipients dispatched"
        )
        self.assertEqual(first["gaps"], "what happens when the parent fails while enqueuing batches")
        self.assertEqual(first["concepts"], [
            {"name": "idempotency", "use": "a redelivered batch skips recipients already dispatched"},
            {"name": "batching", "use": "the unit of retry became 50 recipients"},
        ])

    def test_an_unknown_understanding_level_reads_as_not_assessed(self):
        _, text = self.request("GET", "/api/state")
        self.assertEqual(json.loads(text)["work"][1]["understanding"], "not assessed")

    def test_work_skipped_on_override_keeps_its_skipped_level(self):
        skipped = (
            "\n### Hurried change\n- kind: built\n- date: 2026-10-28\n- understanding: skipped\n"
            "- gaps: skipped on override: in a hurry\n"
        )
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

    def test_the_page_links_a_browser_tab_icon_and_the_viewer_serves_it(self):
        _, page = self.request("GET", "/")
        self.assertIn('href="/favicon.svg"', page)
        status, icon = self.request("GET", "/favicon.svg")
        self.assertEqual(status, 200)
        self.assertTrue(icon.startswith("<svg"))

    def test_the_security_policy_lets_the_page_load_its_own_images(self):
        connection = http.client.HTTPConnection("127.0.0.1", self.server.server_port, timeout=5)
        connection.request("GET", "/")
        policy = connection.getresponse().getheader("Content-Security-Policy")
        self.assertIn("img-src 'self'", policy)

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
        self.assertEqual(
            [(event["event"], event["language"]) for event in logged[-2:]],
            [("dial-down", "PHP"), ("setting-changed", "Rust")],
        )

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

    def make_cloud_folder(self):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        return Path(folder.name)

    def current_state(self):
        return json.loads(self.request("GET", "/api/state")[1])

    def test_state_lists_the_storage_backends_and_that_none_is_chosen_yet(self):
        storage = self.current_state()["storage"]
        self.assertIsNone(storage["configured"])
        self.assertIn("folder", [backend["name"] for backend in storage["backends"]])

    def test_choosing_a_storage_backend_saves_it_and_logs_it(self):
        cloud = self.make_cloud_folder()
        choice = {"backend": "folder", "settings": {"directory": str(cloud)}}
        status, result = self.act({"action": "storage-configure", **choice})
        self.assertEqual(status, 200)
        self.assertEqual(result["state"]["storage"]["configured"], choice)
        self.assertEqual(self.logged_events()[-1]["event"], "setting-changed")
        self.assertIn("folder", self.logged_events()[-1]["note"])

    def test_choosing_an_unknown_storage_backend_is_refused_and_changes_nothing(self):
        status, result = self.act({"action": "storage-configure", "backend": "nosuch", "settings": {}})
        self.assertEqual(status, 400)
        self.assertIn("nosuch", result["message"])
        self.assertIsNone(self.current_state()["storage"]["configured"])

    def test_settings_the_backend_does_not_declare_are_refused(self):
        status, _ = self.act({"action": "storage-configure", "backend": "folder", "settings": {"colour": "red"}})
        self.assertEqual(status, 400)

    def test_storage_settings_that_are_not_text_are_refused(self):
        status, _ = self.act({"action": "storage-configure", "backend": "folder", "settings": {"directory": 5}})
        self.assertEqual(status, 400)

    def test_going_back_to_local_only_storage(self):
        cloud = self.make_cloud_folder()
        self.act({"action": "storage-configure", "backend": "folder", "settings": {"directory": str(cloud)}})
        status, result = self.act({"action": "storage-disable"})
        self.assertEqual(status, 200)
        self.assertIsNone(result["state"]["storage"]["configured"])
        self.assertEqual(self.logged_events()[-1]["event"], "setting-changed")

    def test_syncing_now_brings_the_backend_files_here(self):
        cloud = self.make_cloud_folder()
        (cloud / "sources-added.md").write_text("from the cloud\n")
        self.act({"action": "storage-configure", "backend": "folder", "settings": {"directory": str(cloud)}})
        self.assertEqual(self.act({"action": "storage-sync-now"})[0], 200)
        self.assertEqual((self.directory / "sources-added.md").read_text(), "from the cloud\n")

    def test_syncing_now_without_a_backend_is_refused(self):
        status, result = self.act({"action": "storage-sync-now"})
        self.assertEqual(status, 400)
        self.assertIn("No storage backend", result["message"])

    def test_a_storage_change_without_the_token_is_refused(self):
        status, _ = self.act({"action": "storage-disable"}, token="wrong")
        self.assertEqual(status, 403)


class SelfUpdateTest(unittest.TestCase):
    def setUp(self):
        folders = tempfile.TemporaryDirectory()
        self.addCleanup(folders.cleanup)
        self.root = Path(folders.name) / "understand-first"
        self.data = Path(folders.name) / "data"
        self.root.mkdir()
        self.data.mkdir()

    def fake_install(self, version, with_viewer=True):
        folder = self.root / version
        (folder / ".claude-plugin").mkdir(parents=True)
        (folder / ".claude-plugin" / "plugin.json").write_text(json.dumps({"version": version}))
        if with_viewer:
            (folder / "scripts").mkdir()
            (folder / "scripts" / "viewer.py").write_text("")
        return folder

    def real_install(self, version):
        folder = self.root / version
        shutil.copytree(PLUGIN, folder, ignore=shutil.ignore_patterns("__pycache__", ".mypy_cache", ".ruff_cache"))
        manifest = folder / ".claude-plugin" / "plugin.json"
        manifest.write_text(json.dumps({**json.loads(manifest.read_text()), "version": version}))
        return folder

    def newer_than(self, running):
        with unittest.mock.patch.object(viewer, "PLUGIN_ROOT", self.root / running):
            return viewer.newer_installed_plugin()

    def test_finds_a_newer_installed_version(self):
        self.fake_install("0.9.0")
        newer = self.fake_install("0.10.0")
        self.assertEqual(self.newer_than("0.9.0"), newer)

    def test_picks_the_newest_of_several(self):
        self.fake_install("0.1.0")
        self.fake_install("0.2.0")
        newest = self.fake_install("0.11.0")
        self.assertEqual(self.newer_than("0.1.0"), newest)

    def test_ignores_older_versions(self):
        self.fake_install("0.1.0")
        self.fake_install("0.0.9")
        self.assertIsNone(self.newer_than("0.1.0"))

    def test_ignores_a_folder_that_is_not_a_release_version(self):
        self.fake_install("0.1.0")
        self.fake_install("54f22dcbd905-c57d7e92")
        self.assertIsNone(self.newer_than("0.1.0"))

    def test_ignores_a_newer_install_that_has_no_viewer_yet(self):
        self.fake_install("0.1.0")
        self.fake_install("0.2.0", with_viewer=False)
        self.assertIsNone(self.newer_than("0.1.0"))

    def free_port(self):
        with socket.socket() as probe:
            probe.bind(("127.0.0.1", 0))
            return probe.getsockname()[1]

    def pidfile_version(self):
        try:
            return json.loads((self.data / "viewer.pid").read_text())["version"]
        except (FileNotFoundError, json.JSONDecodeError):
            return None

    def wait_for_version(self, version, port):
        deadline = time.monotonic() + 15
        while time.monotonic() < deadline:
            if self.pidfile_version() == version and viewer.is_healthy(port):
                return
            time.sleep(0.1)
        self.fail(f"the viewer never reported version {version}")

    def stop(self, process):
        process.terminate()
        process.wait(timeout=5)

    def test_a_running_viewer_hands_itself_over_to_a_newer_install(self):
        old = self.real_install("0.1.0")
        port = self.free_port()
        environment = {
            **os.environ,
            "UNDERSTAND_FIRST_DATA": str(self.data),
            "UNDERSTAND_FIRST_PORT": str(port),
            "UNDERSTAND_FIRST_UPDATE_CHECK_SECONDS": "0.2",
        }
        process = subprocess.Popen(
            [sys.executable, str(old / "scripts" / "viewer.py"), "serve"],
            env=environment, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
        self.addCleanup(self.stop, process)
        self.wait_for_version("0.1.0", port)

        self.real_install("0.2.0")

        self.wait_for_version("0.2.0", port)


if __name__ == "__main__":
    unittest.main()
