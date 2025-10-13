# Add this to your schemas.py file or create a new chat_schemas.py

from pydantic import BaseModel, Field
from typing import List, Optional, Union
from datetime import datetime
from uuid import UUID

class MessageCreate(BaseModel):
    content: str = Field(..., min_length=1, max_length=1000)
    conversation_id: Optional[UUID] = None
    recipient_id: Optional[UUID] = None

class MessageResponse(BaseModel):
    id: UUID
    content: str
    author_id: UUID
    author_name: str
    author_avatar: str
    conversation_id: UUID
    message_type: str
    created_at: datetime
    updated_at: datetime
    edited: bool
    
    class Config:
        from_attributes = True

class ConversationCreate(BaseModel):
    type: str = Field(..., regex="^(team|direct)$")
    participant_id: Optional[UUID] = None  # For direct messages
    name: Optional[str] = None

class ConversationParticipantResponse(BaseModel):
    id: UUID
    user_id: UUID
    user_name: str
    user_avatar: str
    joined_at: datetime
    last_read_message_id: Optional[UUID] = None
    
    class Config:
        from_attributes = True

class ConversationResponse(BaseModel):
    id: UUID
    type: str
    name: str
    created_at: datetime
    updated_at: datetime
    participants: List[ConversationParticipantResponse]
    last_message: Optional[MessageResponse] = None
    unread_count: int = 0
    
    class Config:
        from_attributes = True

class ConversationListResponse(BaseModel):
    conversations: List[ConversationResponse]

class MessagesResponse(BaseModel):
    messages: List[MessageResponse]
    total: int
    page: int
    limit: int

class UserStatusUpdate(BaseModel):
    is_online: bool
    last_activity: Optional[datetime] = None

class UserStatusResponse(BaseModel):
    user_id: UUID
    is_online: bool
    last_seen: datetime
    last_activity: datetime
    
    class Config:
        from_attributes = True

class TypingIndicator(BaseModel):
    conversation_id: UUID
    user_id: UUID
    is_typing: bool

class WebSocketMessage(BaseModel):
    type: str
    data: Union[MessageResponse, TypingIndicator, UserStatusResponse, dict]
    conversation_id: Optional[UUID] = None
    user_id: Optional[UUID] = None