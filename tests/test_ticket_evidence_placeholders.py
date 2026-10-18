"""Known template placeholders must never count as lifecycle evidence."""
from datetime import datetime, timezone
import importlib.util
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("ticket_helper", ROOT / "skills/development-tickets/scripts/tickets.py")
assert SPEC is not None and SPEC.loader is not None
HELPER = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(HELPER)


class PlaceholderEvidenceTests(unittest.TestCase):
    def setUp(self):
        self.config = dict(project="example", prefix="DEMO", repos=[], areas=[])
        self.ticket_id = "DEMO-6f183071-b543-42b7-b788-6d1d5c95a0cb"
        self.now = datetime.now(timezone.utc).isoformat()
        self.data = dict(schema_version=1, record_type="development-ticket", ticket_project="example",
                         id=self.ticket_id, summary="Example", kind="docs", status="inbox", priority="unset",
                         areas=[], repos=[], confidence="reported", owner=None, reported_by="tester",
                         created=self.now, updated=self.now, started=None, completed=None,
                         implementation_authorization="none", verification="not-run", deployment="unknown",
                         related=[], duplicate_of=None, tags=["development"])
        self.path = Path(self.ticket_id + ".md")

    def test_not_run_is_not_verification_evidence(self):
        self.data.update(status="done", verification="passed", completed=self.now)
        body = "## Acceptance criteria\n- [x] Document the agreed behaviour.\n\n## Verification evidence\nNot run.\n"
        with self.assertRaises(HELPER.TicketError):
            HELPER.validate(self.data, body, self.path, self.config)

    def test_manual_template_does_not_record_implementation_approval(self):
        self.data.update(status="in-progress", implementation_authorization="approved", owner="coder", started=self.now)
        body = "## Authorization and decisions\nNo implementation authorization. Capture/triage only.\n"
        with self.assertRaises(HELPER.TicketError):
            HELPER.validate(self.data, body, self.path, self.config)

    def test_cancelled_needs_reason_not_any_old_decision(self):
        self.data.update(status="cancelled")
        body = "## Authorization and decisions\nHuman lead selected the docs topic for consideration.\n\n## History\nTicket captured.\n"
        with self.assertRaises(HELPER.TicketError):
            HELPER.validate(self.data, body, self.path, self.config)

    def test_thematic_tags_are_optional(self):
        self.data['tags'] = []
        HELPER.validate(self.data, '', self.path, self.config)

    def test_actual_cancellation_reason_is_accepted(self):
        self.data.update(status="cancelled")
        body = "## Authorization and decisions\nCancellation reason: superseded by the agreed consolidated request.\n"
        HELPER.validate(self.data, body, self.path, self.config)


if __name__ == "__main__":
    unittest.main()
