"""Versioned, additive migration. Back up PostgreSQL before running against real data."""
import argparse
from sqlalchemy import insert, select, text
from models import AppMigration, Project, ProjectMember, User

VERSION = '001_project_membership'


def upgrade(connection, legacy_owner_id=None):
    if connection.dialect.name == 'postgresql':
        connection.execute(text('SELECT pg_advisory_xact_lock(830017001)'))
    AppMigration.__table__.create(connection, checkfirst=True)
    if connection.scalar(select(AppMigration.version).where(AppMigration.version == VERSION)):
        return False
    ProjectMember.__table__.create(connection, checkfirst=True)
    project_ids = list(connection.scalars(select(Project.id).where(~select(ProjectMember.project_id).where(ProjectMember.project_id == Project.id).exists())))
    user_ids = list(connection.scalars(select(User.id).order_by(User.id)))
    if project_ids:
        if legacy_owner_id is None and len(user_ids) == 1:
            legacy_owner_id = user_ids[0]
        if legacy_owner_id not in user_ids:
            raise ValueError('Existing projects need an explicit valid --legacy-owner-id when there is not exactly one user. No user records will be changed.')
        # Preserve pre-existing shared access; new accounts receive no automatic access.
        connection.execute(insert(ProjectMember), [
            {'project_id': project_id, 'user_id': user_id,
             'role': 'owner' if user_id == legacy_owner_id else 'editor'}
            for project_id in project_ids for user_id in user_ids
        ])
    connection.execute(insert(AppMigration).values(version=VERSION))
    return True


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--legacy-owner-id', type=int)
    args = parser.parse_args()
    from database import engine
    try:
        with engine.begin() as connection:
            changed = upgrade(connection, args.legacy_owner_id)
    except ValueError as error:
        parser.exit(1, str(error) + '\n')
    print('Applied project membership migration.' if changed else 'Migration already applied; no changes.')
