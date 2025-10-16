from fastapi import FastAPI, HTTPException, Depends, status, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel, EmailStr
from typing import List, Optional, Dict, Any, Set
from enum import Enum
import uuid
from datetime import datetime, timedelta
import hashlib
import secrets
import logging
import json
import os
import asyncio
from starlette.responses import StreamingResponse
from starlette.requests import Request
from dotenv import load_dotenv

# Load environment variables from .env file (only in local/dev, not on Render)
if not os.getenv("RENDER"):
    load_dotenv()

# Import database modules
try:
    from .database import init_db, get_db, engine, DATABASE_URL
    from .models import (
        Issue as IssueModel,
        IssueStatus as ModelIssueStatus,
        IssueType as ModelIssueType,
        Priority as ModelPriority,
    )
except ImportError:
    # Allows running `python api/main.py` without package context.
    import sys
    from pathlib import Path
    import importlib.util
    import types

    current_dir = Path(__file__).resolve().parent
    parent_dir = current_dir.parent

    for path in (current_dir, parent_dir):
        if str(path) not in sys.path:
            sys.path.insert(0, str(path))

    package_name = "api"
    if package_name not in sys.modules:
        package = types.ModuleType(package_name)
        package.__path__ = [str(current_dir)]
        sys.modules[package_name] = package

    def _load_module(name: str, path: Path):
        spec = importlib.util.spec_from_file_location(name, path)
        if spec is None or spec.loader is None:
            raise ImportError(f"Could not load module {name} from {path}")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module

    database_module = _load_module("api.database", current_dir / "database.py")
    models_module = _load_module("api.models", current_dir / "models.py")

    init_db = database_module.init_db  # type: ignore
    get_db = database_module.get_db  # type: ignore
    engine = database_module.engine  # type: ignore
    DATABASE_URL = database_module.DATABASE_URL  # type: ignore

    IssueModel = models_module.Issue  # type: ignore
    ModelIssueStatus = models_module.IssueStatus  # type: ignore
    ModelIssueType = models_module.IssueType  # type: ignore
    ModelPriority = models_module.Priority  # type: ignore
from sqlalchemy.orm import Session
from sqlalchemy import or_

try:
    import websockets  # type: ignore
    WEBSOCKET_LIB_AVAILABLE = True
except ImportError:
    WEBSOCKET_LIB_AVAILABLE = False

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

if not WEBSOCKET_LIB_AVAILABLE:
    logger.warning("WebSocket support missing. Install 'uvicorn[standard]' or add the 'websockets' package to enable real-time chat.")

app = FastAPI(title="Scope API", version="1.0.0", description="Project Management API")
security = HTTPBearer()

# Configuration
SECRET_KEY = "scope-secret-key-2024"

# Data directory handling
BASE_DIR = os.path.dirname(__file__)
DATA_DIR_PRIMARY = os.path.join(BASE_DIR, 'apps', 'api', 'data')
DATA_DIR_FALLBACK = os.path.join(BASE_DIR, 'data')

def get_data_path(name: str, ensure_dir: bool = True) -> str:
    target_dir = DATA_DIR_PRIMARY if os.path.exists(DATA_DIR_PRIMARY) or not os.path.exists(DATA_DIR_FALLBACK) else DATA_DIR_FALLBACK
    if ensure_dir:
        os.makedirs(target_dir, exist_ok=True)
    return os.path.join(target_dir, name)

def safe_load_json(path: str, root_key: str):
    try:
        with open(path, 'r') as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {root_key: []}

# CORS Configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:3001",
        "http://127.0.0.1:3001",
        "http://192.168.7.3:3000",
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://192.168.7.3:5173",
        "https://missedtask-frontend.onrender.com"
    ],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)

# Enums
class UserRole(str, Enum):
    SUPER_ADMIN = "super_admin"
    ADMIN = "admin"
    SCRUM_MASTER = "scrum_master"
    DEVELOPER = "developer"
    TESTER = "tester"
    PROJECT_MANAGER = "project_manager"

class IssueStatus(str, Enum):
    TODO = "TODO"
    IN_PROGRESS = "IN_PROGRESS"
    REVIEW = "REVIEW"
    DONE = "DONE"

class IssueType(str, Enum):
    STORY = "STORY"
    TASK = "TASK"
    BUG = "BUG"
    EPIC = "EPIC"

class Priority(str, Enum):
    LOWEST = "LOWEST"
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    HIGHEST = "HIGHEST"

class ConversationType(str, Enum):
    TEAM = "team"
    DIRECT = "direct"

# Request Models
class SignupRequest(BaseModel):
    email: EmailStr
    password: str
    name: str
    organization_name: str

class LoginRequest(BaseModel):
    email: EmailStr
    password: str

class UpdateRoleRequest(BaseModel):
    role: UserRole
    is_active: Optional[bool] = None

class UpdateAvatarRequest(BaseModel):
    avatar: Optional[str] = None

class UpdateProfileRequest(BaseModel):
    name: Optional[str] = None
    email: Optional[EmailStr] = None

class UpdateProfilePictureRequest(BaseModel):
    profile_picture: str

class MemberSignupRequest(BaseModel):
    email: EmailStr
    password: str
    name: str

class VerifyOTPRequest(BaseModel):
    email: EmailStr
    otp: str

class CreateIssueRequest(BaseModel):
    title: str
    description: Optional[str] = ""
    issue_type: IssueType
    priority: Priority = Priority.MEDIUM
    story_points: Optional[int] = 1
    assignee_id: Optional[str] = None
    labels: Optional[List[str]] = []
    visibility: Optional[str] = "public"
    deadline: Optional[datetime] = None

