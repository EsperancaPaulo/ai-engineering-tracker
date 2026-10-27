"""Add empty automation-rule storage; preserve existing records and permissions."""
from sqlalchemy import insert, select, text
from models import AppMigration, AutomationRule
VERSION = '002_import_automation'


def upgrade(connection):
    if connection.dialect.name == 'postgresql':
        connection.execute(text('SELECT pg_advisory_xact_lock(830017001)'))
    AppMigration.__table__.create(connection, checkfirst=True)
    if connection.scalar(select(AppMigration.version).where(AppMigration.version == VERSION)):
        return False
    AutomationRule.__table__.create(connection, checkfirst=True)
    connection.execute(insert(AppMigration).values(version=VERSION))
    return True


if __name__ == '__main__':
    from database import engine
    with engine.begin() as connection:
        changed = upgrade(connection)
    print('Automation storage added; existing records unchanged.' if changed else 'Automation migration already applied.')
