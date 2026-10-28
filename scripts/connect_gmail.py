"""Run locally to connect one owner/project. The human completes Google's consent screen."""
import argparse,base64,hashlib,json,secrets,sys,time,webbrowser
from http.server import BaseHTTPRequestHandler,HTTPServer
from pathlib import Path
from urllib.parse import parse_qs,urlsplit,urlencode
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'backend'))
from dotenv import load_dotenv
load_dotenv(ROOT/'backend/.env')
from database import SessionLocal
from models import GmailSource,User
from tracker import project_access
import gmail_client as gmail


def client_settings(path):
    if path.is_symlink() or not path.is_file() or path.stat().st_size>20000:raise RuntimeError('Select the downloaded Google Desktop app JSON file.')
    value=json.loads(path.read_text()).get('installed',{})
    if value.get('auth_uri')!='https://accounts.google.com/o/oauth2/auth' or value.get('token_uri')!=gmail.TOKEN or not isinstance(value.get('client_id'),str) or not value['client_id'].endswith('.apps.googleusercontent.com') or not isinstance(value.get('client_secret'),str):
        raise RuntimeError('Use the downloaded Desktop app OAuth client JSON from Google.')
    return {'client_id':value['client_id'],'client_secret':value['client_secret']}


def authorize(credentials,opener=webbrowser.open):
    state=secrets.token_urlsafe(32);verifier=secrets.token_urlsafe(64)
    challenge=base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).decode().rstrip('=')
    result={}
    class Callback(BaseHTTPRequestHandler):
        def log_message(self,*args):pass
        def do_GET(self):
            parsed=urlsplit(self.path);query=parse_qs(parsed.query)
            valid=parsed.path=='/oauth/callback' and len(query.get('state',[]))==1 and secrets.compare_digest(query['state'][0],state)
            if not valid:
                self.send_response(400);self.end_headers();self.wfile.write(b'Invalid connection callback.');return
            if 'error' in query:result['error']=True
            elif len(query.get('code',[]))==1:result['code']=query['code'][0]
            else:result['error']=True
            self.send_response(200);self.send_header('Content-Type','text/plain');self.send_header('Cache-Control','no-store');self.send_header('Referrer-Policy','no-referrer');self.end_headers();self.wfile.write(b'Google response received. Return to the local connection tool. You can close this tab.')
    with HTTPServer(('127.0.0.1',0),Callback) as server:
        server.timeout=1
        redirect=f'http://127.0.0.1:{server.server_port}/oauth/callback'
        url='https://accounts.google.com/o/oauth2/v2/auth?'+urlencode({'client_id':credentials['client_id'],'redirect_uri':redirect,'response_type':'code','scope':gmail.SCOPE,'state':state,'code_challenge':challenge,'code_challenge_method':'S256','access_type':'offline','prompt':'consent'})
        print('Opening Google permission screen. Read-only access covers the mailbox; this app filters Tracker Inbox. Approve yourself only if this matches your intended account and permissions. No email will be collected during connection.')
        if not opener(url):raise RuntimeError('Could not open the browser. Retry from your local desktop terminal.')
        deadline=time.monotonic()+300
        while not result and time.monotonic()<deadline:server.handle_request()
    if 'code' not in result:raise RuntimeError('Connection was cancelled or timed out. No credentials were saved.')
    with gmail.http_client() as client:
        value=gmail.bounded(client,'POST',gmail.TOKEN,data={**credentials,'code':result['code'],'code_verifier':verifier,'redirect_uri':redirect,'grant_type':'authorization_code'})
        if value.get('scope')!=gmail.SCOPE or not isinstance(value.get('refresh_token'),str) or not isinstance(value.get('access_token'),str) or not 1<=int(value.get('expires_in',0))<=86400:raise RuntimeError('Google did not return the expected read-only offline permission. No credentials saved.')
        headers={'Authorization':'Bearer '+value['access_token']}
        profile=gmail.bounded(client,'GET',gmail.API+'/profile',headers=headers)
        email=profile.get('emailAddress','')
        if not isinstance(email,str) or '@' not in email:raise RuntimeError('Could not identify the selected Gmail mailbox.')
        labels=gmail.bounded(client,'GET',gmail.API+'/labels',headers=headers).get('labels',[])
        label=next((entry.get('id') for entry in labels if entry.get('name')==gmail.LABEL),None)
        if not label:raise RuntimeError('Create the Tracker Inbox label in the selected Gmail account, then reconnect.')
    return {**credentials,'access_token':value['access_token'],'refresh_token':value['refresh_token'],'expires_at':time.time()+int(value['expires_in']),'scope':gmail.SCOPE,'account_key':hashlib.sha256(email.strip().lower().encode()).hexdigest()},label


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--credentials',type=Path,required=True);parser.add_argument('--project-id',type=int,required=True);parser.add_argument('--owner-id',type=int,required=True)
    args=parser.parse_args();credentials=client_settings(args.credentials)
    with SessionLocal() as db:
        owner=db.get(User,args.owner_id)
        if not owner:raise RuntimeError('Owner account not found.')
        project_access(db,owner,args.project_id,owner_only=True)
    value,label=authorize(credentials)
    with SessionLocal() as db:
        owner=db.get(User,args.owner_id);project_access(db,owner,args.project_id,write=True,owner_only=True)
        source=db.get(GmailSource,args.project_id)
        if source and (source.owner_id!=args.owner_id or source.account_key!=value['account_key']):raise RuntimeError('This project is bound to a different mailbox. Keep the existing binding; use a different project for this mailbox.')
        with gmail.credential_lock(args.project_id):
            gmail.write_private(gmail.credential_path(args.project_id),{**value,'project_id':args.project_id,'owner_id':args.owner_id})
        if source:
            source.label_id=label;source.automatic=False;source.cursor=None;source.next_poll=None;source.failures=0;source.last_result='Reconnected; automatic collection paused.'
        else:db.add(GmailSource(project_id=args.project_id,owner_id=args.owner_id,account_key=value['account_key'],label_id=label))
        db.commit()
    print('Gmail connected privately to the selected project. Automatic collection is off. Open Gmail drafts in the app to collect and review a test message. No emails collected yet.')

if __name__=='__main__':
    try:main()
    except Exception:
        # Provider/client errors must never print token-bearing request or credential data.
        raise SystemExit('Gmail connection did not finish. Check Desktop JSON, project/owner IDs, Google test-user access and the Tracker Inbox label. No mailbox contents were imported. Retry locally; keep all credentials private.') from None
