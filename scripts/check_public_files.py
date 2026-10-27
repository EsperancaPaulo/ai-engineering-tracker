"""Check the staged Git snapshot before publication. Never print secret values."""
from pathlib import Path
import re
import subprocess
from urllib.parse import urlsplit, unquote

from dotenv import dotenv_values

ROOT = Path(__file__).resolve().parents[1]


def git(*args):
    return subprocess.check_output(['git', '-C', str(ROOT), *args])


private_values = []
for file in [ROOT / '.env', ROOT / 'backend/.env']:
    if file.exists():
        values = dotenv_values(file)
        private_values.extend(value.encode() for key,value in values.items() if value and len(value) >= 8 and re.search(r'SECRET|PASSWORD|TOKEN|PRIVATE_KEY|DATABASE_URL|API_KEY|WEBHOOK',key,re.I))
        url = values.get('DATABASE_URL')
        if url:
            password = urlsplit(url).password
            if password and len(unquote(password)) >= 4:
                private_values.append(unquote(password).encode())

patterns = [
    rb'-----BEGIN (?:RSA |EC |OPENSSH |DSA |ENCRYPTED )?PRIVATE KEY-----',
    rb'gh[pousr]_[A-Za-z0-9]{20,}',
    rb'github_pat_[A-Za-z0-9_]{30,}',
    rb'sk-(?:proj-|svcacct-)?[A-Za-z0-9_-]{30,}',
    rb'AKIA[A-Z0-9]{16}',
    rb'xox[baprs]-[A-Za-z0-9-]{20,}',
    rb'https://hooks[.]slack[.]com/services/T[A-Z0-9]{8,}/B[A-Z0-9]{8,}/[A-Za-z0-9]{20,}',
    rb'AIza[0-9A-Za-z_-]{30,}',
    rb'eyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}',
]
compiled = [re.compile(pattern) for pattern in patterns]
blocked_parts = {'.venv', 'node_modules', '__pycache__', '.pytest_cache', 'work', 'outputs', 'uploads', 'dumps', 'backups'}
blocked_suffixes = {'.db', '.sqlite', '.sqlite3', '.dump', '.backup', '.log', '.pem', '.key', '.p12', '.pfx', '.pyc'}
failures = []
entries = [entry for entry in git('ls-files', '--stage', '-z').split(b'\0') if entry]
if not entries:
    raise SystemExit('No staged/tracked files to inspect. Stage intended public files first.')
for entry in entries:
    metadata, filename = entry.split(b'\t', 1)
    mode, _, stage = metadata.split()
    path = filename.decode()
    file = Path(path)
    if mode not in (b'100644', b'100755') or stage != b'0':
        failures.append((path, 'unsupported file mode or unresolved merge'))
        continue
    if (blocked_parts.intersection(file.parts) or file.suffix.lower() in blocked_suffixes
            or (file.name.startswith('.env') and file.name != '.env.example')):
        failures.append((path, 'private/runtime file'))
        continue
    data = git('show', ':' + path)
    if any(value in data for value in private_values):
        failures.append((path, 'matches a local secret'))
    if any(pattern.search(data) for pattern in compiled):
        failures.append((path, 'credential-like content'))
    if re.search(rb'/Users/[A-Za-z0-9_.-]+/', data) or re.search(rb'[A-Za-z0-9._%+-]+@gmail[.]com', data):
        failures.append((path, 'personal path or email; review before publication'))
if failures:
    for path, reason in failures:
        print(f'BLOCKED: {path}: {reason}')
    raise SystemExit(1)
print(f'Passed: {len(entries)} indexed files checked for private paths, local secrets, and common credential formats.')
print('This focused check is a safeguard, not a guarantee against all possible secrets.')
