"""Bounded CSV task imports with owner review, signed snapshots, and replay protection."""
import csv
from email import policy as email_policy
from email.parser import BytesParser
from html.parser import HTMLParser
import hashlib
import io
import json
from datetime import datetime, timedelta, timezone
from typing import Annotated

import jwt
from fastapi import APIRouter, HTTPException, Request, Response
from pydantic import BaseModel, ConfigDict, Field, SecretStr
from sqlalchemy import select

from auth import ALGORITHM, ISSUER, SECRET_KEY, Database
from models import ActivityLog, Task
from tracker import CurrentUser, project_access, record
import automation

router = APIRouter(prefix='/api', tags=['File imports'])
PREVIEW_ISSUER = ISSUER+'/csv-preview'
MAX_BYTES = 256*1024
MAX_ROWS = 100
MAX_SELECTION = 25
TEMPLATE = 'title,description,priority\nReview release checklist,Check acceptance criteria and record the result,medium\nPrepare weekly update,Collect completed work and blockers,low\n'


class ImportSelection(BaseModel):
    model_config = ConfigDict(extra='forbid')
    preview_token: SecretStr = Field(min_length=1, max_length=3000000)
    row_numbers: list[Annotated[int, Field(ge=2, le=MAX_ROWS+1)]] = Field(min_length=1, max_length=MAX_SELECTION)


def fingerprint(row):
    content = [row['title'], row['description'], row['priority']]
    return hashlib.sha256(json.dumps(content, ensure_ascii=True, separators=(',', ':')).encode()).hexdigest()


def parse_csv(raw):
    if not raw or len(raw) > MAX_BYTES:
        raise HTTPException(413, 'Choose a nonempty CSV file no larger than 256 KB.')
    try:
        text = raw.decode('utf-8-sig')
    except UnicodeDecodeError:
        raise HTTPException(422, 'Save the file as CSV UTF-8, then try again.') from None
    if '\x00' in text:
        raise HTTPException(422, 'This file contains unsupported binary content. Choose a CSV UTF-8 task list.')
    reader = csv.reader(io.StringIO(text, newline=''), strict=True)
    try:
        headers = [value.strip().lower() for value in next(reader)]
        if 'title' not in headers or len(set(headers)) != len(headers) or set(headers)-{'title', 'description', 'priority'}:
            raise HTTPException(422, 'Use a title column, with optional description and priority columns. Download the template for the expected format.')
        rows, errors = [], []
        for number, values in enumerate(reader, start=2):
            if number > MAX_ROWS+1:
                raise HTTPException(422, 'A preview supports at most 100 data rows. Split this task list into smaller files.')
            if not any(value.strip() for value in values):
                continue
            problem = None
            if len(values) != len(headers):
                problem = 'The number of values does not match the column headings.'
                data = {}
            else:
                data = {key: value.replace('\r\n', '\n').replace('\r', '\n').strip() for key, value in zip(headers, values)}
                data.setdefault('description', '')
                data['priority'] = data.get('priority', '').lower() or 'medium'
                if not 1 <= len(data['title']) <= 200:
                    problem = 'Title must contain 1–200 characters.'
                elif any(ord(char) < 32 for char in data['title']):
                    problem = 'Title must be a single line without control characters.'
                elif len(data['description']) > 8000:
                    problem = 'Description must contain no more than 8,000 characters.'
                elif any(ord(char) < 32 and char not in '\n\t' for char in data['description']):
                    problem = 'Description contains unsupported control characters.'
                elif data['priority'] not in ('low', 'medium', 'high'):
                    problem = 'Priority must be low, medium or high.'
            if problem:
                errors.append({'row_number': number, 'message': problem})
            else:
                rows.append({'row_number': number, **data, 'fingerprint': fingerprint(data)})
        if not rows and not errors:
            raise HTTPException(422, 'This file has headings but no task rows.')
        return rows, errors
    except (csv.Error, StopIteration):
        raise HTTPException(422, 'CSV could not be read. Check commas and quoted fields, or use the template.') from None


class PlainHTML(HTMLParser):
    def __init__(self):super().__init__();self.parts=[];self.hidden=0
    def handle_starttag(self,tag,attrs):
        if tag in ('script','style','head'):self.hidden+=1
        if tag in ('p','br','div','li'):self.parts.append('\n')
    def handle_endtag(self,tag):
        if tag in ('script','style','head') and self.hidden:self.hidden-=1
    def handle_data(self,data):
        if not self.hidden:self.parts.append(data)


def parse_email(raw):
    if not raw or len(raw)>MAX_BYTES:raise HTTPException(413,'Choose an email file no larger than 256 KB.')
    try:
        message=BytesParser(policy=email_policy.default).parsebytes(raw)
        if message.defects:raise ValueError()
        title=' '.join(str(message.get('Subject','')).split())
        if not title or len(title)>200 or any(ord(char)<32 for char in title):raise ValueError()
        part=message.get_body(preferencelist=('plain','html'))
        if part is None or part.get_content_disposition()=='attachment':raise ValueError()
        body=part.get_content()
        if not isinstance(body,str):raise ValueError()
        if part.get_content_type()=='text/html':
            parser=PlainHTML();parser.feed(body);body=''.join(parser.parts)
        body=body.replace('\r\n','\n').replace('\r','\n').strip()
        if not body or len(body)>7800 or any(ord(char)<32 and char not in '\n\t' for char in body):raise ValueError()
        row={'row_number':2,'title':title,'description':body,'priority':'medium'}
        row['fingerprint']=fingerprint(row)
        return [row],[]
    except (ValueError,TypeError,LookupError,AttributeError):
        raise HTTPException(422,'Email could not be imported. Use an .eml file with a subject up to 200 characters and readable message text up to 7,800 characters. Attachments are not imported.') from None



