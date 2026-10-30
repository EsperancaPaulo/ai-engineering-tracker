"""Add empty in-app update settings, progress baselines and personal reminders."""
from sqlalchemy import insert,select,text
from models import AppMigration,NotificationSettings,ProjectProgress,TaskReminder
VERSION='005_in_app_updates'

def upgrade(connection):
    if connection.dialect.name=='postgresql':connection.execute(text('SELECT pg_advisory_xact_lock(830017001)'))
    AppMigration.__table__.create(connection,checkfirst=True)
    if connection.scalar(select(AppMigration.version).where(AppMigration.version==VERSION)):return False
    for model in (NotificationSettings,ProjectProgress,TaskReminder):model.__table__.create(connection,checkfirst=True)
    connection.execute(insert(AppMigration).values(version=VERSION));return True

if __name__=='__main__':
    from database import engine
    with engine.begin() as connection:changed=upgrade(connection)
    print('In-app update storage added.' if changed else 'In-app update migration already applied.')