class UpdateIssueRequest(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    status: Optional[IssueStatus] = None
    priority: Optional[Priority] = None
    story_points: Optional[int] = None
    assignee_id: Optional[str] = None
    visibility: Optional[str] = None
    deadline: Optional[datetime] = None

class CreateCommentRequest(BaseModel):
    content: str

# Chat Message Request Models
class ChatMessageRequest(BaseModel):
    content: str
    conversation_id: Optional[str] = "team-chat"

class CreateConversationRequest(BaseModel):
    id: Optional[str] = None
    type: ConversationType = ConversationType.DIRECT
    participants: List[str] = []
    name: Optional[str] = None

# Response Models
class UserResponse(BaseModel):
    id: str
    name: str
    email: str
    avatar: str
    profile_picture: Optional[str] = None
    role: str
    organization_id: str
    is_active: bool
    is_online: Optional[bool] = False
    created_at: str

class OrganizationResponse(BaseModel):
    id: str
    name: str
    domain: str
    plan: str
    user_count: int
    max_users: int
    created_at: str

class IssueResponse(BaseModel):
    id: str
    key: str
    title: str
    description: str
    issue_type: IssueType
    priority: Priority
    status: IssueStatus
    assignee_id: Optional[str]
    reporter_id: str
    story_points: Optional[int]
    labels: List[str]
    organization_id: str
    visibility: str
    deadline: Optional[str] = None
    created_at: str
    updated_at: str

class CommentResponse(BaseModel):
    id: str
    content: str
    author_id: str
    issue_id: str
    created_at: str
    updated_at: str

class AuthResponse(BaseModel):
    access_token: str
    token_type: str
    user: UserResponse
    organization: OrganizationResponse

class HealthResponse(BaseModel):
    ok: bool
    service: str
    version: str
    timestamp: str

# Chat Response Models
class ConversationMessageResponse(BaseModel):
    id: str
    content: str
    sender_id: str
    sender_name: str
    sender_avatar: str
    sender_profile_picture: Optional[str] = None
    conversation_id: str
    created_at: str
    message_type: Optional[str] = "text"
    edited: Optional[bool] = False
    reply_to: Optional[str] = None

class ConversationResponse(BaseModel):
    id: str
    type: str
    name: str
    participants: List[str]
    last_message: Optional[ConversationMessageResponse] = None
    unread_count: int = 0
    avatar: Optional[str] = None
    created_at: str
    updated_at: str

# In-memory storage (use database in production)
users_db: Dict[str, dict] = {}
organizations_db: Dict[str, dict] = {}
issues_db: Dict[str, dict] = {}
comments_db: Dict[str, dict] = {}
otp_db: Dict[str, dict] = {}
sessions_db: Dict[str, str] = {}
issue_counter = 1

# Chat in-memory stores
conversations_db: Dict[str, dict] = {}
conversation_messages_db: Dict[str, dict] = {}
user_conversations_db: Dict[str, List[str]] = {}  # user_id -> list of conversation_ids

# WebSocket connection registries
active_chat_connections: Dict[str, List[Dict[str, Any]]] = {}
sse_connections: Dict[str, List[asyncio.Queue]] = {}
presence_counters: Dict[str, Dict[str, int]] = {}

def user_has_active_session(user_id: Optional[str]) -> bool:
    """Check whether the given user has an active access token."""
    if not user_id:
        return False
    return any(uid == user_id for uid in sessions_db.values())


def _enum_value(value: Any) -> Optional[str]:
    if value is None:
        return None
    if hasattr(value, "value"):
        return value.value
    return str(value)


def issue_model_to_dict(issue: IssueModel) -> Dict[str, Any]:
    return {
        "id": issue.id,
        "key": issue.key,
        "title": issue.title,
        "description": issue.description or "",
        "issue_type": _enum_value(issue.issue_type),
        "status": _enum_value(issue.status),
        "priority": _enum_value(issue.priority),
        "story_points": issue.story_points,
        "assignee_id": issue.assignee_id,
        "reporter_id": issue.reporter_id,
        "organization_id": issue.organization_id,
        "labels": list(issue.labels or []),
        "visibility": issue.visibility or "public",
        "created_at": issue.created_at.isoformat() if issue.created_at else datetime.utcnow().isoformat(),
        "updated_at": issue.updated_at.isoformat() if issue.updated_at else datetime.utcnow().isoformat(),
        "deadline": issue.due_date.isoformat() if issue.due_date else None,
        "epic_id": issue.epic_id,
        "sprint_id": issue.sprint_id,
    }


def issue_dict_to_response(issue_data: Dict[str, Any]) -> IssueResponse:
    payload = dict(issue_data)
    payload["issue_type"] = IssueType(_enum_value(issue_data.get("issue_type")))
    payload["status"] = IssueStatus(_enum_value(issue_data.get("status")))
    payload["priority"] = Priority(_enum_value(issue_data.get("priority")))
    payload["labels"] = issue_data.get("labels", [])
    return IssueResponse(**payload)

def get_online_user_ids_for_org(organization_id: Optional[str]) -> Set[str]:
    """Return online user IDs for a specific organization based on active tokens."""
    if not organization_id:
        return set()
    online_ids: Set[str] = set()
    for token_user_id in sessions_db.values():
        user = users_db.get(token_user_id)
        if user and user.get('organization_id') == organization_id:
            online_ids.add(token_user_id)
    return online_ids

def _increment_presence(organization_id: str, user_id: str) -> bool:
    org = presence_counters.setdefault(organization_id, {})
    previous = org.get(user_id, 0)
    org[user_id] = previous + 1
    return previous == 0

def _decrement_presence(organization_id: str, user_id: str) -> bool:
    org = presence_counters.get(organization_id)
    if not org:
        return False
    previous = org.get(user_id, 0)
    if previous <= 1:
        org.pop(user_id, None)
        if not org:
            presence_counters.pop(organization_id, None)
        return previous > 0
    org[user_id] = previous - 1
    return False

async def broadcast_to_sse(organization_id: str, message: dict):
    if organization_id not in sse_connections:
        return
    stale: List[asyncio.Queue] = []
    for queue in sse_connections[organization_id]:
        try:
            queue.put_nowait(message)
        except Exception:
            stale.append(queue)
    if stale:
        for queue in stale:
            try:
                sse_connections[organization_id].remove(queue)
            except ValueError:
                pass
        if not sse_connections.get(organization_id):
            sse_connections.pop(organization_id, None)

def add_chat_connection(organization_id: str, websocket, user_data: dict) -> bool:
    if organization_id not in active_chat_connections:
        active_chat_connections[organization_id] = []

    connection_info = {
        'websocket': websocket,
        'user_id': user_data['id'],
        'user_name': user_data['name'],
        'user_avatar': user_data['avatar']
    }
    active_chat_connections[organization_id].append(connection_info)
    logger.info(f"Added chat connection for {user_data['name']} in org {organization_id}")
    return _increment_presence(organization_id, user_data['id'])

def remove_chat_connection(organization_id: str, websocket, user_id: str) -> bool:
    if organization_id in active_chat_connections:
        remaining = []
        for conn in active_chat_connections[organization_id]:
            if conn['websocket'] != websocket:
                remaining.append(conn)
        if remaining:
            active_chat_connections[organization_id] = remaining
        else:
            active_chat_connections.pop(organization_id, None)
        logger.info(f"Removed chat connection from org {organization_id}")
    return _decrement_presence(organization_id, user_id)

async def broadcast_to_organization(organization_id: str, message: dict, exclude_websocket=None):
    if organization_id in active_chat_connections:
        message_str = json.dumps(message)
        connections_to_remove = []
        for connection in active_chat_connections[organization_id]:
            if connection['websocket'] == exclude_websocket:
                continue
            try:
                await connection['websocket'].send_text(message_str)
                logger.info(f"Sent chat message to {connection['user_name']}")
            except Exception as e:
                logger.info(f"Failed to send to {connection['user_name']}: {e}")
                connections_to_remove.append(connection)
        for conn in connections_to_remove:
            try:
                active_chat_connections[organization_id].remove(conn)
            except ValueError:
                pass
        if not active_chat_connections.get(organization_id):
            active_chat_connections.pop(organization_id, None)
    else:
        logger.info(f"No active chat connections for org {organization_id}")

    await broadcast_to_sse(organization_id, message)

async def broadcast_to_conversation(conversation_id: str, message: dict, exclude_websocket=None):
    """Broadcast message to all participants in a specific conversation"""
    conversation = conversations_db.get(conversation_id)
    if not conversation:
        return
    
    # Get organization from conversation participants
    participants = conversation.get('participants', [])
    if not participants:
        return
    
    # Get first participant's organization (assuming all in same org)
    first_user = users_db.get(participants[0])
    if not first_user:
        return
    
    org_id = first_user['organization_id']
    
    # Broadcast to organization but add conversation context
    message['conversation_id'] = conversation_id
    await broadcast_to_organization(org_id, message, exclude_websocket)

# FILE PERSISTENCE FUNCTIONS
def save_user_data(user_data):
    file_path = get_data_path("users.json")
    os.makedirs(os.path.dirname(file_path), exist_ok=True)
    
    try:
        with open(file_path, 'r') as f:
            data = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        data = {"users": []}
    
    existing_emails = [u.get('email') for u in data["users"]]
    if user_data.get('email') not in existing_emails:
        data["users"].append(user_data)
        with open(file_path, 'w') as f:
            json.dump(data, f, indent=2)
        logger.info(f"User saved to file: {user_data['email']}")
    else:
        logger.info(f"User already exists in file: {user_data['email']}")

def update_user_data(user_data):
    file_path = get_data_path("users.json")
    os.makedirs(os.path.dirname(file_path), exist_ok=True)
    try:
        with open(file_path, 'r') as f:
            data = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        data = {"users": []}
    found = False
    for i, u in enumerate(data.get("users", [])):
        if u.get('id') == user_data.get('id'):
            data["users"][i] = user_data
            found = True
            break
    if not found:
        data.setdefault("users", []).append(user_data)
    with open(file_path, 'w') as f:
        json.dump(data, f, indent=2)

def save_organization_data(org_data):
    file_path = get_data_path("organizations.json")
    os.makedirs(os.path.dirname(file_path), exist_ok=True)
    
    try:
        with open(file_path, 'r') as f:
            data = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        data = {"organizations": []}
    
    existing_ids = [o.get('id') for o in data["organizations"]]
    if org_data.get('id') not in existing_ids:
        data["organizations"].append(org_data)
        with open(file_path, 'w') as f:
            json.dump(data, f, indent=2)
        logger.info(f"Organization saved to file: {org_data['name']}")
    else:
        logger.info(f"Organization already exists in file: {org_data['name']}")

def update_organization_data(org_data):
    file_path = get_data_path("organizations.json")
    os.makedirs(os.path.dirname(file_path), exist_ok=True)
    data = {"organizations": []}
    try:
        with open(file_path, 'r') as f:
            data = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        pass

    updated = False
    for i, org in enumerate(data.get("organizations", [])):
        if org.get('id') == org_data.get('id'):
            data["organizations"][i] = org_data
            updated = True
            break

    if not updated:
        data.setdefault("organizations", []).append(org_data)

    with open(file_path, 'w') as f:
        json.dump(data, f, indent=2)
    logger.info(f"Organization updated in file: {org_data['name']}")

def save_issue_data(issue_data):
    file_path = get_data_path("issues.json")
    os.makedirs(os.path.dirname(file_path), exist_ok=True)
    
    try:
        with open(file_path, 'r') as f:
            data = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        data = {"issues": []}
    
    existing_ids = [i.get('id') for i in data["issues"]]
    if issue_data.get('id') not in existing_ids:
        data["issues"].append(issue_data)
    else:
        for i, issue in enumerate(data["issues"]):
            if issue.get('id') == issue_data.get('id'):
                data["issues"][i] = issue_data
                break
    
    with open(file_path, 'w') as f:
        json.dump(data, f, indent=2)
    logger.info(f"Issue saved to file: {issue_data.get('key', issue_data.get('id'))}")

def remove_issue_from_file(issue_id: str):
    file_path = get_data_path("issues.json")
    try:
        with open(file_path, 'r') as f:
            data = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return

    original_count = len(data.get("issues", []))
    data["issues"] = [issue for issue in data.get("issues", []) if issue.get("id") != issue_id]

    if len(data["issues"]) != original_count:
        with open(file_path, 'w') as f:
            json.dump(data, f, indent=2)
        logger.info(f"Issue removed from file: {issue_id}")

def save_comment_data(comment_data):
    file_path = get_data_path("comments.json")
    os.makedirs(os.path.dirname(file_path), exist_ok=True)
    
    try:
        with open(file_path, 'r') as f:
            data = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        data = {"comments": []}
    
    existing_ids = [c.get('id') for c in data["comments"]]
    if comment_data.get('id') not in existing_ids:
        data["comments"].append(comment_data)
        with open(file_path, 'w') as f:
            json.dump(data, f, indent=2)
        logger.info(f"Comment saved to file: {comment_data['id']}")

def save_conversation_data(conversation_data):
    file_path = get_data_path("conversations.json")
    os.makedirs(os.path.dirname(file_path), exist_ok=True)
    try:
        with open(file_path, 'r') as f:
            data = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        data = {"conversations": []}
    
    # Upsert by id
    replaced = False
    for i, conv in enumerate(data.get("conversations", [])):
        if conv.get('id') == conversation_data.get('id'):
            data["conversations"][i] = conversation_data
            replaced = True
            break
    if not replaced:
        data.setdefault("conversations", []).append(conversation_data)
    
    with open(file_path, 'w') as f:
        json.dump(data, f, indent=2)
    logger.info(f"Conversation saved: {conversation_data['id']}")

def save_conversation_message(msg_data):
    file_path = get_data_path("conversation_messages.json")
    os.makedirs(os.path.dirname(file_path), exist_ok=True)
    # Work on a copy so that normalization updates are persisted consistently
    message_record = dict(msg_data) if isinstance(msg_data, dict) else {}
    normalize_message_record(message_record)
    try:
        with open(file_path, 'r') as f:
            data = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        data = {"messages": []}

    replaced = False
    for idx, existing in enumerate(data.get("messages", [])):
        if existing.get('id') == message_record.get('id'):
            data["messages"][idx] = message_record
            replaced = True
            break

    if not replaced:
        data.setdefault("messages", []).append(message_record)

    with open(file_path, 'w') as f:
        json.dump(data, f, indent=2)
    logger.info(f"Conversation message saved: {message_record.get('id')}")

def normalize_message_record(message: dict) -> bool:
    """
    Normalize chat message dicts so API responses are consistent.

    Returns True when the message was modified.
    """
    if not isinstance(message, dict):
        return False

    updated = False

    # Ensure sender* aliases exist for legacy author* fields and vice versa
    for new_key, legacy_key in (
        ("sender_id", "author_id"),
        ("sender_name", "author_name"),
        ("sender_avatar", "author_avatar"),
    ):
        new_value = message.get(new_key)
        legacy_value = message.get(legacy_key)
        if new_value is None and legacy_value is not None:
            message[new_key] = legacy_value
            updated = True
        elif legacy_value is None and new_value is not None:
            message[legacy_key] = new_value
            updated = True

    # Standardize message type
    message_type = message.get("message_type")
    if not message_type:
        legacy_type = message.get("type")
        if legacy_type and legacy_type not in ("message", "text"):
            message_type = str(legacy_type)
        else:
            message_type = "text"
        message["message_type"] = message_type
        updated = True
    else:
        message_type = str(message_type)
    if not message.get("type"):
        message["type"] = message_type
        updated = True

    # Edited flag normalisation
    if "edited" not in message and "is_edited" in message:
        message["edited"] = bool(message.get("is_edited"))
        updated = True
    elif "edited" not in message:
        message["edited"] = False
        updated = True

    # Reply-to alias
    if "reply_to" not in message and message.get("parent_message_id"):
        message["reply_to"] = message.get("parent_message_id")
        updated = True

    # Ensure timestamps are serializable strings
    created_at = message.get("created_at")
    if isinstance(created_at, datetime):
        message["created_at"] = created_at.isoformat()
        updated = True
    elif not created_at:
        message["created_at"] = datetime.utcnow().isoformat()
        updated = True

    updated_at = message.get("updated_at")
    if isinstance(updated_at, datetime):
        message["updated_at"] = updated_at.isoformat()
        updated = True

    return updated

def build_message_response(message: dict) -> ConversationMessageResponse:
    """Convert stored message dicts into ConversationMessageResponse objects."""
    normalize_message_record(message)

    sender_id = message.get("sender_id") or message.get("author_id") or ""
    sender_name = message.get("sender_name") or message.get("author_name") or ""
    sender_avatar = message.get("sender_avatar") or message.get("author_avatar") or ""

    sender_profile_picture = message.get("sender_profile_picture")
    if not sender_profile_picture and sender_id:
        sender = users_db.get(sender_id)
        if sender:
            sender_profile_picture = sender.get("profile_picture")

    created_at = message.get("created_at")
    if isinstance(created_at, datetime):
        created_at = created_at.isoformat()
    elif not created_at:
        created_at = datetime.utcnow().isoformat()

    message_type = message.get("message_type") or "text"
    edited_value = message.get("edited")
    if edited_value is None:
        edited_value = bool(message.get("is_edited", False))

    if not sender_id:
        logger.warning(f"Message {message.get('id')} is missing sender information after normalization")

    return ConversationMessageResponse(
        id=str(message.get("id", "")),
        content=message.get("content", ""),
        sender_id=str(sender_id),
        sender_name=sender_name,
        sender_avatar=sender_avatar,
        sender_profile_picture=sender_profile_picture,
        conversation_id=str(message.get("conversation_id", "")),
        created_at=str(created_at),
        message_type=str(message_type),
        edited=bool(edited_value),
        reply_to=message.get("reply_to")
    )

def delete_conversation_message(message_id):
    """Delete a message from persistent storage"""
    file_path = get_data_path("conversation_messages.json")
    try:
        with open(file_path, 'r') as f:
            data = json.load(f)

        # Filter out the message to delete
        original_count = len(data.get("messages", []))
        data["messages"] = [m for m in data.get("messages", []) if m.get('id') != message_id]

        if len(data["messages"]) < original_count:
            with open(file_path, 'w') as f:
                json.dump(data, f, indent=2)
            logger.info(f"Conversation message deleted: {message_id}")
            return True
        return False
    except (FileNotFoundError, json.JSONDecodeError) as e:
        logger.error(f"Error deleting message: {e}")
        return False

def load_data_from_files():
    global users_db, organizations_db, issues_db, comments_db

    # Load users
    try:
        user_data = safe_load_json(get_data_path("users.json"), "users")
        for user in user_data.get("users", []):
            users_db[user['id']] = user
        logger.info(f"Loaded {len(users_db)} users from file")
    except Exception as e:
        logger.warning(f"Could not load users.json: {e}")

    # Load organizations
    try:
        org_data = safe_load_json(get_data_path("organizations.json"), "organizations")
        for org in org_data.get("organizations", []):
            organizations_db[org['id']] = org
        logger.info(f"Loaded {len(organizations_db)} organizations from file")
    except Exception as e:
        logger.warning(f"Could not load organizations.json: {e}")

    # Load issues
    try:
        issue_data = safe_load_json(get_data_path("issues.json"), "issues")
        for issue in issue_data.get("issues", []):
            issues_db[issue['id']] = issue
        logger.info(f"Loaded {len(issues_db)} issues from file")
    except Exception as e:
        logger.warning(f"Could not load issues.json: {e}")

    # Load comments
    try:
        comment_data = safe_load_json(get_data_path("comments.json"), "comments")
        for comment in comment_data.get("comments", []):
            comments_db[comment['id']] = comment
        logger.info(f"Loaded {len(comments_db)} comments from file")
    except Exception as e:
        logger.warning(f"Could not load comments.json: {e}")
    
    migrate_existing_data()

def load_chat_data_from_files():
    global conversations_db, conversation_messages_db, user_conversations_db
    
    # Load conversations
    try:
        conv_data = safe_load_json(get_data_path("conversations.json"), "conversations")
        for conv in conv_data.get("conversations", []):
            conversations_db[conv['id']] = conv
            # Build user conversation mapping
            for participant_id in conv.get('participants', []):
                if participant_id not in user_conversations_db:
                    user_conversations_db[participant_id] = []
                if conv['id'] not in user_conversations_db[participant_id]:
                    user_conversations_db[participant_id].append(conv['id'])
        logger.info(f"Loaded {len(conversations_db)} conversations from file")
    except Exception:
        pass
    
    # Load conversation messages
    try:
        conv_data = safe_load_json(get_data_path("conversation_messages.json"), "messages")
        messages_updated = False
        for m in conv_data.get("messages", []):
            if normalize_message_record(m):
                messages_updated = True
            conversation_messages_db[m['id']] = m
        logger.info(f"Loaded {len(conversation_messages_db)} conversation messages from file")

        if messages_updated:
            try:
                file_path = get_data_path("conversation_messages.json")
                with open(file_path, 'w') as f:
                    json.dump({"messages": list(conversation_messages_db.values())}, f, indent=2)
                logger.info("Normalized legacy conversation messages and persisted updates")
            except Exception as e:
                logger.error(f"Failed to persist normalized chat messages: {e}")
    except Exception:
        pass
    
    # Ensure team chat conversation exists for all organizations
    for org_id in organizations_db.keys():
        team_conv_id = f"team-chat-{org_id}"
        if team_conv_id not in conversations_db:
            create_team_conversation(org_id)

def create_team_conversation(organization_id: str):
    """Create default team chat conversation for organization"""
    team_conv_id = f"team-chat-{organization_id}"
    if team_conv_id in conversations_db:
        return conversations_db[team_conv_id]
    
    # Get all users in organization
    org_users = [u['id'] for u in users_db.values() if u.get('organization_id') == organization_id]
    
    conversation = {
        'id': team_conv_id,
        'type': 'team',
        'name': 'Team Chat',
        'participants': org_users,
        'organization_id': organization_id,
        'created_at': datetime.utcnow().isoformat(),
        'updated_at': datetime.utcnow().isoformat()
    }
    
    conversations_db[team_conv_id] = conversation
    save_conversation_data(conversation)
    
    # Add to user conversations mapping
    for user_id in org_users:
        if user_id not in user_conversations_db:
            user_conversations_db[user_id] = []
        if team_conv_id not in user_conversations_db[user_id]:
            user_conversations_db[user_id].append(team_conv_id)
    
    logger.info(f"Created team conversation for org {organization_id}")
    return conversation

def log_data_state():
    logger.info(f"Data state: {len(users_db)} users, {len(organizations_db)} orgs, {len(issues_db)} issues, {len(comments_db)} comments, {len(conversations_db)} conversations")

# Utility functions
def hash_password(password: str) -> str:
    return hashlib.sha256((password + SECRET_KEY).encode()).hexdigest()

def verify_password(password: str, hashed: str) -> bool:
    return hash_password(password) == hashed

def create_access_token(user_id: str) -> str:
    token = secrets.token_urlsafe(32)
    sessions_db[token] = user_id
    logger.info(f"Created access token for user: {user_id}")
    return token

def generate_otp() -> str:
    return ''.join([str(secrets.randbelow(10)) for _ in range(6)])

def generate_issue_key(org_id: str) -> str:
    global issue_counter
    org = organizations_db.get(org_id, {})
    prefix = org.get('name', 'SCOPE')[:4].upper()
    key = f"{prefix}-{issue_counter}"
    issue_counter += 1
    return key

def create_user_avatar(name: str) -> str:
    words = name.strip().split()
    if len(words) >= 2:
        return f"{words[0][0]}{words[1][0]}".upper()
    elif len(words) == 1:
        return words[0][:2].upper()
    else:
        return "UN"

def verify_access_token(token: str) -> Optional[dict]:
    try:
        user_id = sessions_db.get(token)
        if not user_id:
            return None
        
        user = users_db.get(user_id)
        if not user:
            return None
            
        return user
    except Exception as e:
        logger.error(f"Token verification error: {e}")
        return None

def migrate_existing_data():
    logger.info("Starting data migration...")
    
    # Migrate issues to add visibility field
    issues_updated = 0
    deadline_updates = 0
    for issue_id, issue in issues_db.items():
        if 'visibility' not in issue:
            issue['visibility'] = 'public'
            issues_updated += 1
        if 'deadline' not in issue:
            issue['deadline'] = None
            deadline_updates += 1
    
    if issues_updated > 0 or deadline_updates > 0:
        if issues_updated > 0:
            logger.info(f"Migrated {issues_updated} issues to add visibility field")
        if deadline_updates > 0:
            logger.info(f"Migrated {deadline_updates} issues to add deadline field")
        try:
            file_path = get_data_path("issues.json")
            data = {"issues": list(issues_db.values())}
            with open(file_path, 'w') as f:
                json.dump(data, f, indent=2)
            logger.info("Updated issues saved to file")
        except Exception as e:
            logger.error(f"Failed to save migrated issues: {e}")
    
    logger.info("Data migration completed")

# Authentication dependency
async def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)) -> dict:
    try:
        token = credentials.credentials
        user_id = sessions_db.get(token)
        
        if not user_id:
            logger.warning(f"Invalid token used: {token[:10]}...")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid authentication token"
            )
        
        user = users_db.get(user_id)
        if not user:
            logger.warning(f"User not found for token: {user_id}")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User not found"
            )
        
        return user
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Authentication error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication failed"
        )