def existing_fingerprints(db, project_id):
    fingerprints = set()
    for details in db.scalars(select(ActivityLog.details).where(ActivityLog.action == 'File task imported')):
        try:
            value = json.loads(details)
            if value.get('project_id') == project_id:
                fingerprints.add(value['fingerprint'])
        except (ValueError, TypeError, KeyError, AttributeError):
            continue
    # Also avoid duplicating identical current tasks created through another workflow.
    for task in db.scalars(select(Task).where(Task.project_id == project_id)):
        fingerprints.add(fingerprint({'title': task.title.strip(), 'description': (task.description or '').replace('\r\n', '\n').replace('\r', '\n').strip(), 'priority': task.priority}))
    return fingerprints


@router.get('/task-import-template.csv', include_in_schema=False)
def download_template():
    return Response(TEMPLATE, media_type='text/csv', headers={'Content-Disposition': 'attachment; filename="task-import-template.csv"'})


@router.post('/projects/{project_id}/files/preview')
async def preview(project_id: int, request: Request, db: Database, user: CurrentUser):
    project_access(db, user, project_id, owner_only=True)
    content_type=request.headers.get('content-type','').split(';')[0].strip().lower()
    if content_type not in ('text/csv','message/rfc822'):
        raise HTTPException(415,'Choose a CSV UTF-8 or .eml email file.')
    user_id = user.id
    db.rollback()
    raw = bytearray()
    async for chunk in request.stream():
        if len(raw)+len(chunk) > MAX_BYTES:
            raise HTTPException(413, 'Choose a CSV file no larger than 256 KB.')
        raw.extend(chunk)
    source='email' if content_type=='message/rfc822' else 'csv'
    rows, errors = parse_email(bytes(raw)) if source=='email' else parse_csv(bytes(raw))
    project_access(db, user, project_id, owner_only=True)
    active_rules = automation.rule_set(db, project_id)
    for row in rows:
        row['automation'] = automation.effects(db, project_id, active_rules, row['title'], row['description'])
    existing = existing_fingerprints(db, project_id)
    seen = set()
    output = []
    for row in rows:
        duplicate = 'Already imported or identical task exists' if row['fingerprint'] in existing else 'Repeated row in this file' if row['fingerprint'] in seen else None
        output.append({**row, 'duplicate_reason': duplicate})
        seen.add(row['fingerprint'])
    now = datetime.now(timezone.utc)
    token = jwt.encode({'iss': PREVIEW_ISSUER, 'sub': str(user_id), 'aud': str(project_id), 'iat': now, 'exp': now+timedelta(minutes=5), 'rows': rows, 'rule_digest': automation.digest(active_rules), 'source':source}, SECRET_KEY, algorithm=ALGORITHM)
    return {'preview_token': token, 'rows': output, 'errors': errors, 'maximum_selection': MAX_SELECTION, 'source':source}


@router.post('/projects/{project_id}/files/import')
def import_selected(project_id: int, data: ImportSelection, db: Database, user: CurrentUser):
    project_access(db, user, project_id, write=True, owner_only=True)
    try:
        claims = jwt.decode(data.preview_token.get_secret_value(), SECRET_KEY, algorithms=[ALGORITHM], issuer=PREVIEW_ISSUER, audience=str(project_id), options={'require': ['iss', 'sub', 'aud', 'iat', 'exp']})
        if claims['sub'] != str(user.id):
            raise ValueError()
        rows = {row['row_number']: row for row in claims['rows']}
        selected = list(dict.fromkeys(data.row_numbers))
        if any(number not in rows for number in selected):
            raise ValueError()
    except (jwt.InvalidTokenError, ValueError, KeyError, TypeError):
        raise HTTPException(422, 'Preview expired or does not match this import. Preview the file again.') from None
    automation.check_snapshot(db, project_id, claims.get('rule_digest'))
    existing = existing_fingerprints(db, project_id)
    created, skipped = [], []
    for number in selected:
        row = rows[number]
        if row['fingerprint'] in existing:
            skipped.append(number)
            continue
        task = Task(title=row['title'], description=row['description'], priority=row['priority'], status='todo', assigned_to=user.id, project_id=project_id)
        db.add(task)
        db.flush()
        automation.apply(db, user, project_id, task, row.get('automation'), claims.get('source','csv'))
        record(db, user, 'File task imported', json.dumps({'summary': f"{claims.get('source','csv').upper()} row {number}: {row['title']}", 'source':claims.get('source','csv'), 'project_id': project_id, 'task_id': task.id, 'row_number': number, 'fingerprint': row['fingerprint']}))
        existing.add(row['fingerprint'])
        created.append(task.id)
    db.commit()
    return {'imported_count': len(created), 'created_task_ids': created, 'skipped_row_numbers': skipped}
