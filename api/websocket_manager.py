# Create a new file: websocket_manager.py

from fastapi import WebSocket, WebSocketDisconnect
from typing import Dict, List, Set
import json
import logging
from uuid import UUID
from datetime import datetime

logger = logging.getLogger(__name__)

class ConnectionManager:
    def __init__(self):
        # Store active connections by user_id
        self.active_connections: Dict[str, WebSocket] = {}
        # Store user organizations for message routing
        self.user_organizations: Dict[str, str] = {}
        # Store typing status
        self.typing_users: Dict[str, Set[str]] = {}  # conversation_id -> set of user_ids
        
    async def connect(self, websocket: WebSocket, user_id: str, organization_id: str):
        """Accept websocket connection and store user info"""
        await websocket.accept()
        self.active_connections[user_id] = websocket
        self.user_organizations[user_id] = organization_id
        
        logger.info(f"User {user_id} connected to WebSocket")
        
        # Notify others in organization that user is online
        await self.broadcast_to_organization(
            organization_id,
            {
                "type": "user_online",
                "user_id": user_id,
                "timestamp": datetime.now().isoformat()
            },
            exclude_user=user_id
        )
    
    def disconnect(self, user_id: str):
        """Remove user connection"""
        if user_id in self.active_connections:
            del self.active_connections[user_id]
            
        organization_id = self.user_organizations.get(user_id)
        if user_id in self.user_organizations:
            del self.user_organizations[user_id]
            
        # Remove from typing indicators
        for conversation_id in self.typing_users:
            self.typing_users[conversation_id].discard(user_id)
            
        logger.info(f"User {user_id} disconnected from WebSocket")
        
        # Notify others that user went offline
        if organization_id:
            return organization_id
        return None
    
    async def send_personal_message(self, user_id: str, message: dict):
        """Send message to specific user"""
        if user_id in self.active_connections:
            websocket = self.active_connections[user_id]
            try:
                await websocket.send_text(json.dumps(message, default=str))
                return True
            except Exception as e:
                logger.error(f"Error sending message to {user_id}: {e}")
                # Connection might be dead, remove it
                self.disconnect(user_id)
                return False
        return False
    
    async def broadcast_to_organization(self, organization_id: str, message: dict, exclude_user: str = None):
        """Broadcast message to all users in organization"""
        disconnected_users = []
        
        for user_id, websocket in self.active_connections.items():
            if (self.user_organizations.get(user_id) == organization_id and 
                user_id != exclude_user):
                try:
                    await websocket.send_text(json.dumps(message, default=str))
                except Exception as e:
                    logger.error(f"Error broadcasting to {user_id}: {e}")
                    disconnected_users.append(user_id)
        
        # Clean up disconnected users
        for user_id in disconnected_users:
            self.disconnect(user_id)
    
    async def broadcast_to_conversation(self, conversation_participants: List[str], message: dict, exclude_user: str = None):
        """Broadcast message to conversation participants"""
        disconnected_users = []
        
        for user_id in conversation_participants:
            if user_id != exclude_user and user_id in self.active_connections:
                websocket = self.active_connections[user_id]
                try:
                    await websocket.send_text(json.dumps(message, default=str))
                except Exception as e:
                    logger.error(f"Error sending to conversation participant {user_id}: {e}")
                    disconnected_users.append(user_id)
        
        # Clean up disconnected users
        for user_id in disconnected_users:
            self.disconnect(user_id)
    
    def set_typing_status(self, conversation_id: str, user_id: str, is_typing: bool):
        """Set typing status for user in conversation"""
        if conversation_id not in self.typing_users:
            self.typing_users[conversation_id] = set()
            
        if is_typing:
            self.typing_users[conversation_id].add(user_id)
        else:
            self.typing_users[conversation_id].discard(user_id)
    
    def get_typing_users(self, conversation_id: str) -> List[str]:
        """Get list of users currently typing in conversation"""
        return list(self.typing_users.get(conversation_id, set()))
    
    def get_online_users(self, organization_id: str) -> List[str]:
        """Get list of online users in organization"""
        return [
            user_id for user_id, org_id in self.user_organizations.items() 
            if org_id == organization_id
        ]
    
    def is_user_online(self, user_id: str) -> bool:
        """Check if user is currently online"""
        return user_id in self.active_connections

# Global connection manager instance
connection_manager = ConnectionManager()