# Health check endpoint
@app.get("/healthz", response_model=HealthResponse)
def health_check():
    logger.info("Health check requested")
    log_data_state()
    return HealthResponse(
        ok=True,
        service="Scope API",
        version="1.0.0",
        timestamp=datetime.utcnow().isoformat()
    )

@app.get("/health", response_model=HealthResponse)
@app.get("/test")
def test_endpoint():
    """Health check alias endpoint"""
    return HealthResponse(
        ok=True,
        service="Scope API",
        version="1.0.0",
        timestamp=datetime.utcnow().isoformat()
    )

# Authentication endpoints
@app.post("/api/auth/signup")
async def signup(request: SignupRequest):
    logger.info(f"Signup request for: {request.email}")
    
    if any(u.get('email') == request.email for u in users_db.values()):
        logger.warning(f"User already exists: {request.email}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User with this email already exists"
        )
    
    if len(request.password) < 6:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Password must be at least 6 characters long"
        )
    
    if len(request.organization_name.strip()) < 2:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Organization name must be at least 2 characters long"
        )
    
    otp = generate_otp()
    otp_data = {
        "otp": otp,
        "expires_at": (datetime.utcnow() + timedelta(minutes=10)).isoformat(),
        "signup_data": {
            "email": request.email,
            "password": request.password,
            "name": request.name.strip(),
            "organization_name": request.organization_name.strip()
        }
    }
    otp_db[request.email] = otp_data
    
    print(f"\n{'='*60}")
    print(f"OTP VERIFICATION CODE")
    print(f"Email: {request.email}")
    print(f"OTP: {otp}")
    print(f"Expires: {(datetime.utcnow() + timedelta(minutes=10)).strftime('%H:%M:%S')} UTC")
    print(f"{'='*60}\n")
    
    logger.info(f"OTP generated for {request.email}: {otp}")
    
    return {
        "message": "OTP sent successfully! Check your backend console for the verification code.",
        "email": request.email
    }

