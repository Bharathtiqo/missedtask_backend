"""
Migration script to transfer data from JSON files to database
Run this script once to migrate existing data
"""
import json
import os
import sys
from datetime import datetime
from sqlalchemy.exc import IntegrityError
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from api.database import init_db, get_db_sync
from api.models import (
    Organization, User, Issue, Channel, ChannelMembership,
    Conversation, ConversationMessage
)

def load_json_file(filepath):
    """Load JSON file and return data"""
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            return json.load(f)
    except FileNotFoundError:
        print(f"Warning: File not found: {filepath}")
        return None
    except json.JSONDecodeError as e:
        print(f"Error decoding JSON from {filepath}: {e}")
        return None

def parse_datetime(dt_string):
    """Parse datetime string to datetime object"""
    if not dt_string:
        return None
    try:
        return datetime.fromisoformat(dt_string.replace('Z', '+00:00'))
    except (ValueError, AttributeError):
        return None

def migrate_organizations(db, data_dir):
    """Migrate organizations from JSON to database"""
    print("Migrating organizations...")
    filepath = os.path.join(data_dir, 'organizations.json')
    data = load_json_file(filepath)

    if not data or 'organizations' not in data:
        print("No organizations data found")
        return

    count = 0
    skipped = 0
    for org_data in data['organizations']:
        try:
            org = Organization(
                id=org_data['id'],
                name=org_data['name'],
                domain=org_data.get('domain'),
                settings=org_data.get('settings', {}),
                created_at=parse_datetime(org_data.get('created_at')) or datetime.utcnow()
            )
            db.add(org)
            db.commit()  # Commit each organization individually
            count += 1
        except IntegrityError:
            print(f"Organization {org_data['name']} already exists, skipping...")
            db.rollback()
            skipped += 1

    print(f"Migrated {count} organizations, skipped {skipped} existing")

def migrate_users(db, data_dir):
    """Migrate users from JSON to database"""
    print("Migrating users...")
    filepath = os.path.join(data_dir, 'users.json')
    data = load_json_file(filepath)

    if not data or 'users' not in data:
        print("No users data found")
        return

    count = 0
    skipped = 0
    for user_data in data['users']:
        try:
            user = User(
                id=user_data['id'],
                email=user_data['email'],
                name=user_data['name'],
                role=user_data['role'],
                organization_id=user_data['organization_id'],
                avatar=user_data.get('avatar'),
                is_active=user_data.get('is_active', True),
                password_hash=user_data['password_hash'],
                created_at=parse_datetime(user_data.get('created_at')) or datetime.utcnow(),
                profile_picture=user_data.get('profile_picture')
            )
            db.add(user)
            db.commit()  # Commit each user individually
            count += 1
        except IntegrityError:
            print(f"User {user_data['email']} already exists, skipping...")
            db.rollback()
            skipped += 1

    print(f"Migrated {count} users, skipped {skipped} existing")

def migrate_issues(db, data_dir):
    """Migrate issues from JSON to database"""
    print("Migrating issues...")
    filepath = os.path.join(data_dir, 'issues.json')
    data = load_json_file(filepath)

    if not data or 'issues' not in data:
        print("No issues data found")
        return

    count = 0
    skipped = 0
    for issue_data in data['issues']:
        try:
            issue = Issue(
                id=issue_data['id'],
                key=issue_data['key'],
                title=issue_data['title'],
                description=issue_data.get('description'),
                issue_type=issue_data['issue_type'],
                status=issue_data['status'],
                priority=issue_data['priority'],
                story_points=issue_data.get('story_points'),
                assignee_id=issue_data.get('assignee_id'),
                reporter_id=issue_data['reporter_id'],
                organization_id=issue_data['organization_id'],
                labels=issue_data.get('labels', []),
                visibility=issue_data.get('visibility', 'team'),
                created_at=parse_datetime(issue_data.get('created_at')) or datetime.utcnow(),
                updated_at=parse_datetime(issue_data.get('updated_at')) or datetime.utcnow(),
                due_date=parse_datetime(issue_data.get('due_date')),
                epic_id=issue_data.get('epic_id'),
                sprint_id=issue_data.get('sprint_id')
            )
            db.add(issue)
            db.commit()  # Commit each issue individually
            count += 1
        except IntegrityError as e:
            print(f"Issue {issue_data['key']} (ID: {issue_data['id'][:8]}...) already exists, skipping...")
            db.rollback()
            skipped += 1

    print(f"Migrated {count} issues, skipped {skipped} duplicates")

