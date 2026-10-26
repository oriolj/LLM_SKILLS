#!/usr/bin/env python3
"""Local-only development ticket creation and read-only inspection."""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import sys
import re


class TicketError(ValueError):
    pass


PREFIX = re.compile(r'[A-Z][A-Z0-9]{1,11}')


def text(value):
    return isinstance(value, str) and bool(value.strip()) and not any(ord(c) < 32 or ord(c) == 127 for c in value)


def strings(value):
    return isinstance(value, list) and all(text(item) for item in value) and len(set(value)) == len(value)


def unique_json(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise TicketError('duplicate config key')
        result[key] = value
    return result


def load_config(path):
    if not path.is_absolute():
        raise TicketError('config path must be absolute')
    config = json.loads(path.read_text(encoding='utf-8'), object_pairs_hook=unique_json)
    required = {'schema_version', 'project', 'prefix', 'ticket_dir', 'repos', 'areas'}
    if not isinstance(config, dict) or not required <= config.keys() or config.keys() - required - {'developer', 'kind_prefixes'}:
        raise TicketError('invalid config fields')
    if type(config['schema_version']) is not int or config['schema_version'] != 1:
        raise TicketError('invalid config schema_version')
    if not text(config['project']) or not isinstance(config['prefix'], str) or not PREFIX.fullmatch(config['prefix']):
        raise TicketError('invalid config project or prefix')
    # Optional per-kind prefixes (BUG-001, IMP-009); kinds left out use `prefix`.
    kind_prefixes = config.get('kind_prefixes', {})
    if (not isinstance(kind_prefixes, dict) or not set(kind_prefixes) <= set(KINDS)
            or not all(isinstance(value, str) and PREFIX.fullmatch(value) for value in kind_prefixes.values())
            or len(set(kind_prefixes.values())) != len(kind_prefixes)):
        raise TicketError('invalid config kind_prefixes')
    if not strings(config['repos']) or not strings(config['areas']) or ('developer' in config and not text(config['developer'])):
        raise TicketError('invalid config repos, areas or developer')
    directory = config['ticket_dir']
    if not text(directory) or Path(directory).is_absolute() or '..' in Path(directory).parts:
        raise TicketError('ticket_dir must be a nonempty relative path inside the config directory')
    base = path.parent.resolve()
    root = (base / directory).resolve()
    if root == base or not root.is_relative_to(base):
        raise TicketError('ticket_dir escapes config directory')
    return config, root

try:
    import yaml
except ImportError:
    print('tickets: PyYAML is required; please provide it in your Python environment. Nothing was installed.', file=sys.stderr)
    sys.exit(1)

KINDS = ('bug', 'improvement', 'feature', 'docs', 'chore', 'research')
CONFIDENCE = ('reported', 'suspected', 'reproduced')
STATUSES = ('inbox', 'ready', 'in-progress', 'blocked', 'review', 'done', 'cancelled')
ENUMS = {'kind': KINDS, 'status': STATUSES, 'priority': ('unset', 'p0', 'p1', 'p2', 'p3'),
         'confidence': CONFIDENCE, 'implementation_authorization': ('none', 'approved'),
         'verification': ('not-run', 'partial', 'passed', 'failed'),
         'deployment': ('unknown', 'not-required', 'not-deployed', 'deployed')}
FIELDS = set(('schema_version record_type ticket_project id summary kind status priority areas repos '
              'confidence owner reported_by created updated started completed implementation_authorization '
              'verification deployment related duplicate_of tags').split())
PUBLIC = ('id', 'summary', 'status', 'priority', 'kind', 'areas', 'repos')


class UniqueLoader(yaml.SafeLoader):
    """Safe YAML with duplicate/merge keys rejected rather than silently overwritten."""

    def construct_mapping(self, node, deep=False):
        result = {}
        for key_node, value_node in node.value:
            key = self.construct_object(key_node, deep=deep)
            if not isinstance(key, str) or key in result:
                raise TicketError('duplicate or invalid YAML key')
            result[key] = self.construct_object(value_node, deep=deep)
        return result


SEQUENTIAL = r'[0-9]{3,}'
# Protocol 1.0 minted UUID4 IDs; notes that already carry one stay valid.
LEGACY_UUID = r'[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}'
ID = re.compile(rf'([A-Z][A-Z0-9]{{1,11}})-({SEQUENTIAL}|{LEGACY_UUID})')


def prefixes(config):
    return {config['prefix'], *config.get('kind_prefixes', {}).values()}


def valid_id(value, allowed=None):
    if not isinstance(value, str):
        return False
    match = ID.fullmatch(value)
    return bool(match and (allowed is None or match[1] in allowed))


def valid_filename(name, identifier):
    # `<ID>.md` or `<ID> <readable title>.md`; the ID part is what links rely on.
    return name == identifier + '.md' or (name.startswith(identifier + ' ') and name.endswith('.md'))


def filename_title(summary):
    title = re.sub(r'[\\/:*?"<>|#^\[\]]', ' ', summary)
    title = re.sub(r'\s+', ' ', title).strip(' .')[:80].rstrip(' .')
    return title


def next_id(prefix, records):
    numbers = [int(match[2]) for record in records
               if (match := ID.fullmatch(record['id'])) and match[1] == prefix and match[2].isdigit()]
    return f'{prefix}-{max(numbers, default=0) + 1:03d}'


def timestamp(value):
    if not isinstance(value, str) or not re.match(r'^\d{4}-\d{2}-\d{2}T', value):
        return False
    try:
        return datetime.fromisoformat(value).utcoffset() is not None
    except ValueError:
        return False


def sections(body):
    result = {}
    heading = None
    fenced = False
    body = re.sub(r'<!--.*?-->', '', body, flags=re.S)
    for line in body.splitlines():
        if line.lstrip().startswith(('```', '~~~')):
            fenced = not fenced
            continue
        if fenced:
            continue
        if line.startswith('## '):
            heading = line[3:].strip()
            if heading in result:
                raise TicketError('duplicate body section')
            result[heading] = []
        elif heading is not None:
            result[heading].append(line)
    return {key: '\n'.join(value).strip() for key, value in result.items()}


def meaningful(value):
    clean = re.sub(r'<!--.*?-->', '', value, flags=re.S).strip()
    placeholders = {'todo', 'tbd', 'none', 'n/a', 'not applicable', 'not run', 'not-run',
                    'not started', 'not yet reproduced', 'unknown'}
    for line in clean.splitlines():
        normalized = line.casefold().strip(' .-[]\t')
        if (normalized and normalized not in placeholders
                and not normalized.startswith(('no implementation permission', 'no implementation authorization'))):
            return True
    return False


def validate(data, body, path, config):
    if not isinstance(data, dict) or set(data) != FIELDS:
        raise TicketError('invalid schema fields')
    if type(data['schema_version']) is not int or data['schema_version'] != 1:
        raise TicketError('invalid schema_version')
    if data['record_type'] != 'development-ticket' or data['ticket_project'] != config['project']:
        raise TicketError('invalid record type or project')
    if not valid_id(data['id'], prefixes(config)) or not valid_filename(path.name, data['id']):
        raise TicketError('invalid ID or filename')
    if any(data[key] not in values for key, values in ENUMS.items()):
        raise TicketError('invalid enum')
    if not text(data['summary']) or not text(data['reported_by']) or (data['owner'] is not None and not text(data['owner'])):
        raise TicketError('invalid summary or actor')
    for key in ('areas', 'repos', 'related', 'tags'):
        if not strings(data[key]):
            raise TicketError('invalid list')
    if not set(data['areas']) <= set(config['areas']) or not set(data['repos']) <= set(config['repos']):
        raise TicketError('unknown area or repo')
    if not all(valid_id(item) for item in data['related']):
        raise TicketError('invalid related IDs')
    duplicate = data['duplicate_of']
    if duplicate is not None and (not valid_id(duplicate) or duplicate == data['id']):
        raise TicketError('invalid duplicate reference')
    for key in ('created', 'updated', 'started', 'completed'):
        if key in ('started', 'completed') and data[key] is None:
            continue
        if not timestamp(data[key]):
            raise TicketError('invalid timestamp')
    content = sections(body)
    # This checks recorded evidence only; it cannot grant or authenticate authority.
    if data['status'] in ('in-progress', 'review') and (
            data['implementation_authorization'] != 'approved' or data['owner'] is None
            or data['started'] is None or not meaningful(content.get('Authorization and decisions', ''))):
        raise TicketError('work state requires recorded authorization, owner and started')
    if data['status'] == 'cancelled':
        cancellation = content.get('Authorization and decisions', '') + '\n' + content.get('History', '')
        reason = re.search(r'(?:cancellation reason|cancelled|canceled)\s*:\s*(.+)', cancellation, re.I)
        if not (reason and meaningful(reason[1])):
            raise TicketError('cancelled requires a reason in decisions or history')
    if data['completed'] is not None and data['status'] != 'done':
        raise TicketError('completed is only valid for done')
    if data['status'] == 'done':
        acceptance = content.get('Acceptance criteria', '')
        checks = re.findall(r'^\s*(?:[-*+]|\d+[.)]) \[([^\]\n]*)\][ \t]*(.*)$', acceptance, re.M)
        if (data['completed'] is None or data['verification'] != 'passed' or not checks
                or any(mark.lower() != 'x' or not meaningful(label) or 'define observable completion criteria' in label.casefold() for mark, label in checks)
                or not meaningful(content.get('Verification evidence', ''))):
            raise TicketError('done requires completion, checked acceptance and verification evidence')


def scan(root, config):
    records, errors, seen = [], 0, set()
    if not root.exists():
        return records, errors, 0
    if not root.is_dir():
        raise TicketError('ticket_dir is not a directory')
    # One flat canonical directory; never follow directory symlinks.
    paths = sorted(root.iterdir())
    total = 0
    for path in paths:
        if path.suffix.lower() != '.md' and 'sync-conflict' not in path.name.casefold() and not path.is_symlink():
            continue
        total += 1
        try:
            if 'sync-conflict' in path.name.casefold() or not path.resolve().is_relative_to(root) or not path.is_file():
                raise TicketError('conflict or unsafe file')
            source = path.read_text(encoding='utf-8')
            lines = source.splitlines(keepends=True)
            if not lines or lines[0].strip() != '---':
                raise TicketError('missing frontmatter')
            end = next((i for i in range(1, len(lines)) if lines[i].strip() == '---'), None)
            if end is None:
                raise TicketError('unclosed frontmatter')
            data = yaml.load(''.join(lines[1:end]), Loader=UniqueLoader)
            body = ''.join(lines[end + 1:])
            validate(data, body, path, config)
            if data['id'] in seen:
                raise TicketError('duplicate ID')
            seen.add(data['id'])
            records.append(data)
        except (TicketError, yaml.YAMLError, OSError, UnicodeError, RecursionError):
            errors += 1
    return records, errors, total



def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config', required=True)
    commands = parser.add_subparsers(dest='command', required=True)
    create = commands.add_parser('create')
    create.add_argument('--summary', required=True)
    create.add_argument('--kind', required=True, choices=KINDS)
    create.add_argument('--actor', required=True)
    create.add_argument('--area', action='append', default=[])
    create.add_argument('--repo', action='append', default=[])
    create.add_argument('--confidence', choices=CONFIDENCE, default='reported')
    commands.add_parser('check')
    commands.add_parser('list')
    args = parser.parse_args()
    config, root = load_config(Path(args.config))
    records, errors, total = scan(root, config)
    if args.command == 'check':
        counts = {}
        for record in records:
            counts[record['status']] = counts.get(record['status'], 0) + 1
        print(json.dumps(dict(total=total, errors=errors, statuses=counts), sort_keys=True))
        if errors:
            print(f'tickets: {errors} invalid record(s); no note contents displayed', file=sys.stderr)
        return int(bool(errors))
    if errors:
        raise TicketError(f'{errors} invalid existing record(s); run check before continuing')
    if args.command == 'list':
        print(json.dumps([{key: record[key] for key in PUBLIC} for record in records], ensure_ascii=False))
        return 0
    if not text(args.summary) or not text(args.actor):
        raise TicketError('summary and actor must be nonempty single-line text')
    if not set(args.area) <= set(config['areas']) or not set(args.repo) <= set(config['repos']):
        raise TicketError('unknown area or repo')
    if any(record['status'] not in ('done', 'cancelled') and record['summary'].casefold() == args.summary.casefold() for record in records):
        raise TicketError('active ticket with this summary exists; choose the existing note instead (no automatic merge)')
    now = datetime.now(timezone.utc).isoformat()
    # Next free number for the prefix on THIS host. Another host can mint the same
    # one before Syncthing catches up; `check` then reports a duplicate ID.
    identifier = next_id(config.get('kind_prefixes', {}).get(args.kind, config['prefix']), records)
    data = dict(schema_version=1, record_type='development-ticket', ticket_project=config['project'],
                id=identifier, summary=args.summary, kind=args.kind, status='inbox', priority='unset',
                areas=list(dict.fromkeys(args.area)), repos=list(dict.fromkeys(args.repo)), confidence=args.confidence, owner=None,
                reported_by=args.actor, created=now, updated=now, started=None, completed=None,
                implementation_authorization='none', verification='not-run', deployment='unknown',
                related=[], duplicate_of=None, tags=['development'])
    sections = ['Problem or request', 'Source and evidence', 'Expected and actual behaviour',
                'Reproduction', 'Acceptance criteria', 'Exclusions and dependencies',
                'Authorization and decisions', 'Implementation evidence', 'Verification evidence',
                'Deployment evidence', 'History']
    body = '# ' + args.summary + '\n'
    for section in sections:
        body += '\n## ' + section + '\n\n'
        if section == 'Acceptance criteria':
            body += '- [ ] Define observable completion criteria.\n'
        elif section == 'Authorization and decisions':
            body += 'No implementation permission granted.\n'
        elif section == 'History':
            body += f'- {now} — {args.actor}: captured.\n'
    root.mkdir(parents=True, exist_ok=True)
    title = filename_title(args.summary)
    name = f'{identifier} — {title}.md' if title else identifier + '.md'
    with (root / name).open('x', encoding='utf-8') as handle:
        handle.write('---\n' + yaml.safe_dump(data, sort_keys=False, allow_unicode=True) + '---\n' + body)
    print(identifier)
    return 0


if __name__ == '__main__':
    try:
        sys.exit(main())
    except (TicketError, OSError, UnicodeError, json.JSONDecodeError) as exc:
        # Never echo parser payloads or note contents (which may be sensitive).
        message = str(exc) if isinstance(exc, TicketError) else 'unable to read or write local ticket files/config'
        print('tickets: ' + message, file=sys.stderr)
        sys.exit(1)