@app.post("/api/auth/signup-member")
async def signup_member(request: MemberSignupRequest):
    logger.info(f"Member signup request for: {request.email}")

    if any(u.get('email') == request.email for u in users_db.values()):
        logger.warning(f"User already exists: {request.email}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User with this email already exists"
        )

    if len(request.password) < 6:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Password must be at least 6 characters long"
        )

    domain = request.email.split("@")[-1].lower()
    org = next((o for o in organizations_db.values() if o.get('domain', '').lower() == domain), None)
    if not org:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No organization found for this email domain. Ask your admin to create one first."
        )

    if org.get('user_count', 0) >= org.get('max_users', 0):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Organization has reached maximum users"
        )

    otp = generate_otp()
    otp_data = {
        "otp": otp,
        "expires_at": (datetime.utcnow() + timedelta(minutes=10)).isoformat(),
        "signup_data": {
            "email": request.email,
            "password": request.password,
            "name": request.name.strip(),
            "organization_id": org['id']
        },
        "mode": "member"
    }
    otp_db[request.email] = otp_data

    print(f"\n{'='*60}")
    print(f"OTP VERIFICATION CODE (Member Signup)")
    print(f"Email: {request.email}")
    print(f"OTP: {otp}")
    print(f"Expires: {(datetime.utcnow() + timedelta(minutes=10)).strftime('%H:%M:%S')} UTC")
    print(f"{'='*60}\n")

    logger.info(f"OTP generated for member {request.email}: {otp}")

    return {
        "message": "OTP sent successfully! Check your backend console for the verification code.",
        "email": request.email
    }

@app.post("/api/auth/verify-otp", response_model=AuthResponse)
async def verify_otp(request: VerifyOTPRequest):
    logger.info(f"OTP verification for: {request.email}")
    
    otp_data = otp_db.get(request.email)
    if not otp_data:
        logger.warning(f"No OTP found for: {request.email}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No OTP found for this email. Please request a new signup."
        )
    
    expires_at = datetime.fromisoformat(otp_data["expires_at"])
    if expires_at < datetime.utcnow():
        del otp_db[request.email]
        logger.warning(f"Expired OTP for: {request.email}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="OTP has expired. Please signup again."
        )
    
    if otp_data["otp"] != request.otp:
        logger.warning(f"Invalid OTP for {request.email}: {request.otp}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid OTP. Please check the code and try again."
        )
    
    org_id = str(uuid.uuid4())
    signup_data = otp_data["signup_data"]
    org_domain = signup_data["email"].split("@")[1].lower()
    org_name_lower = signup_data["organization_name"].strip().lower()
    for o in organizations_db.values():
        if o.get("domain", "").lower() == org_domain or o.get("name", "").strip().lower() == org_name_lower:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Organization already exists. Use join flow.")

    organization = {
        "id": org_id,
        "name": signup_data["organization_name"],
        "domain": signup_data["email"].split("@")[1],
        "plan": "free",
        "user_count": 1,
        "max_users": 10,
        "created_at": datetime.utcnow().isoformat()
    }
    organizations_db[org_id] = organization
    
    user_id = str(uuid.uuid4())
    user = {
        "id": user_id,
        "email": signup_data["email"],
        "name": signup_data["name"],
        "role": UserRole.SUPER_ADMIN,
        "organization_id": org_id,
        "avatar": create_user_avatar(signup_data["name"]),
        "is_active": True,
        "password_hash": hash_password(signup_data["password"]),
        "created_at": datetime.utcnow().isoformat()
    }
    users_db[user_id] = user
    
    save_user_data(user)
    save_organization_data(organization)
    
    # Create team conversation for the new organization
    create_team_conversation(org_id)
    
    del otp_db[request.email]
    
    was_online = user_has_active_session(user_id)
    access_token = create_access_token(user_id)
    
    if not was_online:
        await broadcast_to_organization(
            org_id,
            {
                'type': 'user_status_change',
                'user_id': user_id,
                'user_name': user['name'],
                'user_avatar': user.get('avatar'),
                'is_online': True
            }
        )
    
    logger.info(f"User created successfully: {user['name']} ({user['email']})")
    log_data_state()
    
    user_payload = {k: v for k, v in user.items() if k != 'password_hash'}
    user_payload['is_online'] = True
    user_response = UserResponse(**user_payload)
    org_response = OrganizationResponse(**organization)
    
    return AuthResponse(
        access_token=access_token,
        token_type="bearer",
        user=user_response,
        organization=org_response
    )

@app.post("/api/auth/verify-otp-member", response_model=AuthResponse)
async def verify_otp_member(request: VerifyOTPRequest):
    logger.info(f"Member OTP verification for: {request.email}")

    otp_data = otp_db.get(request.email)
    if not otp_data or otp_data.get("mode") != "member":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No pending member signup for this email"
        )

    expires_at = datetime.fromisoformat(otp_data["expires_at"])
    if expires_at < datetime.utcnow():
        del otp_db[request.email]
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="OTP has expired. Please signup again."
        )

    if otp_data["otp"] != request.otp:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid OTP. Please check the code and try again."
        )

    signup_data = otp_data["signup_data"]
    org_id = signup_data["organization_id"]
    organization = organizations_db.get(org_id)
    if not organization:
        del otp_db[request.email]
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Organization not found"
        )

    if organization.get('user_count', 0) >= organization.get('max_users', 0):
        del otp_db[request.email]
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Organization has reached maximum users"
        )

    user_id = str(uuid.uuid4())
    user = {
        "id": user_id,
        "email": signup_data["email"],
        "name": signup_data["name"],
        "role": UserRole.DEVELOPER,
        "organization_id": org_id,
        "avatar": create_user_avatar(signup_data["name"]),
        "is_active": True,
        "password_hash": hash_password(signup_data["password"]),
        "created_at": datetime.utcnow().isoformat()
    }
    users_db[user_id] = user
    save_user_data(user)

    organization['user_count'] = organization.get('user_count', 0) + 1
    organizations_db[org_id] = organization
    update_organization_data(organization)

    # Add user to team conversation
    team_conv_id = f"team-chat-{org_id}"
    if team_conv_id in conversations_db:
        team_conv = conversations_db[team_conv_id]
        if user_id not in team_conv['participants']:
            team_conv['participants'].append(user_id)
            team_conv['updated_at'] = datetime.utcnow().isoformat()
            save_conversation_data(team_conv)
        
        # Add to user conversations mapping
        if user_id not in user_conversations_db:
            user_conversations_db[user_id] = []
        if team_conv_id not in user_conversations_db[user_id]:
            user_conversations_db[user_id].append(team_conv_id)

    del otp_db[request.email]

    was_online = user_has_active_session(user_id)
    access_token = create_access_token(user_id)

    if not was_online:
        await broadcast_to_organization(
            org_id,
            {
                'type': 'user_status_change',
                'user_id': user_id,
                'user_name': user['name'],
                'user_avatar': user.get('avatar'),
                'is_online': True
            }
        )

    user_payload = {k: v for k, v in user.items() if k != 'password_hash'}
    user_payload['is_online'] = True
    user_response = UserResponse(**user_payload)
    org_response = OrganizationResponse(**organization)

    return AuthResponse(
        access_token=access_token,
        token_type="bearer",
        user=user_response,
        organization=org_response
    )

# DUPLICATE LOGIN ENDPOINT REMOVED - See line 2441 for active endpoint

@app.post("/api/auth/logout")
async def logout(current_user: dict = Depends(get_current_user)):
    user_id = current_user.get('id')
    tokens_to_remove = [token for token, uid in sessions_db.items() if uid == user_id]
    for token in tokens_to_remove:
        del sessions_db[token]
    
    logger.info(f"User logged out: {current_user['email']} (removed {len(tokens_to_remove)} token(s))")

    if not user_has_active_session(user_id):
        payload = {
            'type': 'user_status_change',
            'user_id': user_id,
            'user_name': current_user.get('name'),
            'user_avatar': current_user.get('avatar'),
            'is_online': False
        }
        org_id = current_user.get('organization_id')
        if org_id:
            await broadcast_to_organization(org_id, payload)
    
    return {"message": "Successfully logged out"}

# Issue endpoints
@app.get("/api/issues", response_model=List[IssueResponse])
async def get_issues(
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    logger.info(f"Getting issues for user: {current_user['email']} (role: {current_user['role']})")

    org_id = current_user['organization_id']
    user_id = current_user['id']
    user_role = current_user.get('role')
    if hasattr(user_role, "value"):
        user_role = user_role.value

    query = db.query(IssueModel).filter(IssueModel.organization_id == org_id)

    if user_role not in ['super_admin', 'admin', 'project_manager']:
        query = query.filter(
            or_(
                IssueModel.reporter_id == user_id,
                IssueModel.assignee_id == user_id,
                IssueModel.visibility == 'public'
            )
        )

    issues = query.order_by(IssueModel.created_at.desc()).all()
    logger.info(f"Found {len(issues)} issues for organization {org_id}")

    processed_issues: List[IssueResponse] = []
    for issue_model in issues:
        serialized = issue_model_to_dict(issue_model)
        issues_db[issue_model.id] = {
            **serialized,
            "comments": [c for c in comments_db.values() if c.get('issue_id') == issue_model.id]
        }
        processed_issues.append(issue_dict_to_response(serialized))

    return processed_issues

@app.post("/api/issues", response_model=IssueResponse)
async def create_issue(
    request: CreateIssueRequest,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    logger.info(f"Creating issue: {request.title}")
    
    user_role = current_user.get("role")
    if hasattr(user_role, "value"):
        user_role = user_role.value
    
    allowed_roles = [
        UserRole.SUPER_ADMIN.value, 
        UserRole.ADMIN.value,
        UserRole.PROJECT_MANAGER.value, 
        UserRole.SCRUM_MASTER.value
    ]
    
    if user_role not in allowed_roles:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, 
            detail=f"Only {', '.join(allowed_roles)} can create issues. Your role: {user_role}"
        )
    
    if not request.title.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Issue title cannot be empty"
        )
    
    if request.assignee_id:
        assignee = users_db.get(request.assignee_id)
        if not assignee or assignee.get('organization_id') != current_user['organization_id']:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid assignee - must be from the same organization"
            )
        
        if not assignee.get('is_active', False):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot assign to inactive user"
            )
    
    if request.story_points and (request.story_points < 1 or request.story_points > 21):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Story points must be between 1 and 21"
        )
    
    visibility = getattr(request, 'visibility', 'public')
    if visibility not in ['public', 'assignee_only']:
        visibility = 'public'
    
    issue_id = str(uuid.uuid4())
    now = datetime.utcnow()
    issue_model = IssueModel(
        id=issue_id,
        key=generate_issue_key(current_user['organization_id']),
        title=request.title.strip(),
        description=request.description.strip() if request.description else "",
        issue_type=ModelIssueType(request.issue_type.value if hasattr(request.issue_type, "value") else request.issue_type),
        status=ModelIssueStatus.TODO,
        priority=ModelPriority(request.priority.value if hasattr(request.priority, "value") else request.priority),
        story_points=request.story_points,
        assignee_id=request.assignee_id,
        reporter_id=current_user['id'],
        organization_id=current_user['organization_id'],
        labels=request.labels or [],
        visibility=visibility,
        due_date=request.deadline,
        created_at=now,
        updated_at=now,
    )

    db.add(issue_model)
    db.commit()
    db.refresh(issue_model)

    serialized_issue = issue_model_to_dict(issue_model)
    issues_db[issue_id] = {**serialized_issue, "comments": []}
    save_issue_data(serialized_issue)

    logger.info(f"Issue created: {serialized_issue['key']} by {current_user['name']} (role: {user_role})")
    log_data_state()

    return issue_dict_to_response(serialized_issue)

