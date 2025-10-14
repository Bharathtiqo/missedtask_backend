# Database Migration Guide

This document explains how to migrate your data from JSON files to a database.

## Overview

The application has been upgraded to use a database (PostgreSQL or SQLite) instead of JSON files for data persistence. This provides:

- ✅ Better performance
- ✅ ACID compliance
- ✅ Concurrent access support
- ✅ Referential integrity
- ✅ Query optimization
- ✅ Production-ready scalability

## Architecture Changes

### Before (JSON)
```
api/data/
├── users.json
├── organizations.json
├── issues.json
├── channels.json
├── conversations.json
└── conversation_messages.json
```

### After (Database)
```
Database Tables:
├── organizations
├── users
├── issues
├── channels
├── channel_memberships
├── conversations
└── conversation_messages
```

## New Files Added

1. **[api/models.py](api/models.py)** - SQLAlchemy ORM models
2. **[api/database.py](api/database.py)** - Database configuration and session management
3. **[api/migrate_json_to_db.py](api/migrate_json_to_db.py)** - Migration script
4. **[.env.example](.env.example)** - Environment variables template

## Migration Steps

### Step 1: Install Dependencies

```bash
pip install -r requirements.txt
```

New dependencies added:
- `sqlalchemy==2.0.23` - ORM framework
- `psycopg2-binary==2.9.9` - PostgreSQL adapter
- `alembic==1.13.0` - Database migrations tool

### Step 2: Configure Environment

Create a `.env` file from the template:

```bash
cp .env.example .env
```

Edit `.env` and set your database URL:

**For local development (SQLite):**
```bash
DATABASE_URL=sqlite:///./missedtask.db
```

**For PostgreSQL:**
```bash
DATABASE_URL=postgresql://username:password@localhost:5432/missedtask
```

### Step 3: Run Migration

```bash
python -m api.migrate_json_to_db
```

**Expected Output:**
```
==================================================
Starting JSON to Database Migration
==================================================
Data directory: g:\Bharath\MissedTask-backend\api\data
Initializing database...
Database initialized

Migrating organizations...
Migrated 2 organizations
Migrating users...
Migrated 4 users
Migrating issues...
Migrated 7 issues
Migrating channels...
Migrated 4 channels and 12 memberships
Migrating conversations...
Migrated 19 conversations
Migrating messages...
Migrated 25 messages

==================================================
Migration completed successfully!
==================================================
```

### Step 4: Verify Migration

Start the server:
```bash
uvicorn api.main:app --reload
```

Check the data:
```bash
# Health check
curl http://localhost:8000/health

# Check users
curl http://localhost:8000/api/users

# Check issues
curl http://localhost:8000/api/issues
```

## Database Schema

### Organizations
- `id` (PK)
- `name`
- `domain`
- `settings` (JSON)
- `created_at`

### Users
- `id` (PK)
- `email` (unique, indexed)
- `name`
- `role` (enum)
- `organization_id` (FK → organizations)
- `avatar`
- `is_active`
- `password_hash`
- `created_at`
- `profile_picture`

### Issues
- `id` (PK)
- `key` (unique, indexed)
- `title`
- `description`
- `issue_type` (enum)
- `status` (enum)
- `priority` (enum)
- `story_points`
- `assignee_id` (FK → users)
- `reporter_id` (FK → users)
- `organization_id` (FK → organizations)
- `labels` (JSON array)
- `visibility`
- `created_at`
- `updated_at`
- `due_date`
- `epic_id`
- `sprint_id`

### Channels
- `id` (PK)
- `name`
- `description`
- `organization_id` (FK → organizations)
- `is_private`
- `created_at`
- `created_by`

### Channel Memberships
- `id` (PK)
- `channel_id` (FK → channels)
- `user_id` (FK → users)
- `joined_at`
- `role`

### Conversations
- `id` (PK)
- `channel_id` (FK → channels)
- `organization_id` (FK → organizations)
- `title`
- `created_at`
- `updated_at`
- `is_active`

### Conversation Messages
- `id` (PK)
- `conversation_id` (FK → conversations)
- `sender_id` (FK → users)
- `content`
- `message_type`
- `created_at`
- `edited_at`
- `is_edited`
- `metadata` (JSON)

## Relationships

```
Organization
├── has many Users
├── has many Issues
├── has many Channels
└── has many Conversations

User
├── belongs to Organization
├── has many assigned Issues (as assignee)
├── has many reported Issues (as reporter)
├── has many ChannelMemberships
└── sends many Messages

Issue
├── belongs to Organization
├── has one assignee (User)
└── has one reporter (User)

Channel
├── belongs to Organization
├── has many ChannelMemberships
└── has many Conversations

Conversation
├── belongs to Channel
├── belongs to Organization
└── has many Messages

Message
├── belongs to Conversation
└── belongs to User (sender)
```

