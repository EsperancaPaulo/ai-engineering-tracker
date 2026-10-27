"""Private local PostgreSQL backups and isolated restore verification; never replace the live database."""
import argparse,hashlib,json,os,subprocess,sys,secrets
from datetime import datetime,timezone
from pathlib import Path
from dotenv import dotenv_values
from sqlalchemy import create_engine,inspect,select
from sqlalchemy.engine import make_url
ROOT=Path(__file__).resolve().parents[1]


def fingerprints(engine):
    sys.path.insert(0,str(ROOT/'backend'))
    import models
    from database import Base
    found=set(inspect(engine).get_table_names())
    result={}
    with engine.connect() as connection:
        for table in Base.metadata.sorted_tables:
            if table.name not in found:continue
            rows=[]
            for row in connection.execute(select(table)):
                encoded=json.dumps(dict(row._mapping),sort_keys=True,default=lambda value:value.astimezone(timezone.utc).isoformat() if isinstance(value,datetime) and value.tzinfo else str(value))
                rows.append(hashlib.sha256(encoded.encode()).hexdigest())
            result[table.name]=sorted(rows)
    return result


def pg_args(url):
    args=['-d',url.database]
    if url.host:args+=['-h',url.host]
    if url.port:args+=['-p',str(url.port)]
    if url.username:args+=['-U',url.username]
    return args


def run(args,env,**kwargs):
    result=subprocess.run(args,env=env,stderr=subprocess.PIPE,**kwargs)
    if result.returncode:raise RuntimeError('Database utility failed. No live restore was performed; check local PostgreSQL tools and permissions.')
    return result


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action',choices=['backup','verify-restore'])
    parser.add_argument('--archive',type=Path)
    args=parser.parse_args()
    config=dotenv_values(ROOT/'backend/.env')
    url=make_url(config['DATABASE_URL'])
    if not url.drivername.startswith('postgresql'):raise RuntimeError('This maintenance tool supports PostgreSQL only.')
    # Configure imports privately without echoing credentials.
    os.environ['DATABASE_URL']=config['DATABASE_URL']
    engine=create_engine(url)
    env={'PATH':os.environ.get('PATH',''),'PGPASSWORD':url.password or ''}
    if args.action=='backup':
        folder=ROOT/'backups';folder.mkdir(mode=0o700,exist_ok=True);folder.chmod(0o700)
        path=folder/('tracker-'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')+'-'+secrets.token_hex(2)+'.dump')
        before=fingerprints(engine)
        with path.open('xb') as output:
            path.chmod(0o600);run(['pg_dump','--format=custom','--no-owner','--no-acl',*pg_args(url)],env,stdout=output)
        run(['pg_restore','--list',str(path)],env,stdout=subprocess.DEVNULL)
        after=fingerprints(engine)
        if before!=after:raise RuntimeError('Records changed during backup. Retry during a quiet period before using this archive for restore verification.')
        manifest=path.with_suffix('.manifest.json');manifest.write_text(json.dumps({'sha256':hashlib.sha256(path.read_bytes()).hexdigest(),'records':after},sort_keys=True));manifest.chmod(0o600)
        print('Private backup created and archive-verified: '+path.name)
        return
    path=args.archive.resolve() if args.archive else None
    folder=(ROOT/'backups').resolve()
    if not path or path.parent!=folder or path.suffix!='.dump':raise RuntimeError('Choose a private archive inside this project’s backups folder.')
    manifest=json.loads(path.with_suffix('.manifest.json').read_text())
    if hashlib.sha256(path.read_bytes()).hexdigest()!=manifest['sha256']:raise RuntimeError('Archive checksum mismatch; restore verification stopped.')
    import psycopg
    from psycopg import sql
    temporary='tracker_restore_'+secrets.token_hex(6)
    admin_url=url.set(database='postgres')
    params={'dbname':'postgres'}
    if url.host:params['host']=url.host
    if url.port:params['port']=url.port
    if url.username:params['user']=url.username
    if url.password:params['password']=url.password
    with psycopg.connect(**params,autocommit=True) as admin:
        admin.execute(sql.SQL('CREATE DATABASE {}').format(sql.Identifier(temporary)))
        try:
            admin.execute(sql.SQL('REVOKE ALL ON DATABASE {} FROM PUBLIC').format(sql.Identifier(temporary)))
            target=url.set(database=temporary)
            run(['pg_restore','--no-owner','--no-acl',*pg_args(target),str(path)],env,stdout=subprocess.DEVNULL)
            restored=create_engine(target)
            try:
                if fingerprints(restored)!=manifest['records']:raise RuntimeError('Restored records do not match the backup manifest.')
            finally:restored.dispose()
            print('Restore drill passed in an isolated temporary database; all record fingerprints match. Live database untouched.')
        finally:admin.execute(sql.SQL('DROP DATABASE {} WITH (FORCE)').format(sql.Identifier(temporary)))


if __name__=='__main__':
    try:main()
    except (RuntimeError,KeyError,FileNotFoundError) as error:raise SystemExit(str(error)) from None