def migrate_channels(db, data_dir):
    """Migrate channels from JSON to database"""
    print("Migrating channels...")
    filepath = os.path.join(data_dir, 'channels.json')
    data = load_json_file(filepath)

    if not data or 'channels' not in data:
        print("No channels data found")
        return

    count = 0
    membership_count = 0
    skipped = 0

    for channel_data in data['channels']:
        try:
            channel = Channel(
                id=channel_data['id'],
                name=channel_data['name'],
                description=channel_data.get('description'),
                organization_id=channel_data['organization_id'],
                is_private=channel_data.get('is_private', False),
                created_at=parse_datetime(channel_data.get('created_at')) or datetime.utcnow(),
                created_by=channel_data.get('created_by')
            )
            db.add(channel)
            db.flush()  # Flush to check for foreign key errors before adding memberships

            # Migrate channel memberships
            for member_data in channel_data.get('members', []):
                try:
                    if isinstance(member_data, dict):
                        membership = ChannelMembership(
                            id=member_data.get('id', f"{channel_data['id']}-{member_data['user_id']}"),
                            channel_id=channel_data['id'],
                            user_id=member_data['user_id'],
                            joined_at=parse_datetime(member_data.get('joined_at')) or datetime.utcnow(),
                            role=member_data.get('role', 'member')
                        )
                    else:
                        # Old format: just user_id string
                        membership = ChannelMembership(
                            id=f"{channel_data['id']}-{member_data}",
                            channel_id=channel_data['id'],
                            user_id=member_data,
                            joined_at=datetime.utcnow(),
                            role='member'
                        )
                    db.add(membership)
                    membership_count += 1
                except IntegrityError as e:
                    print(f"  Skipping membership for invalid user in channel {channel_data['name']}")
                    db.rollback()

            db.commit()
            count += 1

        except IntegrityError as e:
            error_msg = str(e)
            if 'foreign key constraint' in error_msg.lower():
                print(f"Channel '{channel_data['name']}' (org: {channel_data['organization_id'][:8]}...) references non-existent organization, skipping...")
            else:
                print(f"Channel {channel_data['name']} already exists, skipping...")
            db.rollback()
            skipped += 1

    print(f"Migrated {count} channels and {membership_count} memberships, skipped {skipped} invalid channels")

def migrate_conversations(db, data_dir):
    """Migrate conversations from JSON to database"""
    print("Migrating conversations...")
    filepath = os.path.join(data_dir, 'conversations.json')
    data = load_json_file(filepath)

    if not data or 'conversations' not in data:
        print("No conversations data found")
        return

    count = 0
    skipped = 0
    for conv_data in data['conversations']:
        try:
            # Skip if missing required fields
            if 'channel_id' not in conv_data or 'organization_id' not in conv_data:
                conv_id = conv_data.get('id', 'unknown')[:8] if 'id' in conv_data else 'unknown'
                print(f"Conversation {conv_id}... missing required fields, skipping...")
                skipped += 1
                continue

            conversation = Conversation(
                id=conv_data['id'],
                channel_id=conv_data['channel_id'],
                organization_id=conv_data['organization_id'],
                title=conv_data.get('title'),
                created_at=parse_datetime(conv_data.get('created_at')) or datetime.utcnow(),
                updated_at=parse_datetime(conv_data.get('updated_at')) or datetime.utcnow(),
                is_active=conv_data.get('is_active', True)
            )
            db.add(conversation)
            db.commit()
            count += 1
        except IntegrityError as e:
            error_msg = str(e)
            if 'foreign key constraint' in error_msg.lower():
                print(f"Conversation {conv_data.get('id', 'unknown')[:8]}... references non-existent channel/org, skipping...")
            else:
                print(f"Conversation {conv_data.get('id', 'unknown')[:8]}... already exists, skipping...")
            db.rollback()
            skipped += 1
        except KeyError as e:
            print(f"Conversation missing required field {e}, skipping...")
            skipped += 1

    print(f"Migrated {count} conversations, skipped {skipped} invalid")

