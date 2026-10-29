"""Real CLI tests; temporary work stays under the configured scratch directory."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
import uuid

import yaml

SCRIPT = Path(__file__).resolve().parents[1] / 'skills/development-tickets/scripts/tickets.py'
SCRATCH = os.environ.get('TMPDIR')


class TicketsTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(dir=SCRATCH)
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.config = self.root / 'ticket-system.json'
        self.settings = dict(schema_version=1, project='bikecrm', prefix='BCRM',
                             ticket_dir='Tickets', repos=['backend'], areas=['sales'])
        self.save_config()

    def save_config(self):
        self.config.write_text(json.dumps(self.settings), encoding='utf-8')

    def cli(self, *args):
        return subprocess.run([sys.executable, str(SCRIPT), '--config', str(self.config), *args],
                              capture_output=True, text=True)

    def create(self, summary='A request', *extra):
        return self.cli('create', '--summary', summary, '--kind', 'bug', '--actor', 'Oriol', *extra)

    def note(self):
        return next((self.root / 'Tickets').glob('*.md'))

    def load_note(self):
        text = self.note().read_text(encoding='utf-8')
        _, metadata, body = text.split('---', 2)
        return yaml.safe_load(metadata), body

    def save_note(self, data, body):
        self.note().write_text('---\n' + yaml.safe_dump(data, sort_keys=False) + '---\n' + body,
                               encoding='utf-8')

    def test_invalid_config_never_writes(self):
        original = self.settings.copy()
        cases = [('schema_version', 2), ('schema_version', True), ('project', ''),
                 ('prefix', '../oops'), ('prefix', 'a'), ('ticket_dir', ''),
                 ('ticket_dir', '../outside'), ('ticket_dir', '/absolute'),
                 ('repos', 'backend'), ('areas', [1]), ('developer', 42),
                 ('unexpected', 'value'), ('kind_prefixes', {'bug': 'bad'}),
                 ('kind_prefixes', {'unknown-kind': 'BUG'}), ('kind_prefixes', ['BUG']),
                 ('kind_prefixes', {'bug': 'BUG', 'feature': 'BUG'})]
        for key, value in cases:
            with self.subTest(key=key, value=value):
                self.settings = {**original, key: value}
                self.save_config()
                result = self.create()
                self.assertEqual(result.returncode, 1, result.stderr)
                self.assertNotIn('Traceback', result.stderr)
                self.assertFalse((self.root / 'Tickets').exists())

    def test_symlink_ticket_dir_escape_rejected(self):
        (self.root / 'Tickets').symlink_to(self.root.parent, target_is_directory=True)
        result = self.create()
        self.assertEqual(result.returncode, 1, result.stderr)
        self.assertIn('ticket_dir', result.stderr)

    def test_invalid_create_inputs_never_write(self):
        for extra in [('--area', 'unknown'), ('--repo', '../backend'), ('--actor', '  '),
                      ('--summary', '   '), ('--summary', 'heading\n## injected')]:
            with self.subTest(extra=extra):
                result = self.create('A request', *extra)
                self.assertEqual(result.returncode, 1, result.stderr)
                self.assertFalse((self.root / 'Tickets').exists())

    def test_empty_check_and_list_are_read_only(self):
        result = self.cli('check')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout), {'total': 0, 'errors': 0, 'statuses': {}})
        result = self.cli('list')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout), [])
        self.assertFalse((self.root / 'Tickets').exists())

    def test_list_only_public_fields(self):
        self.assertEqual(self.create().returncode, 0)
        before = self.note().read_bytes()
        result = self.cli('list')
        self.assertEqual(result.returncode, 0, result.stderr)
        rows = json.loads(result.stdout)
        self.assertEqual(len(rows), 1)
        self.assertEqual(set(rows[0]), {'id', 'summary', 'status', 'priority', 'kind', 'areas', 'repos', 'triage', 'decision'})
        self.assertEqual(self.note().read_bytes(), before)
        result = self.cli('check')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout)['statuses'], {'inbox': 1})

    def test_duplicate_active_summary_refused(self):
        self.assertEqual(self.create('Repair Straße').returncode, 0)
        result = self.create('REPAIR STRASSE')
        self.assertEqual(result.returncode, 1, result.stderr)
        self.assertIn('existing', result.stderr)
        self.assertEqual(len(list((self.root / 'Tickets').glob('*.md'))), 1)

    def test_invalid_schema_blocks_check_list_and_create(self):
        self.assertEqual(self.create().returncode, 0)
        original, body = self.load_note()
        mutations = [('schema_version', 2), ('schema_version', True), ('record_type', 'other'),
                     ('ticket_project', 'other'), ('id', 'BCRM-not-a-number'), ('kind', 'oops'),
                     ('status', 'oops'), ('priority', 'oops'), ('confidence', 'oops'),
                     ('implementation_authorization', 'oops'), ('verification', 'oops'),
                     ('deployment', 'oops'), ('summary', ''), ('reported_by', None),
                     ('areas', ['unknown']), ('repos', 'backend'), ('related', ['bad']),
                     ('tags', 'not-a-list'), ('owner', 42), ('created', '2026-01-01T12:00:00'),
                     ('updated', None), ('started', 'yesterday'), ('completed', 'invalid'),
                     ('duplicate_of', original['id'])]
        for key, value in mutations:
            with self.subTest(field=key):
                self.save_note({**original, key: value}, body)
                before = self.note().read_bytes()
                for args in [('check',), ('list',), ('create', '--summary', 'New', '--kind', 'bug', '--actor', 'Oriol')]:
                    result = self.cli(*args)
                    self.assertEqual(result.returncode, 1, result.stderr)
                    self.assertNotIn('Traceback', result.stderr)
                self.assertEqual(self.note().read_bytes(), before)
                self.assertEqual(len(list((self.root / 'Tickets').glob('*.md'))), 1)
        data = original.copy()
        del data['owner']
        self.save_note(data, body)
        self.assertEqual(self.cli('check').returncode, 1)

    def test_yaml_and_filename_errors_are_clean_and_counted(self):
        self.assertEqual(self.create().returncode, 0)
        original = self.note().read_text()
        path = self.note()
        variants = ['---\nprivate: [secret value\n---\n', original.replace('schema_version: 1', 'schema_version: 1\nschema_version: 1'), 'not frontmatter']
        for value in variants:
            with self.subTest(value=value[:10]):
                path.write_text(value)
                result = self.cli('check')
                self.assertEqual(result.returncode, 1, result.stderr)
                self.assertEqual(json.loads(result.stdout)['errors'], 1)
                self.assertNotIn('secret value', result.stderr)
                self.assertNotIn('Traceback', result.stderr)
        path.write_text(original)
        conflict = path.with_name(path.stem + '.sync-conflict-20260101.md')
        path.rename(conflict)
        self.assertEqual(self.cli('check').returncode, 1)
        conflict.rename(path.with_name('wrong.md'))
        self.assertEqual(self.cli('check').returncode, 1)

    def test_symlink_note_outside_root_rejected(self):
        self.assertEqual(self.create().returncode, 0)
        path = self.note()
        outside = self.root / path.name
        path.rename(outside)
        path.symlink_to(outside)
        result = self.cli('check')
        self.assertEqual(result.returncode, 1, result.stderr)

    def test_done_requires_checked_real_acceptance_and_verification(self):
        self.assertEqual(self.create().returncode, 0)
        data, body = self.load_note()
        data.update(status='done', completed=data['updated'], verification='passed')
        good = body.replace('- [ ] Define observable completion criteria.', '- [x] CLI produces a canonical ticket.')
        good = good.replace('## Verification evidence\n', '## Verification evidence\n\nRan CLI tests: all passed.\n')
        self.save_note(data, good)
        result = self.cli('check')
        self.assertEqual(result.returncode, 0, result.stderr)
        cases = [({**data, 'completed': None}, good), ({**data, 'verification': 'not-run'}, good),
                 ({**data, 'status': 'inbox'}, good), (data, body),
                 (data, good.replace('[x]', '[ ]')), (data, good.replace('CLI produces a canonical ticket.', 'Define observable completion criteria.')),
                 (data, good.replace('Ran CLI tests: all passed.', '')), (data, good.replace('Ran CLI tests: all passed.', 'TODO')),
                 (data, good.replace('- [x] CLI produces a canonical ticket.', ''))]
        for changed, content in cases:
            with self.subTest(changed=changed['status'], content=content[-80:]):
                self.save_note(changed, content)
                self.assertEqual(self.cli('check').returncode, 1)
        self.save_note(data, good)
        self.assertEqual(self.create().returncode, 0, 'done ticket does not block new capture')

    def test_work_states_require_recorded_authorization(self):
        self.assertEqual(self.create().returncode, 0)
        data, body = self.load_note()
        authorization = body.replace('No implementation permission granted.', 'Oriol approved bounded local docs work in message 2026-10-18; no push or deployment.')
        for status in ('in-progress', 'review'):
            good = {**data, 'status': status, 'owner': 'Oriol', 'started': data['created'], 'implementation_authorization': 'approved'}
            self.save_note(good, authorization)
            self.assertEqual(self.cli('check').returncode, 0)
            for key, value in [('owner', None), ('started', None), ('implementation_authorization', 'none')]:
                with self.subTest(status=status, key=key):
                    self.save_note({**good, key: value}, authorization)
                    self.assertEqual(self.cli('check').returncode, 1)
            self.save_note(good, body)
            self.assertEqual(self.cli('check').returncode, 1)

    def test_cancelled_requires_explicit_reason_not_capture_history(self):
        self.assertEqual(self.create().returncode, 0)
        data, body = self.load_note()
        data['status'] = 'cancelled'
        self.save_note(data, body)
        self.assertEqual(self.cli('check').returncode, 1)
        for content in [body.replace('No implementation permission granted.', 'Cancellation reason: superseded by a reviewed request.'),
                        body + '\n- Cancellation reason: duplicate of existing request.\n']:
            self.save_note(data, content)
            result = self.cli('check')
            self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.create().returncode, 0)

    def test_repeated_registry_flags_do_not_create_invalid_lists(self):
        result = self.create('Repeated flags', '--area', 'sales', '--area', 'sales', '--repo', 'backend', '--repo', 'backend')
        self.assertEqual(result.returncode, 0, result.stderr)
        data, _ = self.load_note()
        self.assertEqual(data['areas'], ['sales'])
        self.assertEqual(data['repos'], ['backend'])
        self.assertEqual(self.cli('check').returncode, 0)

    def test_done_rejects_partial_or_hidden_acceptance(self):
        self.assertEqual(self.create().returncode, 0)
        data, body = self.load_note()
        data.update(status='done', completed=data['created'], verification='passed')
        body = body.replace('## Verification evidence\n', '## Verification evidence\n\nTests passed.\n')
        for checks in ['- [x] Real criterion.\n- [/] Partially met criterion.',
                       '<!--\n- [x] Hidden criterion.\n-->',
                       '- [x] Real criterion.\n1. [ ] Unmet numbered criterion.']:
            with self.subTest(checks=checks):
                changed = body.replace('- [ ] Define observable completion criteria.', checks)
                self.save_note(data, changed)
                self.assertEqual(self.cli('check').returncode, 1)

    def test_config_duplicate_keys_rejected(self):
        value = self.config.read_text().replace('"schema_version": 1', '"schema_version": 1, "schema_version": 1')
        self.config.write_text(value)
        result = self.create()
        self.assertEqual(result.returncode, 1, result.stderr)
        self.assertFalse((self.root / 'Tickets').exists())

    def test_non_markdown_symlink_escape_is_flagged(self):
        (self.root / 'Tickets').mkdir()
        (self.root / 'Tickets' / 'outside').symlink_to(self.root, target_is_directory=True)
        result = self.cli('check')
        self.assertEqual(result.returncode, 1, result.stderr)
        self.assertEqual(json.loads(result.stdout)['errors'], 1)
        self.assertEqual(self.create().returncode, 1)

    def test_missing_dependency_has_polite_error(self):
        result = subprocess.run([sys.executable, '-I', '-S', str(SCRIPT), '--config', str(self.config), 'check'],
                                capture_output=True, text=True)
        self.assertEqual(result.returncode, 1)
        self.assertIn('PyYAML is required', result.stderr)
        self.assertNotIn('Traceback', result.stderr)
        self.assertFalse((self.root / 'Tickets').exists())

    def test_malformed_configs_are_clean(self):
        for value in ['null', '[]', '{private: secret}', '{"schema_version": 1}']:
            with self.subTest(value=value):
                self.config.write_text(value)
                result = self.cli('check')
                self.assertEqual(result.returncode, 1)
                self.assertNotIn('Traceback', result.stderr)
                self.assertNotIn('secret', result.stderr)
        result = subprocess.run([sys.executable, str(SCRIPT), '--config', 'relative.json', 'check'], capture_output=True, text=True)
        self.assertEqual(result.returncode, 1)
        self.assertIn('absolute', result.stderr)

    def test_related_cross_project_ids_preserved_without_lookup(self):
        self.assertEqual(self.create().returncode, 0)
        data, body = self.load_note()
        data['related'] = ['DOCS-' + str(uuid.uuid4()), 'OTHER-042']
        self.save_note(data, body)
        before = self.note().read_bytes()
        self.assertEqual(self.cli('check').returncode, 0)
        self.assertEqual(self.note().read_bytes(), before)

    def test_canonical_ids_and_unique_filenames_enforced(self):
        self.assertEqual(self.create().returncode, 0)
        original, body = self.load_note()
        for identifier in ['OTHER-001', 'BCRM-01', 'BCRM-1', 'bcrm-001', 'BCRM-' + str(uuid.uuid1()),
                           'BCRM-' + str(uuid.uuid4()).upper(), original['id'] + '/suffix']:
            with self.subTest(identifier=identifier):
                self.save_note({**original, 'id': identifier}, body)
                self.assertEqual(self.cli('check').returncode, 1)
        self.save_note(original, body)
        (self.root / 'Tickets' / 'copy.md').write_bytes(self.note().read_bytes())
        result = self.cli('check')
        self.assertEqual(result.returncode, 1)
        self.assertEqual(json.loads(result.stdout)['total'], 2)
        self.assertEqual(json.loads(result.stdout)['errors'], 1)

    def test_filename_is_id_optionally_followed_by_a_title(self):
        self.assertEqual(self.create('Broken upload').returncode, 0)
        path = self.note()
        self.assertEqual(path.name, 'BCRM-001 — Broken upload.md')
        for name in ['BCRM-001.md', 'BCRM-001 Renamed title.md']:
            path = path.rename(path.with_name(name))
            self.assertEqual(self.cli('check').returncode, 0, name)
        for name in ['BCRM-0011.md', 'BCRM-001-x.md', 'Title BCRM-001.md']:
            path = path.rename(path.with_name(name))
            self.assertEqual(self.cli('check').returncode, 1, name)

    def test_sequential_ids_continue_after_highest_number_including_closed(self):
        self.assertEqual(self.create('First').returncode, 0)
        data, body = self.load_note()
        self.note().unlink()
        cancelled = {**data, 'id': 'BCRM-041', 'status': 'cancelled'}
        (self.root / 'Tickets' / 'BCRM-041.md').write_text(
            '---\n' + yaml.safe_dump(cancelled, sort_keys=False) + '---\n' + body
            + '\n- Cancellation reason: duplicate.\n', encoding='utf-8')
        result = self.create('Second')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.strip(), 'BCRM-042')
        self.assertTrue((self.root / 'Tickets' / 'BCRM-042 — Second.md').exists())

    def test_kind_prefixes_number_each_prefix_and_survive_reclassification(self):
        self.settings['kind_prefixes'] = {'bug': 'BUG', 'improvement': 'IMP'}
        self.save_config()
        outputs = [self.cli('create', '--summary', summary, '--kind', kind, '--actor', 'Oriol').stdout.strip()
                   for summary, kind in [('One', 'bug'), ('Two', 'improvement'), ('Three', 'bug'), ('Four', 'docs')]]
        self.assertEqual(outputs, ['BUG-001', 'IMP-001', 'BUG-002', 'BCRM-001'])
        path = next((self.root / 'Tickets').glob('BUG-002*.md'))
        text = path.read_text(encoding='utf-8').replace('kind: bug', 'kind: improvement')
        path.write_text(text, encoding='utf-8')
        self.assertEqual(self.cli('check').returncode, 0, 'reclassifying keeps the minted ID')

    def test_investigation_kind(self):
        self.settings['kind_prefixes'] = {'investigation': 'INV'}
        self.save_config()
        result = self.cli('create', '--summary', 'GlitchTip event', '--kind', 'investigation', '--actor', 'Patri')
        self.assertEqual(result.stdout.strip(), 'INV-001', result.stderr)
        data, _ = self.load_note()
        self.assertEqual(data['kind'], 'investigation')
        self.assertEqual(self.cli('check').returncode, 0)

    def test_legacy_uuid_tickets_stay_valid(self):
        self.assertEqual(self.create().returncode, 0)
        data, body = self.load_note()
        legacy = 'BCRM-' + str(uuid.uuid4())
        self.note().unlink()
        (self.root / 'Tickets' / (legacy + '.md')).write_text(
            '---\n' + yaml.safe_dump({**data, 'id': legacy}, sort_keys=False) + '---\n' + body, encoding='utf-8')
        self.assertEqual(self.cli('check').returncode, 0)
        result = self.create('Next one')
        self.assertEqual(result.stdout.strip(), 'BCRM-001', 'UUID IDs do not take part in numbering')

    def test_same_number_from_two_hosts_is_flagged(self):
        self.assertEqual(self.create('From laptop').returncode, 0)
        path = self.note()
        (self.root / 'Tickets' / 'BCRM-001 — From the bot.md').write_bytes(path.read_bytes())
        result = self.cli('check')
        self.assertEqual(result.returncode, 1)
        self.assertEqual(json.loads(result.stdout)['errors'], 1)
        self.assertEqual(self.create('Blocked until renumbered').returncode, 1)

    def test_title_in_filename_is_sanitized(self):
        result = self.create('a/b: c? "d" [e] #f ' + 'x' * 200)
        self.assertEqual(result.returncode, 0, result.stderr)
        name = self.note().name
        self.assertTrue(name.startswith('BCRM-001 — a b c d e f '))
        self.assertLessEqual(len(name), len('BCRM-001 — .md') + 80)
        self.assertFalse(any(char in name[:-3] for char in '/:?"[]#'))

    def test_number_race_never_overwrites_file(self):
        # Simulates another writer taking the number between scan and write:
        # only the ID choice is controlled, filesystem and CLI stay real.
        import importlib.util
        from contextlib import redirect_stdout
        import io
        from unittest.mock import patch
        spec = importlib.util.spec_from_file_location('local_tickets', SCRIPT)
        assert spec is not None and spec.loader is not None
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        args = ['tickets.py', '--config', str(self.config), 'create', '--summary', 'Same', '--kind', 'bug', '--actor', 'Oriol']
        with patch.object(sys, 'argv', args), patch.object(module, 'next_id', return_value='BCRM-001'), redirect_stdout(io.StringIO()):
            self.assertEqual(module.main(), 0)
            before = self.note().read_bytes()
            args[args.index('Same')] = 'Same.'  # a new summary whose filename is the same
            with self.assertRaises(FileExistsError):
                module.main()
            self.assertEqual(self.note().read_bytes(), before)

    def test_triage_fields_default_and_legacy_notes_without_them(self):
        self.assertEqual(self.create().returncode, 0)
        data, body = self.load_note()
        self.assertEqual((data['triage'], data['triaged_by'], data['triaged'], data['decision']),
                         ('untriaged', None, None, 'pending'))
        for key in ('triage', 'triaged_by', 'triaged', 'decision'):
            del data[key]
        self.save_note(data, body)
        self.assertEqual(self.cli('check').returncode, 0)
        self.assertEqual(json.loads(self.cli('list').stdout)[0]['triage'], 'untriaged')

    def test_triage_rules(self):
        self.assertEqual(self.create().returncode, 0)
        original, body = self.load_note()
        when = '2026-10-29T19:40:00+00:00'
        valid = [dict(triage='agent-reviewed', triaged_by='claude-code', triaged=when),
                 dict(triage='agent-reviewed', triaged_by='claude-code', triaged=when, decision='needs-discussion'),
                 dict(triage='human-reviewed', triaged_by='Oriol', triaged=when, decision='agreed'),
                 dict(triage='human-reviewed', triaged_by='Oriol', triaged=when, decision='declined',
                      status='cancelled')]
        invalid = [dict(triage='oops'), dict(decision='oops'),
                   dict(triaged_by='claude-code'),  # untriaged with a reviewer
                   dict(triage='agent-reviewed', triaged=when),  # no reviewer
                   dict(triage='agent-reviewed', triaged_by='claude-code', triaged='yesterday'),
                   dict(triage='agent-reviewed', triaged_by='oriol', triaged=when),  # reporter reviewing itself
                   dict(triage='agent-reviewed', triaged_by='claude-code', triaged=when, decision='agreed'),
                   dict(triage='human-reviewed', triaged_by='Oriol', triaged=when, decision='declined'),
                   dict(triage='unexpected-field-check', extra='x')]
        cancelled_body = body.replace('## History\n', '## History\n\n- Cancellation reason: not wanted.\n')
        for change in valid:
            with self.subTest(valid=change):
                self.save_note({**original, **change}, cancelled_body)
                result = self.cli('check')
                self.assertEqual(result.returncode, 0, result.stderr)
        for change in invalid:
            with self.subTest(invalid=change):
                self.save_note({**original, **change}, body)
                self.assertEqual(self.cli('check').returncode, 1)

    def test_ready_feature_requires_agreed_but_bug_does_not(self):
        self.assertEqual(self.create().returncode, 0)
        data, body = self.load_note()
        self.save_note({**data, 'status': 'ready'}, body)
        self.assertEqual(self.cli('check').returncode, 0, 'a ready bug may stay pending')
        self.save_note({**data, 'status': 'ready', 'kind': 'feature'}, body)
        self.assertEqual(self.cli('check').returncode, 1)
        self.save_note({**data, 'status': 'ready', 'kind': 'feature', 'triage': 'human-reviewed',
                        'triaged_by': 'Oriol', 'triaged': '2026-10-29T19:40:00+00:00', 'decision': 'agreed'}, body)
        self.assertEqual(self.cli('check').returncode, 0)
        legacy = {key: value for key, value in data.items() if key not in ('triage', 'triaged_by', 'triaged', 'decision')}
        self.save_note({**legacy, 'status': 'ready', 'kind': 'feature'}, body)
        self.assertEqual(self.cli('check').returncode, 0, 'pre-1.2 ready notes stay valid')

    def test_create_canonical_safe_inbox(self):
        result = self.create('../not a path', '--area', 'sales', '--repo', 'backend')
        self.assertEqual(result.returncode, 0, result.stderr)
        data, body = self.load_note()
        self.assertEqual(data['id'], 'BCRM-001')
        self.assertEqual(self.note().name, 'BCRM-001 — not a path.md')
        self.assertEqual(data['status'], 'inbox')
        self.assertEqual(data['areas'], ['sales'])
        self.assertEqual(data['implementation_authorization'], 'none')
        self.assertIsNone(data['completed'])
        self.assertIn('## Acceptance criteria', body)
        self.assertIn('- [ ] Define observable completion criteria.', body)
        self.assertIn('## History', body)
        self.assertIn('Oriol', body)


if __name__ == '__main__':
    unittest.main()
