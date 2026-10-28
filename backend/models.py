from datetime import datetime, timezone

from sqlalchemy import (
    String,
    Integer,
    ForeignKey,
    DateTime,
    Text,
    CheckConstraint,
    Index,
    text
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database import Base


def utc_now():
    return datetime.now(timezone.utc)


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100))
    email: Mapped[str] = mapped_column(String(255), unique=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    role: Mapped[str] = mapped_column(String(30), default="developer")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now
    )


class Project(Base):
    __tablename__ = "projects"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(150))
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now
    )


class Task(Base):
    __tablename__ = "tasks"

    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(200))
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(30), default="todo")
    priority: Mapped[str] = mapped_column(String(20), default="medium")

    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"))
    assigned_to: Mapped[int | None] = mapped_column(
        ForeignKey("users.id"), nullable=True
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now
    )


class ActivityLog(Base):
    __tablename__ = "activity_logs"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id"), nullable=True
    )
    action: Mapped[str] = mapped_column(String(100))
    details: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now
    )


class ProjectMember(Base):
    __tablename__ = 'project_members'
    project_id: Mapped[int] = mapped_column(ForeignKey('projects.id', ondelete='CASCADE'), primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey('users.id'), primary_key=True)
    role: Mapped[str] = mapped_column(String(20))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)

    __table_args__ = (
        CheckConstraint("role IN ('owner', 'editor', 'viewer')", name='project_member_role'),
        Index('one_owner_per_project', 'project_id', unique=True,
              postgresql_where=text("role = 'owner'"), sqlite_where=text("role = 'owner'")),
    )


class AppMigration(Base):
    __tablename__ = 'app_migrations'
    version: Mapped[str] = mapped_column(String(80), primary_key=True)
    applied_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class AutomationRule(Base):
    __tablename__ = 'automation_rules'
    id: Mapped[int] = mapped_column(primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey('projects.id', ondelete='CASCADE'), index=True)
    name: Mapped[str] = mapped_column(String(80))
    keyword: Mapped[str] = mapped_column(String(80))
    match_field: Mapped[str] = mapped_column(String(20), default='title')
    priority: Mapped[str | None] = mapped_column(String(20), nullable=True)
    assigned_to: Mapped[int | None] = mapped_column(ForeignKey('users.id'), nullable=True)
    checklist: Mapped[str] = mapped_column(Text, default='[]')
    enabled: Mapped[bool] = mapped_column(default=False)
    revision: Mapped[int] = mapped_column(default=1)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class InboxNotice(Base):
    __tablename__ = 'inbox_notices'
    id: Mapped[int] = mapped_column(primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey('projects.id',ondelete='CASCADE'),index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey('users.id'),index=True)
    task_id: Mapped[int | None] = mapped_column(ForeignKey('tasks.id',ondelete='SET NULL'),nullable=True)
    event_key: Mapped[str] = mapped_column(String(64),unique=True)
    message: Mapped[str] = mapped_column(String(500))
    read: Mapped[bool] = mapped_column(default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True),default=utc_now)


class SlackDelivery(Base):
    __tablename__ = 'slack_deliveries'
    id: Mapped[int] = mapped_column(primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey('projects.id',ondelete='CASCADE'),index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey('users.id'))
    delivery_key: Mapped[str] = mapped_column(String(64),unique=True)
    state: Mapped[str] = mapped_column(String(20),default='sending')
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True),default=utc_now)


class RevokedSession(Base):
    __tablename__ = 'revoked_sessions'
    token_digest: Mapped[str] = mapped_column(String(64),primary_key=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True),index=True)


class UserSecurity(Base):
    __tablename__ = 'user_security'
    user_id: Mapped[int] = mapped_column(ForeignKey('users.id'),primary_key=True)
    session_version: Mapped[int] = mapped_column(default=0)
    notifications_enabled: Mapped[bool] = mapped_column(default=True)
    email_verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True),nullable=True)


class EmailGrant(Base):
    __tablename__ = 'email_grants'
    token_digest: Mapped[str] = mapped_column(String(64),primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey('users.id'),index=True)
    kind: Mapped[str] = mapped_column(String(20))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True),index=True)
    consumed: Mapped[bool] = mapped_column(default=False)


class GmailSource(Base):
    __tablename__ = 'gmail_sources'
    project_id: Mapped[int] = mapped_column(ForeignKey('projects.id',ondelete='CASCADE'),primary_key=True)
    owner_id: Mapped[int] = mapped_column(ForeignKey('users.id'))
    account_key: Mapped[str] = mapped_column(String(64))
    label_id: Mapped[str] = mapped_column(String(200))
    cursor: Mapped[str | None] = mapped_column(Text,nullable=True)
    automatic: Mapped[bool] = mapped_column(default=False)
    next_poll: Mapped[datetime | None] = mapped_column(DateTime(timezone=True),nullable=True)
    failures: Mapped[int] = mapped_column(default=0)
    last_result: Mapped[str] = mapped_column(String(200),default='Connected; no collection yet.')


class GmailDraft(Base):
    __tablename__ = 'gmail_drafts'
    id: Mapped[int] = mapped_column(primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey('projects.id',ondelete='CASCADE'),index=True)
    owner_id: Mapped[int] = mapped_column(ForeignKey('users.id'))
    message_key: Mapped[str] = mapped_column(String(64),unique=True)
    title: Mapped[str] = mapped_column(String(200),default='')
    description: Mapped[str] = mapped_column(Text,default='')
    state: Mapped[str] = mapped_column(String(20),default='pending')
    problem: Mapped[str] = mapped_column(String(300),default='')
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True),default=utc_now)
