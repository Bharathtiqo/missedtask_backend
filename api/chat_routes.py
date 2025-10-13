# Create a new file: chat_routes.py

from fastapi import APIRouter, Depends, HTTPException, WebSocket, WebSocketDisconnect, Query
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import and_, or_, desc, func
from database import get_db
from .auth import get_current_user
from models import User, Organization
from chat_models import Conversation, ConversationParticipant, Message, UserStatus
from chat_schemas import (
    ConversationCreate, ConversationResponse, ConversationListResponse,
    MessageCreate, MessageResponse, MessagesResponse,
    UserStatusResponse, WebSocketMessage
)
from websocket_manager import connection_manager
from typing import List, Optional
from uuid import UUID
import json
import logging
from datetime import datetime

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/chat", tags=["chat"])

# ============= CONVERSATION ENDPOINTS =============

@router.get("/conversations", response_model=ConversationListResponse)
async def get_user_conversations(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get all conversations for the current user"""
    
    # Get conversations where user is a participant
    conversations_query = (
        db.query(Conversation)
        .join(ConversationParticipant)
        .filter(ConversationParticipant.user_id == current_user.id)
        .filter(Conversation.organization_id == current_user.organization_id)
        .options(
            joinedload(Conversation.participants).joinedload(ConversationParticipant.user),
            joinedload(Conversation.messages).joinedload(Message.author)
        )
        .order_by(desc(Conversation.updated_at))
        .all()
    )
    
    # Create team conversation if it doesn't exist
    team_conv = next((c for c in conversations_query if c.type == 'team'), None)
    if not team_conv:
        team_conv = create_team_conversation(db, current_user.organization_id)
        conversations_query.insert(0, team_conv)
    
    conversations_response = []
    for conv in conversations_query:
        # Get last message
        last_message = (
            db.query(Message)
            .filter(Message.conversation_id == conv.id)
            .order_by(desc(Message.created_at))
            .first()
        )
        
        # Calculate unread count
        user_participant = next(
            (p for p in conv.participants if p.user_id == current_user.id), 
            None
        )
        
        unread_count = 0
        if user_participant and last_message:
            unread_count = (
                db.query(Message)
                .filter(Message.conversation_id == conv.id)
                .filter(Message.created_at > (user_participant.last_read_message.created_at if user_participant.last_read_message else datetime.min))
                .filter(Message.author_id != current_user.id)  # Don't count own messages
                .count()
            )
        
        # Format conversation name for direct messages
        conv_name = conv.name
        if conv.type == 'direct':
            other_participant = next(
                (p for p in conv.participants if p.user_id != current_user.id), 
                None
            )
            if other_participant:
                conv_name = other_participant.user.name
        
        conv_response = ConversationResponse(
            id=conv.id,
            type=conv.type,
            name=conv_name,
            created_at=conv.created_at,
            updated_at=conv.updated_at,
            participants=[
                {
                    "id": p.id,
                    "user_id": p.user_id,
                    "user_name": p.user.name,
                    "user_avatar": p.user.avatar,
                    "joined_at": p.joined_at,
                    "last_read_message_id": p.last_read_message_id
                }
                for p in conv.participants
            ],
            last_message={
                "id": last_message.id,
                "content": last_message.content,
                "author_id": last_message.author_id,
                "author_name": last_message.author.name,
                "author_avatar": last_message.author.avatar,
                "conversation_id": last_message.conversation_id,
                "message_type": last_message.message_type,
                "created_at": last_message.created_at,
                "updated_at": last_message.updated_at,
                "edited": last_message.edited
            } if last_message else None,
            unread_count=unread_count
        )
        conversations_response.append(conv_response)
    
    return ConversationListResponse(conversations=conversations_response)

@router.post("/conversations", response_model=ConversationResponse)
async def create_conversation(
    conversation_data: ConversationCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Create a new conversation"""
    
    if conversation_data.type == "direct":
        if not conversation_data.participant_id:
            raise HTTPException(status_code=400, detail="participant_id required for direct messages")
        
        # Check if direct conversation already exists
        existing_conv = (
            db.query(Conversation)
            .join(ConversationParticipant, Conversation.id == ConversationParticipant.conversation_id)
            .filter(Conversation.type == "direct")
            .filter(Conversation.organization_id == current_user.organization_id)
            .group_by(Conversation.id)
            .having(
                func.count(ConversationParticipant.user_id) == 2,
                func.bool_and(
                    or_(
                        ConversationParticipant.user_id == current_user.id,
                        ConversationParticipant.user_id == conversation_data.participant_id
                    )
                )
            )
            .first()
        )
        
        if existing_conv:
            raise HTTPException(status_code=400, detail="Direct conversation already exists")
        
        # Verify participant exists and is in same organization
        participant = db.query(User).filter(
            User.id == conversation_data.participant_id,
            User.organization_id == current_user.organization_id,
            User.is_active == True
        ).first()
        
        if not participant:
            raise HTTPException(status_code=404, detail="Participant not found")
    
    # Create conversation
    conversation = Conversation(
        type=conversation_data.type,
        name=conversation_data.name or ("Team Chat" if conversation_data.type == "team" else None),
        organization_id=current_user.organization_id
    )
    db.add(conversation)
    db.flush()
    
    # Add participants
    participants = [current_user.id]
    if conversation_data.type == "direct" and conversation_data.participant_id:
        participants.append(conversation_data.participant_id)
    elif conversation_data.type == "team":
        # Add all active users in organization
        org_users = db.query(User).filter(
            User.organization_id == current_user.organization_id,
            User.is_active == True
        ).all()
        participants = [user.id for user in org_users]
    
    for user_id in participants:
        participant = ConversationParticipant(
            conversation_id=conversation.id,
            user_id=user_id
        )
        db.add(participant)
    
    db.commit()
    db.refresh(conversation)
    
    return get_conversation_response(db, conversation.id, current_user.id)

# ============= MESSAGE ENDPOINTS =============

@router.get("/conversations/{conversation_id}/messages", response_model=MessagesResponse)
async def get_conversation_messages(
    conversation_id: UUID,
    page: int = Query(1, ge=1),
    limit: int = Query(50, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get messages for a specific conversation"""
    
    # Verify user has access to conversation
    participant = (
        db.query(ConversationParticipant)
        .filter(
            ConversationParticipant.conversation_id == conversation_id,
            ConversationParticipant.user_id == current_user.id
        )
        .first()
    )
    
    if not participant:
        raise HTTPException(status_code=403, detail="Access denied to this conversation")
    
    # Get messages with pagination
    offset = (page - 1) * limit
    messages_query = (
        db.query(Message)
        .filter(Message.conversation_id == conversation_id)
        .options(joinedload(Message.author))
        .order_by(desc(Message.created_at))
        .offset(offset)
        .limit(limit)
        .all()
    )
    
    # Reverse to get chronological order
    messages_query.reverse()
    
    # Get total count
    total = db.query(Message).filter(Message.conversation_id == conversation_id).count()
    
    messages_response = [
        MessageResponse(
            id=msg.id,
            content=msg.content,
            author_id=msg.author_id,
            author_name=msg.author.name,
            author_avatar=msg.author.avatar,
            conversation_id=msg.conversation_id,
            message_type=msg.message_type,
            created_at=msg.created_at,
            updated_at=msg.updated_at,
            edited=msg.edited
        )
        for msg in messages_query
    ]
    
    return MessagesResponse(
        messages=messages_response,
        total=total,
        page=page,
        limit=limit
    )

@router.post("/conversations/{conversation_id}/messages", response_model=MessageResponse)
async def send_message_to_conversation(
    conversation_id: UUID,
    message_data: MessageCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Send message to specific conversation"""
    
    # Verify user has access to conversation
    conversation = (
        db.query(Conversation)
        .filter(Conversation.id == conversation_id)
        .options(joinedload(Conversation.participants))
        .first()
    )
    
    if not conversation:
        raise HTTPException(status_code=404, detail="Conversation not found")
    
    participant = next(
        (p for p in conversation.participants if p.user_id == current_user.id), 
        None
    )
    
    if not participant:
        raise HTTPException(status_code=403, detail="Access denied to this conversation")
    
    # Create message
    message = Message(
        conversation_id=conversation_id,
        author_id=current_user.id,
        content=message_data.content,
        message_type="message"
    )
    db.add(message)
    
    # Update conversation timestamp
    conversation.updated_at = datetime.now()
    
    db.commit()
    db.refresh(message)
    
    # Create response
    message_response = MessageResponse(
        id=message.id,
        content=message.content,
        author_id=message.author_id,
        author_name=current_user.name,
        author_avatar=current_user.avatar,
        conversation_id=message.conversation_id,
        message_type=message.message_type,
        created_at=message.created_at,
        updated_at=message.updated_at,
        edited=message.edited
    )
    
    # Broadcast to conversation participants
    participant_ids = [str(p.user_id) for p in conversation.participants]
    await connection_manager.broadcast_to_conversation(
        participant_ids,
        {
            "type": "chat_message" if conversation.type == "team" else "direct_message",
            "message": message_response.dict(),
            "conversation_id": str(conversation_id)
        },
        exclude_user=str(current_user.id)
    )
    
    return message_response

# ============= TEAM CHAT ENDPOINTS (Legacy support) =============

@router.get("/messages", response_model=MessagesResponse)
async def get_team_messages(
    page: int = Query(1, ge=1),
    limit: int = Query(50, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get team chat messages (legacy endpoint)"""
    
    # Get or create team conversation
    team_conv = get_or_create_team_conversation(db, current_user.organization_id)
    
    return await get_conversation_messages(team_conv.id, page, limit, current_user, db)

@router.post("/messages", response_model=MessageResponse)
async def send_team_message(
    message_data: MessageCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Send message to team chat (legacy endpoint)"""
    
    # Get or create team conversation
    team_conv = get_or_create_team_conversation(db, current_user.organization_id)
    
    return await send_message_to_conversation(team_conv.id, message_data, current_user, db)

# ============= WEBSOCKET ENDPOINT =============

@router.websocket("/ws/{token}")
async def websocket_endpoint(
    websocket: WebSocket,
    token: str,
    db: Session = Depends(get_db)
):
    """WebSocket endpoint for real-time communication"""
    
    # Verify token and get user
    try:
        from auth import verify_access_token
        payload = verify_access_token(token)
        user_id = payload.get("sub")
        
        if not user_id:
            await websocket.close(code=4001, reason="Invalid token")
            return
            
        user = db.query(User).filter(User.id == user_id).first()
        if not user or not user.is_active:
            await websocket.close(code=4001, reason="User not found")
            return
            
    except Exception as e:
        logger.error(f"WebSocket authentication error: {e}")
        await websocket.close(code=4001, reason="Authentication failed")
        return
    
    # Connect user
    await connection_manager.connect(websocket, str(user.id), str(user.organization_id))
    
    # Update user online status
    update_user_online_status(db, user.id, True)
    
    try:
        while True:
            # Receive message from client
            data = await websocket.receive_text()
            message_data = json.loads(data)
            
            message_type = message_data.get("type")
            
            if message_type == "typing":
                # Handle typing indicator
                conversation_id = message_data.get("conversation_id")
                if conversation_id:
                    connection_manager.set_typing_status(conversation_id, str(user.id), True)
                    
                    # Get conversation participants
                    conversation = db.query(Conversation).filter(Conversation.id == conversation_id).first()
                    if conversation:
                        participant_ids = [
                            str(p.user_id) for p in conversation.participants 
                            if p.user_id != user.id
                        ]
                        
                        await connection_manager.broadcast_to_conversation(
                            participant_ids,
                            {
                                "type": "user_typing",
                                "user_id": str(user.id),
                                "conversation_id": conversation_id
                            }
                        )
            
            elif message_type == "stop_typing":
                # Handle stop typing
                conversation_id = message_data.get("conversation_id")
                if conversation_id:
                    connection_manager.set_typing_status(conversation_id, str(user.id), False)
                    
                    # Get conversation participants
                    conversation = db.query(Conversation).filter(Conversation.id == conversation_id).first()
                    if conversation:
                        participant_ids = [
                            str(p.user_id) for p in conversation.participants 
                            if p.user_id != user.id
                        ]
                        
                        await connection_manager.broadcast_to_conversation(
                            participant_ids,
                            {
                                "type": "user_stopped_typing",
                                "user_id": str(user.id),
                                "conversation_id": conversation_id
                            }
                        )
            
            # Update last activity
            update_user_last_activity(db, user.id)
            
    except WebSocketDisconnect:
        pass
    except Exception as e:
        logger.error(f"WebSocket error for user {user.id}: {e}")
    finally:
        # Disconnect user
        organization_id = connection_manager.disconnect(str(user.id))
        
        # Update user offline status
        update_user_online_status(db, user.id, False)
        
        # Notify others that user went offline
        if organization_id:
            await connection_manager.broadcast_to_organization(
                organization_id,
                {
                    "type": "user_offline",
                    "user_id": str(user.id),
                    "timestamp": datetime.now().isoformat()
                }
            )

# ============= HELPER FUNCTIONS =============

def create_team_conversation(db: Session, organization_id: UUID) -> Conversation:
    """Create team conversation for organization"""
    conversation = Conversation(
        type="team",
        name="Team Chat",
        organization_id=organization_id
    )
    db.add(conversation)
    db.flush()
    
    # Add all active users in organization as participants
    org_users = db.query(User).filter(
        User.organization_id == organization_id,
        User.is_active == True
    ).all()
    
    for user in org_users:
        participant = ConversationParticipant(
            conversation_id=conversation.id,
            user_id=user.id
        )
        db.add(participant)
    
    db.commit()
    return conversation

def get_or_create_team_conversation(db: Session, organization_id: UUID) -> Conversation:
    """Get existing team conversation or create new one"""
    team_conv = (
        db.query(Conversation)
        .filter(
            Conversation.type == "team",
            Conversation.organization_id == organization_id
        )
        .first()
    )
    
    if not team_conv:
        team_conv = create_team_conversation(db, organization_id)
    
    return team_conv

def get_conversation_response(db: Session, conversation_id: UUID, user_id: UUID) -> ConversationResponse:
    """Get formatted conversation response"""
    conversation = (
        db.query(Conversation)
        .filter(Conversation.id == conversation_id)
        .options(
            joinedload(Conversation.participants).joinedload(ConversationParticipant.user)
        )
        .first()
    )
    
    if not conversation:
        raise HTTPException(status_code=404, detail="Conversation not found")
    
    # Get last message
    last_message = (
        db.query(Message)
        .filter(Message.conversation_id == conversation_id)
        .options(joinedload(Message.author))
        .order_by(desc(Message.created_at))
        .first()
    )
    
    return ConversationResponse(
        id=conversation.id,
        type=conversation.type,
        name=conversation.name,
        created_at=conversation.created_at,
        updated_at=conversation.updated_at,
        participants=[
            {
                "id": p.id,
                "user_id": p.user_id,
                "user_name": p.user.name,
                "user_avatar": p.user.avatar,
                "joined_at": p.joined_at,
                "last_read_message_id": p.last_read_message_id
            }
            for p in conversation.participants
        ],
        last_message={
            "id": last_message.id,
            "content": last_message.content,
            "author_id": last_message.author_id,
            "author_name": last_message.author.name,
            "author_avatar": last_message.author.avatar,
            "conversation_id": last_message.conversation_id,
            "message_type": last_message.message_type,
            "created_at": last_message.created_at,
            "updated_at": last_message.updated_at,
            "edited": last_message.edited
        } if last_message else None,
        unread_count=0
    )

def update_user_online_status(db: Session, user_id: UUID, is_online: bool):
    """Update user online status"""
    user_status = db.query(UserStatus).filter(UserStatus.user_id == user_id).first()
    
    if not user_status:
        user_status = UserStatus(user_id=user_id, is_online=is_online)
        db.add(user_status)
    else:
        user_status.is_online = is_online
        if not is_online:
            user_status.last_seen = datetime.now()
    
    db.commit()

def update_user_last_activity(db: Session, user_id: UUID):
    """Update user last activity timestamp"""
    user_status = db.query(UserStatus).filter(UserStatus.user_id == user_id).first()
    
    if user_status:
        user_status.last_activity = datetime.now()
        db.commit()