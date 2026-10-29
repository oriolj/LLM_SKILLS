"""Offline packaging checks; no runtime installation or network."""
import importlib.util
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
SYNC = ROOT / "scripts/sync_ticket_protocol.py"


class ProtocolPackagingTests(unittest.TestCase):
    def test_sync_check_command_exists_and_passes(self):
        self.assertTrue(SYNC.is_file(), "Missing protocol synchronization helper")
        result = subprocess.run([sys.executable, str(SYNC), "--check"], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_copied_bot_protocol_and_template_match_canonical(self):
        for rel in ["references/protocol.md", "references/triage.md", "templates/ticket.md", "templates/tickets.base"]:
            self.assertEqual((ROOT / "skills/development-tickets" / rel).read_bytes(),
                             (ROOT / "bots/development-ticket-triage" / rel).read_bytes())

    def test_symlinked_destination_ancestor_never_overwrites_other_files(self):
        assert SYNC.is_file()
        spec = importlib.util.spec_from_file_location("sync_protocol_symlink", SYNC)
        assert spec is not None and spec.loader is not None
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for rel in ["references/protocol.md", "references/triage.md", "templates/ticket.md", "templates/tickets.base"]:
                source = root / "skills/development-tickets" / rel
                source.parent.mkdir(parents=True, exist_ok=True)
                source.write_text("canonical")
            unrelated = root / "unrelated"
            unrelated.mkdir()
            (unrelated / "protocol.md").write_text("must survive")
            package = root / "bots/development-ticket-triage"
            (package / "templates").mkdir(parents=True)
            (package / "templates/ticket.md").write_text("old template")
            (package / "references").symlink_to(unrelated, target_is_directory=True)
            with self.assertRaises(ValueError):
                module.synchronize(root, check=False)
            self.assertEqual((unrelated / "protocol.md").read_text(), "must survive")
            self.assertEqual((package / "templates/ticket.md").read_text(), "old template")

    def test_second_pair_symlink_prevents_first_pair_write(self):
        assert SYNC.is_file()
        spec = importlib.util.spec_from_file_location("sync_protocol_preflight", SYNC)
        assert spec is not None and spec.loader is not None
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        for dangling in (False, True):
            with self.subTest(dangling=dangling), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                for rel in ["references/protocol.md", "references/triage.md", "templates/ticket.md", "templates/tickets.base"]:
                    source = root / "skills/development-tickets" / rel
                    source.parent.mkdir(parents=True, exist_ok=True)
                    source.write_text("canonical")
                package = root / "bots/development-ticket-triage"
                (package / "references").mkdir(parents=True)
                (package / "references/protocol.md").write_text("old protocol")
                other = root / "other"
                if not dangling:
                    other.mkdir()
                    (other / "ticket.md").write_text("unrelated template")
                (package / "templates").symlink_to(other, target_is_directory=True)
                with self.assertRaises(ValueError):
                    module.synchronize(root, check=False)
                self.assertEqual((package / "references/protocol.md").read_text(), "old protocol")
                if not dangling:
                    self.assertEqual((other / "ticket.md").read_text(), "unrelated template")

    def test_check_detects_drift_without_repair(self):
        if not SYNC.is_file():
            self.skipTest("Covered by missing-helper test")
        spec = importlib.util.spec_from_file_location("sync_protocol", SYNC)
        assert spec is not None and spec.loader is not None
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for rel in ["references/protocol.md", "references/triage.md", "templates/ticket.md", "templates/tickets.base"]:
                canonical = root / "skills/development-tickets" / rel
                copy = root / "bots/development-ticket-triage" / rel
                canonical.parent.mkdir(parents=True, exist_ok=True)
                copy.parent.mkdir(parents=True, exist_ok=True)
                canonical.write_text("canonical")
                copy.write_text("old")
            self.assertEqual(module.synchronize(root, check=True), 1)
            self.assertEqual((root / "bots/development-ticket-triage/references/protocol.md").read_text(), "old")
            self.assertEqual(module.synchronize(root, check=False), 0)
            self.assertEqual(module.synchronize(root, check=True), 0)


    def test_base_only_drift_is_detected_without_repair(self):
        spec = importlib.util.spec_from_file_location("sync_base_drift", SYNC)
        assert spec is not None and spec.loader is not None
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for rel in ["references/protocol.md", "references/triage.md", "templates/ticket.md", "templates/tickets.base"]:
                canonical = root / "skills/development-tickets" / rel
                copy = root / "bots/development-ticket-triage" / rel
                canonical.parent.mkdir(parents=True, exist_ok=True)
                copy.parent.mkdir(parents=True, exist_ok=True)
                canonical.write_text("canonical")
                copy.write_text("old base" if rel.endswith(".base") else "canonical")
            self.assertEqual(module.synchronize(root, check=True), 1)
            target = root / "bots/development-ticket-triage/templates/tickets.base"
            self.assertEqual(target.read_text(), "old base")
            self.assertEqual(module.synchronize(root, check=False), 0)
            self.assertEqual(module.synchronize(root, check=True), 0)

    def test_unsafe_third_pair_prevents_earlier_pair_writes(self):
        spec = importlib.util.spec_from_file_location("sync_base_preflight", SYNC)
        assert spec is not None and spec.loader is not None
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for rel in ["references/protocol.md", "references/triage.md", "templates/ticket.md", "templates/tickets.base"]:
                canonical = root / "skills/development-tickets" / rel
                canonical.parent.mkdir(parents=True, exist_ok=True)
                canonical.write_text("canonical")
            package = root / "bots/development-ticket-triage"
            for rel in ["references/protocol.md", "templates/ticket.md"]:
                target = package / rel
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text("old copy")
            unrelated = root / "unrelated.base"
            unrelated.write_text("must survive")
            (package / "templates/tickets.base").symlink_to(unrelated)
            with self.assertRaises(ValueError):
                module.synchronize(root, check=False)
            self.assertEqual(unrelated.read_text(), "must survive")
            for rel in ["references/protocol.md", "templates/ticket.md"]:
                self.assertEqual((package / rel).read_text(), "old copy")


if __name__ == "__main__":
    unittest.main()