@app.put("/api/issues/{issue_id}", response_model=IssueResponse)
async def update_issue(
    issue_id: str,
    request: UpdateIssueRequest,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    logger.info(f"Updating issue: {issue_id}")

    issue_model = (
        db.query(IssueModel)
        .filter(IssueModel.id == issue_id)
        .first()
    )
    if not issue_model:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Issue not found"
        )

    if issue_model.organization_id != current_user['organization_id']:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied"
        )

    if request.assignee_id:
        assignee = users_db.get(request.assignee_id)
        if not assignee or assignee.get('organization_id') != current_user['organization_id']:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid assignee"
            )

    update_data = request.dict(exclude_unset=True)

    if "title" in update_data:
        new_title = update_data["title"]
        if new_title is not None and not new_title.strip():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Issue title cannot be empty"
            )
        issue_model.title = new_title.strip() if new_title else issue_model.title

    if "description" in update_data:
        desc = update_data["description"]
        issue_model.description = desc.strip() if desc else ""

    if "issue_type" in update_data and update_data["issue_type"]:
        issue_model.issue_type = ModelIssueType(
            update_data["issue_type"].value if hasattr(update_data["issue_type"], "value") else update_data["issue_type"]
        )

    if "status" in update_data and update_data["status"]:
        issue_model.status = ModelIssueStatus(
            update_data["status"].value if hasattr(update_data["status"], "value") else update_data["status"]
        )

    if "priority" in update_data and update_data["priority"]:
        issue_model.priority = ModelPriority(
            update_data["priority"].value if hasattr(update_data["priority"], "value") else update_data["priority"]
        )

    if "story_points" in update_data:
        sp = update_data["story_points"]
        if sp is not None and (sp < 1 or sp > 21):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Story points must be between 1 and 21"
            )
        issue_model.story_points = sp

    if "assignee_id" in update_data:
        issue_model.assignee_id = update_data["assignee_id"]

    if "labels" in update_data:
        issue_model.labels = update_data["labels"] or []

    if "visibility" in update_data and update_data["visibility"]:
        issue_model.visibility = update_data["visibility"]

    if "deadline" in update_data:
        deadline = update_data["deadline"]
        if isinstance(deadline, datetime):
            issue_model.due_date = deadline
        elif deadline is None:
            issue_model.due_date = None

    if "epic_id" in update_data:
        issue_model.epic_id = update_data["epic_id"]

    if "sprint_id" in update_data:
        issue_model.sprint_id = update_data["sprint_id"]

    issue_model.updated_at = datetime.utcnow()

    db.commit()
    db.refresh(issue_model)

    serialized_issue = issue_model_to_dict(issue_model)
    issues_db[issue_id] = {
        **serialized_issue,
        "comments": [c for c in comments_db.values() if c.get('issue_id') == issue_id]
    }
    save_issue_data(serialized_issue)

    logger.info(f"Issue updated: {serialized_issue['key']} by {current_user['name']}")

    return issue_dict_to_response(serialized_issue)

@app.delete("/api/issues/{issue_id}")
async def delete_issue(
    issue_id: str,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    logger.info(f"Deleting issue: {issue_id}")

    issue_model = (
        db.query(IssueModel)
        .filter(IssueModel.id == issue_id)
        .first()
    )
    if not issue_model:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Issue not found"
        )

    if issue_model.organization_id != current_user['organization_id']:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied"
        )

    db.delete(issue_model)
    db.commit()

    issues_db.pop(issue_id, None)
    remove_issue_from_file(issue_id)

    logger.info(f"Issue deleted: {issue_model.key} by {current_user['name']}")
    log_data_state()

    return {"message": "Issue deleted successfully"}

# Comment endpoints
@app.post("/api/issues/{issue_id}/comments", response_model=CommentResponse)
async def add_comment(
    issue_id: str, 
    request: CreateCommentRequest, 
    current_user: dict = Depends(get_current_user)
):
    logger.info(f"Adding comment to issue: {issue_id}")
    
    issue = issues_db.get(issue_id)
    if not issue:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Issue not found"
        )
    
    if issue.get('organization_id') != current_user['organization_id']:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied"
        )
    
    if not request.content.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Comment content cannot be empty"
        )
    
    comment_id = str(uuid.uuid4())
    comment = {
        "id": comment_id,
        "content": request.content.strip(),
        "author_id": current_user['id'],
        "issue_id": issue_id,
        "created_at": datetime.utcnow().isoformat(),
        "updated_at": datetime.utcnow().isoformat()
    }
    
    comments_db[comment_id] = comment
    save_comment_data(comment)
    
    logger.info(f"Comment added to issue {issue['key']} by {current_user['name']}")
    
    return CommentResponse(**comment)

# User endpoints
@app.get("/api/users", response_model=List[UserResponse])
async def get_users(current_user: dict = Depends(get_current_user)):
    def normalize_role(r):
        try:
            return r.value if hasattr(r, "value") else str(r)
        except Exception:
            return str(r)
    
    def to_user_response(u: dict) -> UserResponse:
        data = {
            "id": str(u.get("id", "")),
            "name": u.get("name", ""),
            "email": u.get("email", ""),
            "avatar": str(u.get("avatar", "")),
            "role": normalize_role(u.get("role", "")),
            "organization_id": str(u.get("organization_id", "")),
            "is_active": bool(u.get("is_active", False)),
            "is_online": bool(u.get("is_online", False)),
            "created_at": u.get("created_at", "")
        }
        return UserResponse(**data)
    
    org_id = current_user.get("organization_id")
    users = [u for u in users_db.values() if u.get("organization_id") == org_id]
    
    # Online users determined by active access tokens (with presence as a secondary signal)
    online_user_ids = get_online_user_ids_for_org(org_id)
    online_user_ids.update({
        user_id for user_id, count in presence_counters.get(org_id, {}).items() if count > 0
    })
    
    user_responses = []
    for u in users:
        user_data = dict(u)
        user_data['is_online'] = u['id'] in online_user_ids
        user_responses.append(to_user_response(user_data))
    
    return user_responses

@app.put("/api/users/me/avatar", response_model=UserResponse)
async def update_my_avatar(request: UpdateAvatarRequest, current_user: dict = Depends(get_current_user)):
    user_id = current_user.get('id')
    if not user_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail='User not authenticated')

    user = users_db.get(user_id)
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='User not found')

    avatar_value = request.avatar.strip() if request.avatar else ''
    user['avatar'] = avatar_value if avatar_value else create_user_avatar(user.get('name', 'User'))
    users_db[user_id] = user
    update_user_data(user)

    try:
        await broadcast_to_organization(user['organization_id'], {
            'type': 'user_avatar_updated',
            'user_id': user_id,
            'avatar': user['avatar']
        })
    except Exception as exc:
        logger.debug(f'Avatar update broadcast failed for {user_id}: {exc}')

    sanitized = {k: v for k, v in user.items() if k != 'password_hash'}
    role_value = sanitized.get('role')
    if hasattr(role_value, 'value'):
        sanitized['role'] = role_value.value
    sanitized['is_online'] = user_has_active_session(user_id)

    return UserResponse(**sanitized)

@app.put("/api/users/{user_id}", response_model=UserResponse)
async def update_user_profile(user_id: str, request: UpdateProfileRequest, current_user: dict = Depends(get_current_user)):
    """Update user's profile information (name, email)"""
    current_user_id = current_user.get('id')
    if not current_user_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail='User not authenticated')

    # Users can only update their own profile
    if current_user_id != user_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail='Cannot update another user\'s profile')

    user = users_db.get(user_id)
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='User not found')

    # Update name if provided
    if request.name is not None and request.name.strip():
        user['name'] = request.name.strip()

    # Update email if provided
    if request.email is not None:
        # Check if email is already taken by another user
        email_exists = any(u.get('email') == request.email and u.get('id') != user_id for u in users_db.values())
        if email_exists:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail='Email already in use')
        user['email'] = request.email

    users_db[user_id] = user
    update_user_data(user)

    # Broadcast update to organization
    try:
        await broadcast_to_organization(user['organization_id'], {
            'type': 'user_profile_updated',
            'user_id': user_id,
            'name': user.get('name'),
            'email': user.get('email')
        })
    except Exception as exc:
        logger.debug(f'Profile update broadcast failed for {user_id}: {exc}')

    # Return sanitized user data
    sanitized = {k: v for k, v in user.items() if k != 'password_hash'}
    role_value = sanitized.get('role')
    if hasattr(role_value, 'value'):
        sanitized['role'] = role_value.value
    sanitized['is_online'] = user_has_active_session(user_id)

    return UserResponse(**sanitized)

@app.post("/user/profile-picture", response_model=UserResponse)
async def update_profile_picture(request: UpdateProfilePictureRequest, current_user: dict = Depends(get_current_user)):
    """Update user's profile picture"""
    user_id = current_user.get('id')
    if not user_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail='User not authenticated')

    user = users_db.get(user_id)
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='User not found')

    # Store the base64 profile picture
    user['profile_picture'] = request.profile_picture
    users_db[user_id] = user
    update_user_data(user)

    # Broadcast update to organization
    try:
        await broadcast_to_organization(user['organization_id'], {
            'type': 'user_profile_updated',
            'user_id': user_id,
            'profile_picture': user['profile_picture']
        })
    except Exception as exc:
        logger.debug(f'Profile picture update broadcast failed for {user_id}: {exc}')

    # Return sanitized user data
    sanitized = {k: v for k, v in user.items() if k != 'password_hash'}
    role_value = sanitized.get('role')
    if hasattr(role_value, 'value'):
        sanitized['role'] = role_value.value
    sanitized['is_online'] = user_has_active_session(user_id)

    return UserResponse(**sanitized)

