"""Fixed-origin Gmail read-only client. Private credentials never leave the local backend."""
import base64,fcntl,hashlib,json,os,re,tempfile,time
from contextlib import contextmanager
from pathlib import Path
import httpx
from fastapi import HTTPException
ROOT=Path(__file__).resolve().parents[1]
SCOPE='https://www.googleapis.com/auth/gmail.readonly'
API='https://gmail.googleapis.com/gmail/v1/users/me'
TOKEN='https://oauth2.googleapis.com/token'
LABEL='Tracker Inbox'


def folder():
    path=ROOT/'.private'
    if path.is_symlink():raise RuntimeError('Private credential folder cannot be a symbolic link.')
    path.mkdir(mode=0o700,exist_ok=True);path.chmod(0o700)
    return path


def credential_path(project_id):return folder()/f'gmail-{int(project_id)}.json'


def read_private(path):
    if path.is_symlink() or not path.is_file() or path.stat().st_mode&0o077:
        raise RuntimeError('Gmail credential file must be private, regular and readable only by its owner.')
    if path.stat().st_size>20000:raise RuntimeError('Invalid Gmail credential file.')
    return json.loads(path.read_text())


def write_private(path,value):
    fd,name=tempfile.mkstemp(prefix='.gmail-',dir=folder())
    try:
        with os.fdopen(fd,'w') as output:json.dump(value,output)
        os.replace(name,path)
    finally:
        if os.path.exists(name):os.unlink(name)


@contextmanager
def credential_lock(project_id):
    path=folder()/f'gmail-{int(project_id)}.lock'
    fd=os.open(path,os.O_CREAT|os.O_RDWR|os.O_NOFOLLOW,0o600)
    with os.fdopen(fd,'w') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX)
        try:yield
        finally:fcntl.flock(lock,fcntl.LOCK_UN)


def bounded(client,method,url,**kwargs):
    # Never use provider error bodies: they may contain credentials or mailbox data.
    try:
        with client.stream(method,url,**kwargs) as response:
            if response.status_code>=400:
                raise HTTPException(503,'Gmail could not complete this request. Reconnect for expired access, or wait before retrying.')
            if response.status_code!=200:raise HTTPException(503,'Gmail returned an unexpected response.')
            data=bytearray()
            for chunk in response.iter_bytes():
                if len(data)+len(chunk)>550000:raise HTTPException(413,'Email is too large for this importer.')
                data.extend(chunk)
        value=json.loads(data)
        if not isinstance(value,dict):raise ValueError()
        return value
    except (httpx.HTTPError,ValueError,TypeError):
        raise HTTPException(503,'Gmail is unavailable. No mailbox changes were made; try later.') from None


def http_client():return httpx.Client(timeout=httpx.Timeout(8,connect=4),follow_redirects=False,trust_env=False)


def token(project_id,owner_id,account_key):
    with credential_lock(project_id):
        path=credential_path(project_id)
        try:value=read_private(path)
        except (RuntimeError,ValueError,FileNotFoundError):raise HTTPException(503,'Connect Gmail locally before collecting messages.') from None
        if not isinstance(value,dict) or any(not isinstance(value.get(key),str) or not value[key] for key in ('client_id','client_secret','refresh_token','access_token','account_key')) or not isinstance(value.get('expires_at'),(int,float)):
            raise HTTPException(503,'Invalid local Gmail credentials. Reconnect locally.')
        if value.get('project_id')!=project_id or value.get('owner_id')!=owner_id or value.get('account_key')!=account_key or value.get('scope')!=SCOPE:
            raise HTTPException(503,'Gmail credentials do not match this project and owner. Reconnect locally.')
        if value.get('expires_at',0)<time.time()+60:
            with http_client() as client:
                refreshed=bounded(client,'POST',TOKEN,data={'client_id':value['client_id'],'client_secret':value['client_secret'],'refresh_token':value['refresh_token'],'grant_type':'refresh_token'})
            if not isinstance(refreshed.get('access_token'),str) or not 1<=int(refreshed.get('expires_in',0))<=86400:raise HTTPException(503,'Gmail access could not be refreshed. Reconnect locally.')
            if refreshed.get('scope',SCOPE)!=SCOPE:raise HTTPException(503,'Unexpected Gmail permission scope. Reconnect locally.')
            value.update(access_token=refreshed['access_token'],expires_at=time.time()+int(refreshed['expires_in']))
            write_private(path,value)
        return value['access_token']


def read_page(project_id,owner_id,account_key,label_id,cursor):
    access=token(project_id,owner_id,account_key)
    if not re.fullmatch(r'[A-Za-z0-9_-]{1,200}',label_id):raise HTTPException(503,'Invalid Gmail label binding. Reconnect locally.')
    with http_client() as client:
        headers={'Authorization':'Bearer '+access}
        params={'labelIds':label_id,'maxResults':5,'includeSpamTrash':'false'}
        if cursor:params['pageToken']=cursor
        listing=bounded(client,'GET',API+'/messages',params=params,headers=headers)
        messages=listing.get('messages',[])
        if not isinstance(messages,list) or len(messages)>5:raise HTTPException(503,'Unexpected Gmail message list.')
        result=[]
        for item in messages:
            mid=item.get('id','') if isinstance(item,dict) else ''
            if not isinstance(mid,str) or not re.fullmatch(r'[A-Za-z0-9_-]{1,200}',mid):raise HTTPException(503,'Unexpected Gmail message identifier.')
            key=hashlib.sha256(f'{project_id}:{account_key}:{mid}'.encode()).hexdigest()
            try:
                message=bounded(client,'GET',API+'/messages/'+mid,params={'format':'raw'},headers=headers)
                # Labels may change between listing and reading. Never queue a moved message.
                if label_id not in message.get('labelIds',[]):continue
                encoded=message.get('raw','')
                if not isinstance(encoded,str) or len(encoded)>350000:raise HTTPException(413,'Email is too large for this importer.')
                raw=base64.b64decode(encoded+'='*(-len(encoded)%4),altchars=b'-_',validate=True)
                result.append((key,raw,''))
            except HTTPException as error:
                if error.status_code!=413:raise
                result.append((key,None,'Email exceeds the local import size limit; use a smaller saved email.'))
            except (ValueError,TypeError):
                result.append((key,None,'Email content could not be decoded. Use a saved .eml file instead.'))
        next_cursor=listing.get('nextPageToken')
        if next_cursor is not None and (not isinstance(next_cursor,str) or len(next_cursor)>2000):raise HTTPException(503,'Unexpected Gmail page cursor.')
        return result,next_cursor
