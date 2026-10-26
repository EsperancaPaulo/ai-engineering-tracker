"""Local dictionary/pattern checks only. Never send passwords to external services."""
import json
import re
import unicodedata
from pathlib import Path
from zxcvbn import zxcvbn

POLICY = json.loads((Path(__file__).resolve().parent.parent/'shared/password-policy.json').read_text())


def password_problem(password, name='', email=''):
    if not POLICY['minimum_length'] <= len(password) <= POLICY['maximum_length']:
        return 'Use between 15 and 128 characters.'
    normalized = unicodedata.normalize('NFKC',password).casefold()
    letters = ''.join(char for char in normalized if char.isalpha())
    roots = POLICY['common_roots'] + [name.replace(' ','').casefold(),email.split('@')[0].casefold()]
    if any(root and re.fullmatch(f'(?:{re.escape(root)})+',letters) for root in roots):
        return 'Avoid common passwords and simple versions of your name or email.'
    if ''.join(char for char in normalized if char.isalnum()) in POLICY['common_phrases']:
        return 'Choose an original passphrase rather than a well-known example.'
    result = zxcvbn(password,user_inputs=[name,email,email.split('@')[0]],max_length=128)
    if result['score'] < POLICY['minimum_score']:
        return 'This password is too easy to guess. Try a longer, less predictable passphrase.'
    return None