@app.put("/api/users/{user_id}/role", response_model=UserResponse)
async def update_user_role(user_id: str, request: UpdateRoleRequest, current_user: dict = Depends(get_current_user)):
    _r = current_user.get("role")
    _r = _r.value if hasattr(_r, "value") else _r
    if _r != UserRole.SUPER_ADMIN.value:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only super_admin can change roles")
    
    user = users_db.get(user_id)
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    if user.get("organization_id") != current_user.get("organization_id"):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Cannot modify users from another organization")

    user["role"] = request.role.value
    if request.is_active is not None:
        user["is_active"] = bool(request.is_active)

    users_db[user_id] = user
    update_user_data(user)

    payload = {k: v for k, v in user.items() if k != "password_hash"}
    payload['is_online'] = user_has_active_session(user_id)
    return UserResponse(**payload)

# Chat API Endpoints
@app.get("/api/chat/conversations", response_model=List[ConversationResponse])
async def get_conversations(current_user: dict = Depends(get_current_user)):
    """Get all conversations for current user"""
    try:
        logger.info(f"Loading conversations for user: {current_user['name']}")
        
        user_id = current_user['id']
        org_id = current_user['organization_id']
        
        # Get conversations where user is a participant
        user_conversations = []
        
        for conv in conversations_db.values():
            # Check if user is participant and conversation is in same org
            conv_org_id = conv.get('organization_id')
            if not conv_org_id and conv.get('participants'):
                # Get org from first participant if not set
                first_participant = users_db.get(conv['participants'][0])
                if first_participant:
                    conv_org_id = first_participant['organization_id']
            
            if conv_org_id != org_id:
                continue
                
            if user_id not in conv.get('participants', []):
                continue
            
            # Get last message for this conversation
            conv_messages = [
                msg for msg in conversation_messages_db.values()
                if msg.get('conversation_id') == conv['id']
            ]
            conv_messages.sort(key=lambda m: m.get('created_at', ''))
            last_message = conv_messages[-1] if conv_messages else None
            
            # Convert last message to response format
            last_message_response = build_message_response(last_message) if last_message else None
            
            # For direct messages, set name to other participant's name
            conv_name = conv['name']
            conv_avatar = conv.get('avatar')
            if conv['type'] == 'direct' and len(conv['participants']) == 2:
                other_user_id = next((p for p in conv['participants'] if p != user_id), None)
                if other_user_id:
                    other_user = users_db.get(other_user_id)
                    if other_user:
                        conv_name = other_user['name']
                        conv_avatar = other_user['avatar']
            
            conversation_response = ConversationResponse(
                id=conv['id'],
                type=conv['type'],
                name=conv_name,
                participants=conv['participants'],
                last_message=last_message_response,
                unread_count=0,  # TODO: Implement unread count logic
                avatar=conv_avatar,
                created_at=conv.get('created_at', datetime.utcnow().isoformat()),
                updated_at=conv.get('updated_at', datetime.utcnow().isoformat())
            )
            
            user_conversations.append(conversation_response)
        
        logger.info(f"Found {len(user_conversations)} conversations for user {current_user['name']}")
        
        # Sort by last message time or creation time
        user_conversations.sort(
            key=lambda c: c.last_message.created_at if c.last_message else c.created_at,
            reverse=True
        )
        
        return user_conversations
        
    except Exception as e:
        logger.error(f"Error loading conversations: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to load conversations: {str(e)}")

@app.post("/api/chat/conversations", response_model=ConversationResponse)
async def create_conversation(
    request: CreateConversationRequest,
    current_user: dict = Depends(get_current_user)
):
    """Create a new conversation"""
    try:
        logger.info(f"Creating conversation for user: {current_user['name']}")
        
        conversation_id = request.id or str(uuid.uuid4())
        
        # Check if conversation already exists
        if conversation_id in conversations_db:
            existing_conv = conversations_db[conversation_id]
            return ConversationResponse(**existing_conv)
        
        # Validate participants
        participants = request.participants or []
        if current_user['id'] not in participants:
            participants.append(current_user['id'])
        
        # For direct messages, ensure only 2 participants
        if request.type == ConversationType.DIRECT and len(participants) != 2:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Direct conversations must have exactly 2 participants"
            )
        
        # Validate all participants are in same organization
        for participant_id in participants:
            participant = users_db.get(participant_id)
            if not participant or participant['organization_id'] != current_user['organization_id']:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Invalid participant: {participant_id}"
                )
        
        # Generate name for direct messages
        conv_name = request.name
        if request.type == ConversationType.DIRECT and not conv_name:
            other_user_id = next((p for p in participants if p != current_user['id']), None)
            if other_user_id:
                other_user = users_db.get(other_user_id)
                if other_user:
                    conv_name = other_user['name']
        
        conversation = {
            'id': conversation_id,
            'type': request.type.value,
            'name': conv_name or f"Conversation {conversation_id[:8]}",
            'participants': participants,
            'organization_id': current_user['organization_id'],
            'created_at': datetime.utcnow().isoformat(),
            'updated_at': datetime.utcnow().isoformat()
        }
        
        conversations_db[conversation_id] = conversation
        save_conversation_data(conversation)
        
        # Update user conversations mapping
        for participant_id in participants:
            if participant_id not in user_conversations_db:
                user_conversations_db[participant_id] = []
            if conversation_id not in user_conversations_db[participant_id]:
                user_conversations_db[participant_id].append(conversation_id)
        
        logger.info(f"Created conversation: {conversation_id}")
        
        return ConversationResponse(
            id=conversation['id'],
            type=conversation['type'],
            name=conversation['name'],
            participants=conversation['participants'],
            last_message=None,
            unread_count=0,
            created_at=conversation['created_at'],
            updated_at=conversation['updated_at']
        )
        
    except Exception as e:
        logger.error(f"Error creating conversation: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to create conversation: {str(e)}")

@app.get("/api/chat/messages", response_model=List[ConversationMessageResponse])
async def get_chat_messages(
    conversation_id: Optional[str] = None,
    limit: int = 50,
    current_user: dict = Depends(get_current_user)
):
    """Get chat messages for a conversation"""
    try:
        logger.info(f"Loading messages for conversation: {conversation_id}, user: {current_user['name']}")
        
        org_id = current_user['organization_id']
        
        # Default to team chat if no conversation specified
        if not conversation_id:
            conversation_id = f"team-chat-{org_id}"
        
        # Handle legacy team-chat ID
        if conversation_id == "team-chat":
            conversation_id = f"team-chat-{org_id}"
        
        # Verify user has access to conversation
        conversation = conversations_db.get(conversation_id)
        if conversation:
            if current_user['id'] not in conversation.get('participants', []):
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Access denied to conversation"
                )
        
        # Filter messages by conversation
        filtered_messages = []
        for message in conversation_messages_db.values():
            if message.get('conversation_id') != conversation_id:
                continue
            
            # Verify message is from same organization
            msg_author = users_db.get(message.get('author_id'))
            if not msg_author or msg_author.get('organization_id') != org_id:
                continue
                
            filtered_messages.append(message)
        
        # Sort by creation time and limit
        filtered_messages.sort(key=lambda m: m.get('created_at', ''))
        filtered_messages = filtered_messages[-limit:]  # Get last N messages
        
        logger.info(f"Found {len(filtered_messages)} messages for conversation {conversation_id}")
        return [build_message_response(msg) for msg in filtered_messages]
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error loading chat messages: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to load messages: {str(e)}")

@app.post("/api/chat/messages", response_model=ConversationMessageResponse)
async def send_chat_message(
    message_data: ChatMessageRequest,
    current_user: dict = Depends(get_current_user)
):
    """Send a chat message"""
    try:
        content = message_data.content.strip()
        conversation_id = message_data.conversation_id or f"team-chat-{current_user['organization_id']}"
        
        # Handle legacy team-chat ID
        if conversation_id == "team-chat":
            conversation_id = f"team-chat-{current_user['organization_id']}"
        
        if not content:
            raise HTTPException(status_code=400, detail="Message content is required")
        
        logger.info(f"Sending message from {current_user['name']} to {conversation_id}")
        
        # Verify conversation exists or create it
        conversation = conversations_db.get(conversation_id)
        if not conversation:
            # For team chat, create it automatically
            if conversation_id.startswith(f"team-chat-{current_user['organization_id']}"):
                conversation = create_team_conversation(current_user['organization_id'])
                conversation_id = conversation['id']
            else:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Conversation not found"
                )
        
        # Verify user has access to conversation
        if current_user['id'] not in conversation.get('participants', []):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied to conversation"
            )
        
        # Create message record
        message_id = str(uuid.uuid4())
        created_at = datetime.utcnow().isoformat()
        
        message = {
            'id': message_id,
            'content': content,
            'author_id': current_user['id'],
            'author_name': current_user['name'],
            'author_avatar': current_user['avatar'],
            'conversation_id': conversation_id,
            'created_at': created_at,
            'type': 'message',
            'message_type': 'text'
        }

        normalize_message_record(message)
        
        # Save to in-memory and file
        conversation_messages_db[message_id] = message
        save_conversation_message(message)
        
        # Update conversation last activity
        conversation['updated_at'] = created_at
        conversations_db[conversation_id] = conversation
        save_conversation_data(conversation)
        
        # Create response message with profile picture
        message_response = build_message_response(message)
        # Ensure sender profile picture is populated if we have it on the current user
        if not message_response.sender_profile_picture and current_user.get('profile_picture'):
            message_response = message_response.model_copy(
                update={'sender_profile_picture': current_user.get('profile_picture')}
            )

        message_payload = message_response.model_dump()
        message_payload.setdefault('type', message_payload.get('message_type', 'text'))

        # Broadcast to conversation participants
        broadcast_message = {
            'type': 'chat_message',
            'message': message_payload,
            'conversation_id': conversation_id
        }

        await broadcast_to_conversation(conversation_id, broadcast_message)
        
        logger.info(f"Message sent and broadcasted: {message_id}")
        return message_response
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error sending message: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to send message: {str(e)}")

@app.get("/api/chat/conversations/{conversation_id}/messages", response_model=List[ConversationMessageResponse])
async def get_conversation_messages(conversation_id: str, current_user: dict = Depends(get_current_user)):
    """Get all messages for a conversation"""
    try:
        logger.info(f"Loading messages for conversation: {conversation_id}")

        # Get conversation and verify access
        conversation = conversations_db.get(conversation_id)
        if not conversation:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversation not found")

        # Verify user has access
        if current_user['id'] not in conversation.get('participants', []):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")

        # Get messages for this conversation
        messages = [
            msg for msg in conversation_messages_db.values()
            if msg.get('conversation_id') == conversation_id
        ]

        # Sort by created_at
        messages.sort(key=lambda x: x.get('created_at', ''))

        # Convert to response format
        message_responses = [build_message_response(msg) for msg in messages]

        logger.info(f"Found {len(message_responses)} messages for conversation {conversation_id}")
        return message_responses

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error loading conversation messages: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to load messages: {str(e)}")