def migrate_messages(db, data_dir):
    """Migrate conversation messages from JSON to database"""
    print("Migrating messages...")
    filepath = os.path.join(data_dir, 'conversation_messages.json')
    data = load_json_file(filepath)

    if not data or 'messages' not in data:
        print("No messages data found")
        return

    count = 0
    skipped = 0
    for msg_data in data['messages']:
        try:
            # Skip if missing required fields
            required_fields = ['id', 'conversation_id', 'sender_id', 'content']
            missing_fields = [f for f in required_fields if f not in msg_data]
            if missing_fields:
                msg_id = msg_data.get('id', 'unknown')[:8] if 'id' in msg_data else 'unknown'
                skipped += 1
                continue  # Silently skip - most messages are for non-existent conversations

            message = ConversationMessage(
                id=msg_data['id'],
                conversation_id=msg_data['conversation_id'],
                sender_id=msg_data['sender_id'],
                content=msg_data['content'],
                message_type=msg_data.get('message_type', 'text'),
                created_at=parse_datetime(msg_data.get('created_at')) or datetime.utcnow(),
                edited_at=parse_datetime(msg_data.get('edited_at')),
                is_edited=msg_data.get('is_edited', False),
                message_metadata=msg_data.get('metadata', {})
            )
            db.add(message)
            db.commit()
            count += 1
        except IntegrityError as e:
            error_msg = str(e)
            if 'foreign key constraint' in error_msg.lower():
                # Skip messages for conversations that weren't migrated - silently
                pass
            else:
                print(f"Message {msg_data.get('id', 'unknown')[:8]}... already exists, skipping...")
            db.rollback()
            skipped += 1
        except KeyError as e:
            # Skip silently
            skipped += 1

    print(f"Migrated {count} messages, skipped {skipped} invalid")

def main():
    """Main migration function"""
    print("=" * 50)
    print("Starting JSON to Database Migration")
    print("=" * 50)

    # Show database connection
    db_url = os.getenv("DATABASE_URL", "sqlite:///./missedtask.db")
    if "mysql" in db_url:
        db_type = "MySQL"
        # Mask password in display
        display_url = db_url.split("@")[1] if "@" in db_url else db_url
        print(f"Database: {db_type} ({display_url})")
    elif "postgresql" in db_url:
        db_type = "PostgreSQL"
        display_url = db_url.split("@")[1] if "@" in db_url else db_url
        print(f"Database: {db_type} ({display_url})")
    else:
        db_type = "SQLite"
        print(f"Database: {db_type} (missedtask.db)")
    print()

    # Get data directory
    base_dir = os.path.dirname(os.path.abspath(__file__))
    data_dir = os.path.join(base_dir, 'data')

    if not os.path.exists(data_dir):
        print(f"Error: Data directory not found: {data_dir}")
        sys.exit(1)

    print(f"Data directory: {data_dir}")
    print()

    # Initialize database
    print("Initializing database...")
    init_db()
    print("Database initialized")
    print()

    # Get database session
    db = get_db_sync()

    try:
        # Migrate in order of dependencies
        migrate_organizations(db, data_dir)
        migrate_users(db, data_dir)
        migrate_issues(db, data_dir)
        migrate_channels(db, data_dir)
        migrate_conversations(db, data_dir)
        migrate_messages(db, data_dir)

        print()
        print("=" * 50)
        print("Migration completed successfully!")
        print("=" * 50)

    except Exception as e:
        print(f"Error during migration: {e}")
        db.rollback()
        raise
    finally:
        db.close()

if __name__ == "__main__":
    main()
