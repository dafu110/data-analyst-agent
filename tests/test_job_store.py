from __future__ import annotations

import unittest
from pathlib import Path
import uuid

from backend.job_store import JobStore


ROOT = Path(__file__).resolve().parents[1]
TEST_DB_DIR = ROOT / "storage" / "test-dbs"


class JobStoreTests(unittest.TestCase):
    def test_job_lifecycle_persists_to_disk(self) -> None:
        TEST_DB_DIR.mkdir(parents=True, exist_ok=True)
        store = JobStore(TEST_DB_DIR / f"{uuid.uuid4().hex}.sqlite3")
        try:
            job = store.create("sales.csv", "Find patterns")

            report_path = TEST_DB_DIR / f"{uuid.uuid4().hex}.md"
            store.set_running(job.id, "Profiling dataset.")
            report_path.write_text("# Report", encoding="utf-8")
            store.complete(job.id, {"ok": True}, report_path)

            loaded = store.get(job.id)
            self.assertIsNotNone(loaded)
            assert loaded is not None
            self.assertEqual(loaded.status, "completed")
            self.assertEqual(loaded.result, {"ok": True})
            self.assertTrue(loaded.report_path.endswith(".md"))
            self.assertGreaterEqual(len(loaded.events), 3)
        finally:
            store.close()

    def test_cancel_and_audit(self) -> None:
        TEST_DB_DIR.mkdir(parents=True, exist_ok=True)
        store = JobStore(TEST_DB_DIR / f"{uuid.uuid4().hex}.sqlite3")
        try:
            job = store.create("sales.csv", "Find patterns", owner="alice")
            cancelled = store.cancel(job.id)

            self.assertEqual(cancelled.status, "cancelled")
            self.assertTrue(store.is_cancelled(job.id))

            store.add_audit_event(
                actor="alice",
                action="job.cancel",
                target=job.id,
                trace_id="trace-1",
                ip_address="127.0.0.1",
                detail={"reason": "test"},
                timestamp="2026-06-30T00:00:00+00:00",
            )
            events = store.list_audit_events()
            self.assertEqual(events[0]["action"], "job.cancel")
        finally:
            store.close()

    def test_list_jobs_and_metrics_are_owner_scoped(self) -> None:
        TEST_DB_DIR.mkdir(parents=True, exist_ok=True)
        store = JobStore(TEST_DB_DIR / f"{uuid.uuid4().hex}.sqlite3")
        try:
            alice_job = store.create("alice.csv", "Find revenue", owner="alice")
            bob_job = store.create("bob.csv", "Find churn", owner="bob")
            store.set_running(alice_job.id, "Running")
            store.fail(bob_job.id, "Bad file")

            alice_jobs = store.list_jobs(owner="alice")
            self.assertEqual([job.owner for job in alice_jobs], ["alice"])

            alice_metrics = store.metrics(owner="alice")
            all_metrics = store.metrics()
            self.assertEqual(alice_metrics["total_jobs"], 1)
            self.assertEqual(alice_metrics["active_jobs"], 1)
            self.assertEqual(all_metrics["total_jobs"], 2)
            self.assertEqual(all_metrics["failed_jobs"], 1)
            self.assertIn("avg_duration_ms", all_metrics)
            self.assertIn("p95_duration_ms", all_metrics)
            self.assertEqual(store.cleanup_terminal_jobs(older_than_days=3650), 0)
        finally:
            store.close()

    def test_failed_jobs_do_not_hold_active_capacity(self) -> None:
        TEST_DB_DIR.mkdir(parents=True, exist_ok=True)
        store = JobStore(TEST_DB_DIR / f"{uuid.uuid4().hex}.sqlite3")
        try:
            job = store.create("broken.csv", "Find patterns", owner="alice", organization="acme")
            store.set_running(job.id, "Running")
            self.assertEqual(store.active_count_for_actor("alice", "acme"), 1)

            store.fail(job.id, "Bad dataset")

            self.assertEqual(store.active_count_for_actor("alice", "acme"), 0)
            self.assertEqual(store.metrics(owner="alice", organization="acme")["failed_jobs"], 1)
        finally:
            store.close()

    def test_jobs_are_scoped_by_organization_and_workspace(self) -> None:
        TEST_DB_DIR.mkdir(parents=True, exist_ok=True)
        store = JobStore(TEST_DB_DIR / f"{uuid.uuid4().hex}.sqlite3")
        try:
            store.create("org-a.csv", "Find patterns", owner="alice", organization="org-a", workspace="finance")
            store.create("org-b.csv", "Find patterns", owner="alice", organization="org-b", workspace="finance")
            store.create("ops.csv", "Find patterns", owner="alice", organization="org-a", workspace="ops")

            jobs = store.list_jobs(owner="alice", organization="org-a", workspace="finance")
            self.assertEqual(len(jobs), 1)
            self.assertEqual(jobs[0].filename, "org-a.csv")

            metrics = store.metrics(owner="alice", organization="org-a")
            self.assertEqual(metrics["total_jobs"], 2)
        finally:
            store.close()


if __name__ == "__main__":
    unittest.main()