@app.delete("/api/chat/messages/{message_id}")
async def delete_message(message_id: str, current_user: dict = Depends(get_current_user)):
    """Delete a specific chat message"""
    try:
        logger.info(f"Deleting message: {message_id} by user: {current_user['name']}")

        # Get the message
        message = conversation_messages_db.get(message_id)
        if not message:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Message not found")

        # Verify user is the author or has permission
        if message['author_id'] != current_user['id']:
            # Check if user is admin/manager
            user_role = current_user.get('role', 'developer')
            if user_role not in ['admin', 'manager']:
                raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You can only delete your own messages")

        conversation_id = message['conversation_id']

        # Verify user has access to the conversation
        conversation = conversations_db.get(conversation_id)
        if not conversation or current_user['id'] not in conversation.get('participants', []):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")

        # Delete from in-memory database
        del conversation_messages_db[message_id]

        # Delete from persistent storage
        delete_conversation_message(message_id)

        # Broadcast deletion to conversation participants
        try:
            await broadcast_to_conversation(conversation_id, {
                'type': 'message_deleted',
                'message_id': message_id,
                'conversation_id': conversation_id,
                'deleted_by': current_user['id']
            })
        except Exception as e:
            logger.error(f"Failed to broadcast message deletion: {e}")

        logger.info(f"Message deleted successfully: {message_id}")
        return {"success": True, "message": "Message deleted successfully"}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting message: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to delete message: {str(e)}")

@app.get("/api/chat/users", response_model=List[UserResponse])
async def get_chat_users(current_user: dict = Depends(get_current_user)):
    """Get organization users for chat"""
    try:
        logger.info(f"Loading chat users for org: {current_user['organization_id']}")
        
        org_id = current_user['organization_id']
        org_users = [u for u in users_db.values() if u.get('organization_id') == org_id and u.get('is_active', True)]
        
        # Combine token-based online detection with active connections as fallback
        online_user_ids = get_online_user_ids_for_org(org_id)
        online_user_ids.update({
            user_id for user_id, count in presence_counters.get(org_id, {}).items() if count > 0
        })
        
        # Create response with online status
        user_responses = []
        for user in org_users:
            user_data = {
                "id": user['id'],
                "name": user['name'],
                "email": user['email'],
                "avatar": user['avatar'],
                "role": user.get('role', 'developer'),
                "organization_id": user['organization_id'],
                "is_active": user.get('is_active', True),
                "created_at": user.get('created_at', ''),
                "is_online": user['id'] in online_user_ids
            }
            user_responses.append(UserResponse(**user_data))
        
        logger.info(f"Found {len(user_responses)} chat users, {len(online_user_ids)} online")
        return user_responses
        
    except Exception as e:
        logger.error(f"Error loading chat users: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to load users: {str(e)}")

@app.get("/api/chat/stream")
async def chat_stream(request: Request, token: str):
    user_data = verify_access_token(token)
    if not user_data:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid authentication token")

    org_id = user_data['organization_id']

    queue: asyncio.Queue = asyncio.Queue()
    sse_connections.setdefault(org_id, []).append(queue)

    first_online = _increment_presence(org_id, user_data['id'])
    if first_online:
        await broadcast_to_organization(
            org_id,
            {
                'type': 'user_status_change',
                'user_id': user_data['id'],
                'user_name': user_data['name'],
                'user_avatar': user_data['avatar'],
                'is_online': True
            }
        )

    async def event_generator():
        try:
            while True:
                if await request.is_disconnected():
                    break
                try:
                    message = await asyncio.wait_for(queue.get(), timeout=30)
                    payload = json.dumps(message)
                    event_type = message.get('type', 'message')
                    yield f"event: {event_type}\ndata: {payload}\n\n"
                except asyncio.TimeoutError:
                    heartbeat = { 'type': 'heartbeat', 'timestamp': datetime.utcnow().isoformat() }
                    yield f"event: heartbeat\ndata: {json.dumps(heartbeat)}\n\n"
        finally:
            try:
                sse_connections.get(org_id, []).remove(queue)
                if not sse_connections.get(org_id):
                    sse_connections.pop(org_id, None)
            except ValueError:
                pass
            went_offline = _decrement_presence(org_id, user_data['id'])
            if went_offline and not user_has_active_session(user_data['id']):
                await broadcast_to_organization(
                    org_id,
                    {
                        'type': 'user_status_change',
                        'user_id': user_data['id'],
                        'user_name': user_data['name'],
                        'user_avatar': user_data['avatar'],
                        'is_online': False
                    }
                )

    return StreamingResponse(event_generator(), media_type='text/event-stream')

@app.get("/api/chat/status")
async def chat_status(current_user: dict = Depends(get_current_user)):
    """Get chat system status"""
    org_id = current_user['organization_id']
    active_web_connections = active_chat_connections.get(org_id, [])
    presence = presence_counters.get(org_id, {})

    token_online_ids = get_online_user_ids_for_org(org_id)
    presence_online_ids = {user_id for user_id, count in presence.items() if count > 0}
    combined_online_ids = token_online_ids | presence_online_ids

    online_users = []
    for user_id in combined_online_ids:
        user_record = users_db.get(user_id, {})
        if not user_record:
            continue
        online_users.append({
            'user_id': user_id,
            'user_name': user_record.get('name', ''),
        })

    return {
        'organization_id': org_id,
        'active_connections': sum(presence.values()) if presence else len(active_web_connections),
        'token_online_count': len(token_online_ids),
        'online_users': online_users,
        'total_messages': len(conversation_messages_db),
        'total_conversations': len(conversations_db),
        'supports_websocket': WEBSOCKET_LIB_AVAILABLE
    }

# Enhanced WebSocket endpoint with chat support
@app.websocket('/ws/{token}')
async def websocket_chat(websocket: WebSocket, token: str):
    user_data = verify_access_token(token)
    if not user_data:
        await websocket.close(code=1008, reason="Invalid token")
        return
    
    await websocket.accept()
    logger.info(f"WebSocket connected: {user_data['name']}")
    
    org_id = user_data['organization_id']
    first_online = add_chat_connection(org_id, websocket, user_data)

    # Ensure team conversation exists
    create_team_conversation(org_id)

    if first_online:
        await broadcast_to_organization(
            org_id,
            {
                'type': 'user_status_change',
                'user_id': user_data['id'],
                'user_name': user_data['name'],
                'user_avatar': user_data['avatar'],
                'is_online': True
            },
            exclude_websocket=websocket
        )

    try:
        while True:
            msg_text = await websocket.receive_text()
            try:
                payload = json.loads(msg_text)
            except Exception:
                continue
            
            mtype = payload.get('type')
            logger.info(f"WebSocket message from {user_data['name']}: {mtype}")
            
            # Handle conversation-based chat messages
            if mtype == 'chat_message':
                conversation_id = payload.get('conversation_id', f"team-chat-{org_id}")
                content = (payload.get('content') or '').strip()
                
                # Handle legacy team-chat ID
                if conversation_id == "team-chat":
                    conversation_id = f"team-chat-{org_id}"
                
                if content:
                    # Verify conversation exists
                    conversation = conversations_db.get(conversation_id)
                    if not conversation:
                        if conversation_id.startswith(f"team-chat-{org_id}"):
                            conversation = create_team_conversation(org_id)
                            conversation_id = conversation['id']
                        else:
                            continue  # Skip if conversation doesn't exist
                    
                    # Verify user has access
                    if user_data['id'] not in conversation.get('participants', []):
                        continue
                    
                    # Create and save message
                    message_id = str(uuid.uuid4())
                    created_at = datetime.utcnow().isoformat()
                    
                    message = {
                        'id': message_id,
                        'content': content,
                        'author_id': user_data['id'],
                        'author_name': user_data['name'],
                        'author_avatar': user_data['avatar'],
                        'conversation_id': conversation_id,
                        'created_at': created_at,
                        'type': 'message'
                    }
                    
                    conversation_messages_db[message_id] = message
                    save_conversation_message(message)
                    
                    # Update conversation
                    conversation['updated_at'] = created_at
                    conversations_db[conversation_id] = conversation
                    save_conversation_data(conversation)
                    
                    # Broadcast to conversation participants
                    await broadcast_to_conversation(
                        conversation_id,
                        {
                            'type': 'chat_message',
                            'message': message,
                            'conversation_id': conversation_id
                        }
                    )
            
            # Handle typing indicators
            elif mtype == 'chat_typing':
                conversation_id = payload.get('conversation_id', f"team-chat-{org_id}")
                is_typing = payload.get('is_typing', False)
                
                await broadcast_to_conversation(
                    conversation_id,
                    {
                        'type': 'chat_typing',
                        'conversation_id': conversation_id,
                        'user_id': user_data['id'],
                        'user_name': user_data['name'],
                        'is_typing': is_typing
                    },
                    exclude_websocket=websocket
                )
                
    except WebSocketDisconnect:
        logger.info(f"WebSocket disconnected: {user_data['name']}")
    except Exception as e:
        logger.error(f"WebSocket error for {user_data['name']}: {e}")
    finally:
        # Remove from chat connections
        went_offline = remove_chat_connection(org_id, websocket, user_data['id'])

        if went_offline and not user_has_active_session(user_data['id']):
            await broadcast_to_organization(
                org_id,
                {
                    'type': 'user_status_change',
                    'user_id': user_data['id'],
                    'user_name': user_data['name'],
                    'user_avatar': user_data['avatar'],
                    'is_online': False
                }
            )

# Debug endpoints
# Add these debug endpoints and improvements to your existing backend

# Add this debug endpoint to check token status
@app.get("/debug/token-status/{token}")
async def debug_token_status(token: str):
    """Debug endpoint to check token status"""
    user_id = sessions_db.get(token)
    user_data = users_db.get(user_id) if user_id else None
    
    return {
        "token": token[:10] + "..." if len(token) > 10 else token,
        "token_exists_in_sessions": token in sessions_db,
        "user_id_from_token": user_id,
        "user_exists": bool(user_data),
        "user_name": user_data.get('name') if user_data else None,
        "total_sessions": len(sessions_db),
        "sessions_sample": {k[:10] + "...": v for k, v in list(sessions_db.items())[:3]}
    }

@app.get("/debug/sessions")
async def debug_sessions():
    """Debug endpoint to check all sessions"""
    return {
        "total_sessions": len(sessions_db),
        "sessions": {k[:10] + "...": v for k, v in sessions_db.items()}
    }

