"""Offline contract checks for the portable Obsidian ticket Base template.

These inspect YAML and the documented filter subset; they do not execute
Obsidian's expression engine or prove visual rendering.
"""
from pathlib import Path
import unittest

import yaml

ROOT = Path(__file__).resolve().parents[1]
CANONICAL = ROOT / "skills/development-tickets/templates/tickets.base"
BOT_COPY = ROOT / "bots/development-ticket-triage/templates/tickets.base"


class TicketBaseTemplateTests(unittest.TestCase):
    def test_base_template_ships_in_both_self_contained_packages(self):
        self.assertTrue(CANONICAL.is_file(), "Missing canonical Base template")
        self.assertTrue(BOT_COPY.is_file(), "Missing standalone bot Base template")
        self.assertEqual(CANONICAL.read_bytes(), BOT_COPY.read_bytes())


    def test_filters_scope_by_vault_folder_project_type_and_extension(self):
        data = yaml.safe_load(CANONICAL.read_text())
        self.assertEqual(data['filters']['and'], [
            'file.inFolder("REPLACE_VAULT_RELATIVE_TICKET_DIR")',
            'file.ext == "md"',
            'note.record_type == "development-ticket"',
            'note.ticket_project == "REPLACE_PROJECT"',
        ])
        self.assertEqual(set(data), {'filters', 'formulas', 'properties', 'views'})

    def test_title_links_to_canonical_note_and_columns_use_ticket_fields(self):
        data = yaml.safe_load(CANONICAL.read_text())
        note_template = ROOT / "skills/development-tickets/templates/ticket.md"
        fields = set(yaml.safe_load(note_template.read_text().split('---', 2)[1]))
        self.assertEqual(data['formulas']['ticket'], 'file.asLink(note.summary)')
        for view in data['views']:
            self.assertEqual(view['type'], 'table')
            self.assertEqual(view['order'][0], 'formula.ticket')
            for column in view['order'][1:]:
                self.assertTrue(column.startswith('note.'))
                self.assertIn(column.removeprefix('note.'), fields)

    def test_views_separate_intake_active_and_all_without_hiding_review_or_blocked(self):
        data = yaml.safe_load(CANONICAL.read_text())
        views = {view['name']: view for view in data['views']}
        self.assertEqual(set(views), {'Inbox', 'Active by status', 'All', 'Needs discussion'})
        self.assertEqual(views['Needs discussion']['filters']['and'], [
            'note.decision == "needs-discussion"', 'note.status != "done"', 'note.status != "cancelled"',
        ])
        self.assertEqual(views['Inbox']['filters']['and'], ['note.status == "inbox"'])
        self.assertEqual(views['Active by status']['filters']['and'], [
            'note.status != "done"', 'note.status != "cancelled"',
        ])
        self.assertEqual(views['Active by status']['groupBy'], {
            'property': 'note.status', 'direction': 'ASC',
        })
        self.assertNotIn('groupOrder', views['Active by status'])
        self.assertNotIn('filters', views['All'])
        self.assertTrue(all('limit' not in view for view in views.values()))

    def test_private_copy_can_be_customized_without_changing_shared_template(self):
        original = CANONICAL.read_text()
        customized = original.replace('REPLACE_VAULT_RELATIVE_TICKET_DIR', 'Products/Sample/Tickets')
        customized = customized.replace('REPLACE_PROJECT', 'sample')
        data = yaml.safe_load(customized)
        self.assertIn('file.inFolder("Products/Sample/Tickets")', data['filters']['and'])
        self.assertIn('note.ticket_project == "sample"', data['filters']['and'])
        self.assertNotIn('REPLACE_', customized)
        self.assertEqual(CANONICAL.read_text(), original)


if __name__ == "__main__":
    unittest.main()