## Migration Script Details

The migration script ([api/migrate_json_to_db.py](api/migrate_json_to_db.py)):

1. **Reads JSON files** from `api/data/` directory
2. **Creates database tables** if they don't exist
3. **Migrates data in order** (respecting foreign key dependencies):
   - Organizations first (no dependencies)
   - Users (depend on organizations)
   - Issues (depend on organizations and users)
   - Channels (depend on organizations)
   - Conversations (depend on channels and organizations)
   - Messages (depend on conversations and users)
4. **Handles duplicates** gracefully (skips existing records)
5. **Preserves timestamps** from JSON data
6. **Maintains relationships** via foreign keys

## Rollback

If you need to rollback to JSON files:

1. **Keep your JSON files** - Don't delete them!
2. **The old code** is still in git history
3. **Restore from backup** if needed

```bash
# Backup current database
pg_dump $DATABASE_URL > backup.sql

# Revert to JSON-based code (if needed)
git checkout <previous-commit>
```

## Testing

### Run with SQLite (easiest)

```bash
DATABASE_URL=sqlite:///./test.db python -m api.migrate_json_to_db
DATABASE_URL=sqlite:///./test.db uvicorn api.main:app --reload
```

### Run with PostgreSQL (local)

```bash
# Start PostgreSQL
docker run --name postgres -e POSTGRES_PASSWORD=password -p 5432:5432 -d postgres:15

# Create database
docker exec -it postgres psql -U postgres -c "CREATE DATABASE missedtask;"

# Migrate
DATABASE_URL=postgresql://postgres:password@localhost:5432/missedtask python -m api.migrate_json_to_db

# Start server
DATABASE_URL=postgresql://postgres:password@localhost:5432/missedtask uvicorn api.main:app --reload
```

## Troubleshooting

### Issue: "ModuleNotFoundError: No module named 'api'"

**Solution:** Run from project root directory:
```bash
cd g:\Bharath\MissedTask-backend
python -m api.migrate_json_to_db
```

### Issue: "FileNotFoundError: api/data/users.json"

**Solution:** Ensure you're running from the project root and JSON files exist:
```bash
ls api/data/
```

### Issue: "IntegrityError: duplicate key value"

**Solution:** Data already exists. Migration is idempotent - it skips existing records.

### Issue: Database connection failed

**Solution:** Check your DATABASE_URL:
```bash
# Test connection
psql $DATABASE_URL

# Or for SQLite, check file permissions
ls -l missedtask.db
```

### Issue: "Foreign key constraint failed"

**Solution:** Migration order is important. The script handles this automatically. If manually migrating, follow the order: Organizations → Users → Issues → Channels → Conversations → Messages.

## Next Steps

After successful migration:

1. ✅ **Test all endpoints** to ensure data integrity
2. ✅ **Backup your database** regularly
3. ✅ **Keep JSON files** as backup (for now)
4. ✅ **Update API code** to use database instead of JSON (if needed)
5. ✅ **Deploy to production** following [DEPLOYMENT.md](DEPLOYMENT.md)

## Performance Comparison

| Operation | JSON Files | Database (SQLite) | Database (PostgreSQL) |
|-----------|-----------|-------------------|----------------------|
| Read user | O(n) | O(log n) | O(log n) |
| Search issues | O(n) | O(log n) | O(log n) |
| Concurrent writes | ❌ Unsafe | ⚠️ Limited | ✅ Excellent |
| Referential integrity | ❌ Manual | ✅ Enforced | ✅ Enforced |
| Backup/Restore | ⚠️ Manual | ✅ pg_dump | ✅ pg_dump |
| Scalability | ❌ Poor | ⚠️ Medium | ✅ Excellent |

## FAQ

**Q: Can I still use JSON files?**
A: Yes, but not recommended. The database provides better performance and reliability.

**Q: Will this affect my existing data?**
A: No, the migration script reads from JSON and writes to database. Original JSON files remain untouched.

**Q: Can I run migration multiple times?**
A: Yes, the script is idempotent. It skips records that already exist.

**Q: Which database should I use?**
A:
- **SQLite:** Quick local development, single file, no server needed
- **PostgreSQL:** Production deployments, better performance, concurrent access

**Q: How do I add new fields to the schema?**
A: Update [api/models.py](api/models.py) and use Alembic for migrations:
```bash
alembic revision --autogenerate -m "Add new field"
alembic upgrade head
```

## Support

If you encounter issues:
1. Check this guide's troubleshooting section
2. Review migration script logs
3. Verify environment variables
4. Check database connectivity
5. Review [DEPLOYMENT.md](DEPLOYMENT.md) for platform-specific guides