# Update the verify_access_token function with better logging
def verify_access_token(token: str) -> Optional[dict]:
    """Verify access token and return user data"""
    try:
        logger.info(f"🔍 Verifying token: {token[:10]}... (length: {len(token)})")
        logger.info(f"📊 Total sessions in memory: {len(sessions_db)}")
        
        user_id = sessions_db.get(token)
        if not user_id:
            logger.warning(f"❌ Token not found in sessions_db. Available tokens: {len(sessions_db)}")
            if sessions_db:
                sample_tokens = list(sessions_db.keys())[:3]
                logger.info(f"🔍 Sample tokens: {[t[:10] + '...' for t in sample_tokens]}")
            return None
        
        logger.info(f"✅ Token found, user_id: {user_id}")
        
        user = users_db.get(user_id)
        if not user:
            logger.warning(f"❌ User not found for user_id: {user_id}")
            return None
        
        logger.info(f"✅ User found: {user.get('name', 'Unknown')}")
        return user
    except Exception as e:
        logger.error(f"💥 Token verification error: {e}")
        return None

# Enhanced create_access_token function with better logging
def create_access_token(user_id: str) -> str:
    """Create access token for user"""
    token = secrets.token_urlsafe(32)
    sessions_db[token] = user_id
    logger.info(f"🔑 Created access token for user: {user_id}")
    logger.info(f"🎟️ Token: {token[:10]}... (length: {len(token)})")
    logger.info(f"💾 Sessions count after creation: {len(sessions_db)}")
    return token

# Enhanced WebSocket endpoint with better error handling
@app.websocket('/ws/{token}')
async def websocket_chat(websocket: WebSocket, token: str):
    logger.info(f"🔌 WebSocket connection attempt with token: {token[:10]}...")
    
    user_data = verify_access_token(token)
    if not user_data:
        logger.error(f"❌ WebSocket authentication failed for token: {token[:10]}...")
        await websocket.close(code=1008, reason="Invalid token")
        return
    
    try:
        await websocket.accept()
        logger.info(f"✅ WebSocket connected: {user_data['name']}")
        
        org_id = user_data['organization_id']
        first_online = add_chat_connection(org_id, websocket, user_data)

        # Ensure team conversation exists
        create_team_conversation(org_id)

        if first_online:
            await broadcast_to_organization(
                org_id,
                {
                    'type': 'user_status_change',
                    'user_id': user_data['id'],
                    'user_name': user_data['name'],
                    'user_avatar': user_data['avatar'],
                    'is_online': True
                },
                exclude_websocket=websocket
            )

        while True:
            msg_text = await websocket.receive_text()
            try:
                payload = json.loads(msg_text)
            except Exception:
                continue
            
            mtype = payload.get('type')
            logger.info(f"📨 WebSocket message from {user_data['name']}: {mtype}")
            
            # Handle conversation-based chat messages
            if mtype == 'chat_message':
                conversation_id = payload.get('conversation_id', f"team-chat-{org_id}")
                content = (payload.get('content') or '').strip()
                
                # Handle legacy team-chat ID
                if conversation_id == "team-chat":
                    conversation_id = f"team-chat-{org_id}"
                
                if content:
                    # Verify conversation exists
                    conversation = conversations_db.get(conversation_id)
                    if not conversation:
                        if conversation_id.startswith(f"team-chat-{org_id}"):
                            conversation = create_team_conversation(org_id)
                            conversation_id = conversation['id']
                        else:
                            continue  # Skip if conversation doesn't exist
                    
                    # Verify user has access
                    if user_data['id'] not in conversation.get('participants', []):
                        continue
                    
                    # Create and save message
                    message_id = str(uuid.uuid4())
                    created_at = datetime.utcnow().isoformat()
                    
                    message = {
                        'id': message_id,
                        'content': content,
                        'author_id': user_data['id'],
                        'author_name': user_data['name'],
                        'author_avatar': user_data['avatar'],
                        'conversation_id': conversation_id,
                        'created_at': created_at,
                        'type': 'message'
                    }
                    
                    conversation_messages_db[message_id] = message
                    save_conversation_message(message)
                    
                    # Update conversation
                    conversation['updated_at'] = created_at
                    conversations_db[conversation_id] = conversation
                    save_conversation_data(conversation)
                    
                    # Broadcast to conversation participants
                    await broadcast_to_conversation(
                        conversation_id,
                        {
                            'type': 'chat_message',
                            'message': message,
                            'conversation_id': conversation_id
                        }
                    )
            
            # Handle typing indicators
            elif mtype == 'chat_typing':
                conversation_id = payload.get('conversation_id', f"team-chat-{org_id}")
                is_typing = payload.get('is_typing', False)
                
                await broadcast_to_conversation(
                    conversation_id,
                    {
                        'type': 'chat_typing',
                        'conversation_id': conversation_id,
                        'user_id': user_data['id'],
                        'user_name': user_data['name'],
                        'is_typing': is_typing
                    },
                    exclude_websocket=websocket
                )
                
    except WebSocketDisconnect:
        logger.info(f"🔌 WebSocket disconnected: {user_data['name']}")
    except Exception as e:
        logger.error(f"💥 WebSocket error for {user_data['name']}: {e}")
    finally:
        # Remove from chat connections
        went_offline = remove_chat_connection(org_id, websocket, user_data['id'])

        if went_offline and not user_has_active_session(user_data['id']):
            await broadcast_to_organization(
                org_id,
                {
                    'type': 'user_status_change',
                    'user_id': user_data['id'],
                    'user_name': user_data['name'],
                    'user_avatar': user_data['avatar'],
                    'is_online': False
                }
            )

# Enhanced login endpoint with better token logging
@app.post("/api/auth/login", response_model=AuthResponse)
async def login(request: LoginRequest):
    logger.info(f"Login request for: {request.email}")

    user = None
    for u in users_db.values():
        if u.get('email') == request.email:
            user = u
            break

    if not user:
        logger.warning(f"Login failed - user not found: {request.email}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password"
        )

    if not verify_password(request.password, user.get('password_hash', '')):
        logger.warning(f"Login failed - wrong password: {request.email}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password"
        )

    if not user.get('is_active', False):
        logger.warning(f"Login failed - user inactive: {request.email}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User account is inactive"
        )

    organization = organizations_db.get(user['organization_id'])
    if not organization:
        logger.error(f"Organization not found for user: {user['organization_id']}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Organization not found"
        )

    # Ensure team conversation exists
    create_team_conversation(user['organization_id'])

    was_online = user_has_active_session(user['id'])
    access_token = create_access_token(user['id'])
    if not was_online:
        await broadcast_to_organization(
            user['organization_id'],
            {
                'type': 'user_status_change',
                'user_id': user['id'],
                'user_name': user['name'],
                'user_avatar': user.get('avatar'),
                'is_online': True
            }
        )

    logger.info(f"Login successful: {user['name']} ({user['email']})")
    logger.info(f"Token created: {access_token[:10]}...")

    user_payload = {k: v for k, v in user.items() if k != "password_hash"}
    user_payload['is_online'] = True
    user_response = UserResponse(**user_payload)
    org_response = OrganizationResponse(**organization)

    return AuthResponse(
        access_token=access_token,
        token_type="bearer",
        user=user_response,
        organization=org_response
    )
@app.get("/debug/clear-users")
async def debug_clear_users():
    global users_db, sessions_db
    users_db.clear()
    sessions_db.clear()
    try:
        path = get_data_path("users.json")
        with open(path, "w") as f:
            json.dump({"users": []}, f, indent=2)
    except Exception as e:
        logger.error(f"Failed to truncate users.json: {e}")
    return {"message": "Users and sessions cleared"}

@app.get("/debug/clear-sessions")
async def debug_clear_sessions():
    global sessions_db
    sessions_db.clear()
    return {"message": "Sessions cleared"}

@app.get("/debug/data")
async def debug_data():
    return {
        "users_count": len(users_db),
        "organizations_count": len(organizations_db),
        "issues_count": len(issues_db),
        "comments_count": len(comments_db),
        "sessions_count": len(sessions_db),
        "conversations_count": len(conversations_db),
        "chat_messages_count": len(conversation_messages_db),
        "active_connections": len(sum(active_chat_connections.values(), [])),
        "timestamp": datetime.utcnow().isoformat()
    }

@app.get("/debug/clear")
async def debug_clear():
    global users_db, organizations_db, issues_db, comments_db, otp_db, sessions_db, issue_counter
    global conversations_db, conversation_messages_db, user_conversations_db
    global active_chat_connections, sse_connections, presence_counters

    users_db.clear()
    organizations_db.clear()
    issues_db.clear()
    comments_db.clear()
    otp_db.clear()
    sessions_db.clear()
    conversations_db.clear()
    conversation_messages_db.clear()
    user_conversations_db.clear()
    active_chat_connections.clear()
    sse_connections.clear()
    presence_counters.clear()
    issue_counter = 1

    logger.info("All data cleared")

    return {"message": "All data cleared successfully"}

# Error handlers
@app.exception_handler(HTTPException)
async def http_exception_handler(request, exc):
    logger.error(f"HTTP Exception: {exc.status_code} - {exc.detail}")
    from fastapi.responses import JSONResponse
    return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})

@app.exception_handler(Exception)
async def general_exception_handler(request, exc):
    logger.error(f"Unhandled exception: {str(exc)}")
    from fastapi.responses import JSONResponse
    return JSONResponse(status_code=500, content={"detail": "Internal server error"})

# Startup event
@app.on_event("startup")
async def startup_event():
    logger.info("Starting Scope API...")

    # Log database configuration
    logger.info(f"Database URL: {DATABASE_URL.split('@')[-1] if '@' in DATABASE_URL else DATABASE_URL}")

    # Initialize database (create tables if they don't exist)
    try:
        init_db()
        logger.info("Database tables initialized successfully")
    except Exception as e:
        logger.error(f"Failed to initialize database: {e}")
        raise

    load_data_from_files()
    load_chat_data_from_files()
    log_data_state()



if __name__ == "__main__":
    import uvicorn
    
    print(f"\n{'='*70}")
    print(f">> STARTING SCOPE API SERVER")
    print(f">> Server URL: http://localhost:4000")
    print(f">> Health Check: http://localhost:4000/healthz")
    print(f">> Test: http://localhost:4000/test")
    print(f">> Frontend: http://localhost:3000")
    print(f">> API Docs: http://localhost:4000/docs")
    print(f">> Chat System: ENABLED")
    print(f">> Direct Messages: ENABLED")
    print(f">> Team Chat: ENABLED")
    print(f"{'='*70}\n")
    
    try:
        uvicorn.run(
            "main:app",
            host="0.0.0.0", 
            port=4000, 
            reload=True,
            log_level="info"
        )
    except KeyboardInterrupt:
        print("\n🛑 Server stopped by user")
    except Exception as e:
        print(f"\n❌ Server error: {e}")
        print("Please check your configuration and try again")
