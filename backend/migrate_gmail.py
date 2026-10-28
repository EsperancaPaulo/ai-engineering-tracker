"""Add empty Gmail source/queue storage without changing existing records."""
from sqlalchemy import insert,select,text
from models import AppMigration,GmailSource,GmailDraft
VERSION='004_gmail_review_queue'

def upgrade(connection):
    if connection.dialect.name=='postgresql':connection.execute(text('SELECT pg_advisory_xact_lock(830017001)'))
    AppMigration.__table__.create(connection,checkfirst=True)
    if connection.scalar(select(AppMigration.version).where(AppMigration.version==VERSION)):return False
    for model in (GmailSource,GmailDraft):model.__table__.create(connection,checkfirst=True)
    connection.execute(insert(AppMigration).values(version=VERSION));return True

if __name__=='__main__':
    from database import engine
    with engine.begin() as connection:changed=upgrade(connection)
    print('Gmail queue storage added.' if changed else 'Gmail migration already applied.')
