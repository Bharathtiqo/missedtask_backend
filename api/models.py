from sqlalchemy import Column, String, Boolean, DateTime, Integer, Text, ForeignKey, JSON, Enum as SQLEnum
from sqlalchemy.dialects.mysql import LONGTEXT
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from datetime import datetime
import enum

Base = declarative_base()

class UserRole(str, enum.Enum):
    SUPER_ADMIN = "super_admin"
    ADMIN = "admin"
    SCRUM_MASTER = "scrum_master"
    DEVELOPER = "developer"
    TESTER = "tester"
    PROJECT_MANAGER = "project_manager"

class IssueStatus(str, enum.Enum):
    TODO = "TODO"
    IN_PROGRESS = "IN_PROGRESS"
    REVIEW = "REVIEW"
    DONE = "DONE"

class IssueType(str, enum.Enum):
    STORY = "STORY"
    TASK = "TASK"
    BUG = "BUG"
    EPIC = "EPIC"

class Priority(str, enum.Enum):
    LOWEST = "LOWEST"
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    HIGHEST = "HIGHEST"

class Organization(Base):
    __tablename__ = "organizations"

    id = Column(String(36), primary_key=True)
    name = Column(String(255), nullable=False)
    domain = Column(String(255))
    settings = Column(JSON, default={})
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    users = relationship("User", back_populates="organization", cascade="all, delete-orphan")
    issues = relationship("Issue", back_populates="organization", cascade="all, delete-orphan")
    channels = relationship("Channel", back_populates="organization", cascade="all, delete-orphan")
    conversations = relationship("Conversation", back_populates="organization", cascade="all, delete-orphan")

class User(Base):
    __tablename__ = "users"

    id = Column(String(36), primary_key=True)
    email = Column(String(255), unique=True, nullable=False, index=True)
    name = Column(String(255), nullable=False)
    role = Column(SQLEnum(UserRole), nullable=False)
    organization_id = Column(String(36), ForeignKey("organizations.id"), nullable=False)
    avatar = Column(String(10))
    is_active = Column(Boolean, default=True)
    password_hash = Column(String(255), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    profile_picture = Column(LONGTEXT)  # Base64 encoded image - LONGTEXT for MySQL, works as Text for others

    # Relationships
    organization = relationship("Organization", back_populates="users")
    assigned_issues = relationship("Issue", foreign_keys="Issue.assignee_id", back_populates="assignee")
    reported_issues = relationship("Issue", foreign_keys="Issue.reporter_id", back_populates="reporter")
    channel_memberships = relationship("ChannelMembership", back_populates="user", cascade="all, delete-orphan")
    sent_messages = relationship("ConversationMessage", back_populates="sender", cascade="all, delete-orphan")

class Issue(Base):
    __tablename__ = "issues"

    id = Column(String(36), primary_key=True)
    key = Column(String(50), unique=True, nullable=False, index=True)
    title = Column(String(500), nullable=False)
    description = Column(Text)
    issue_type = Column(SQLEnum(IssueType), nullable=False)
    status = Column(SQLEnum(IssueStatus), nullable=False, default=IssueStatus.TODO)
    priority = Column(SQLEnum(Priority), nullable=False, default=Priority.MEDIUM)
    story_points = Column(Integer)
    assignee_id = Column(String(36), ForeignKey("users.id"))
    reporter_id = Column(String(36), ForeignKey("users.id"), nullable=False)
    organization_id = Column(String(36), ForeignKey("organizations.id"), nullable=False)
    labels = Column(JSON, default=[])
    visibility = Column(String(50), default="team")
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    due_date = Column(DateTime)
    epic_id = Column(String(36))
    sprint_id = Column(String(36))

    # Relationships
    organization = relationship("Organization", back_populates="issues")
    assignee = relationship("User", foreign_keys=[assignee_id], back_populates="assigned_issues")
    reporter = relationship("User", foreign_keys=[reporter_id], back_populates="reported_issues")

class Channel(Base):
    __tablename__ = "channels"

    id = Column(String(36), primary_key=True)
    name = Column(String(255), nullable=False)
    description = Column(Text)
    organization_id = Column(String(36), ForeignKey("organizations.id"), nullable=False)
    is_private = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    created_by = Column(String(36))

    # Relationships
    organization = relationship("Organization", back_populates="channels")
    memberships = relationship("ChannelMembership", back_populates="channel", cascade="all, delete-orphan")
    conversations = relationship("Conversation", back_populates="channel", cascade="all, delete-orphan")

class ChannelMembership(Base):
    __tablename__ = "channel_memberships"

    id = Column(String(36), primary_key=True)
    channel_id = Column(String(36), ForeignKey("channels.id"), nullable=False)
    user_id = Column(String(36), ForeignKey("users.id"), nullable=False)
    joined_at = Column(DateTime, default=datetime.utcnow)
    role = Column(String(50), default="member")  # member, admin

    # Relationships
    channel = relationship("Channel", back_populates="memberships")
    user = relationship("User", back_populates="channel_memberships")

class Conversation(Base):
    __tablename__ = "conversations"

    id = Column(String(36), primary_key=True)
    channel_id = Column(String(36), ForeignKey("channels.id"), nullable=False)
    organization_id = Column(String(36), ForeignKey("organizations.id"), nullable=False)
    title = Column(String(500))
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    is_active = Column(Boolean, default=True)

    # Relationships
    channel = relationship("Channel", back_populates="conversations")
    organization = relationship("Organization", back_populates="conversations")
    messages = relationship("ConversationMessage", back_populates="conversation", cascade="all, delete-orphan", order_by="ConversationMessage.created_at")

class ConversationMessage(Base):
    __tablename__ = "conversation_messages"

    id = Column(String(36), primary_key=True)
    conversation_id = Column(String(36), ForeignKey("conversations.id"), nullable=False)
    sender_id = Column(String(36), ForeignKey("users.id"), nullable=False)
    content = Column(Text, nullable=False)
    message_type = Column(String(50), default="text")  # text, system, attachment
    created_at = Column(DateTime, default=datetime.utcnow)
    edited_at = Column(DateTime)
    is_edited = Column(Boolean, default=False)
    message_metadata = Column(JSON, default={})

    # Relationships
    conversation = relationship("Conversation", back_populates="messages")
    sender = relationship("User", back_populates="sent_messages")
