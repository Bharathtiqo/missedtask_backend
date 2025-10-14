# MySQL Setup Guide with MySQL Workbench

This guide will help you set up your MissedTask backend with MySQL database using MySQL Workbench.

## Prerequisites

- ✅ MySQL Server installed
- ✅ MySQL Workbench installed
- ✅ Python 3.10+ installed

## Step-by-Step Setup

### Step 1: Create Database in MySQL Workbench

1. **Open MySQL Workbench**

2. **Connect to your MySQL Server:**
   - Click on your local MySQL connection (usually "Local instance 3306")
   - Enter your root password when prompted

3. **Create a new database:**

   Click on the SQL editor and run:
   ```sql
   CREATE DATABASE missedtask
   CHARACTER SET utf8mb4
   COLLATE utf8mb4_unicode_ci;
   ```

4. **Verify database was created:**
   ```sql
   SHOW DATABASES;
   ```

   You should see `missedtask` in the list.

5. **Create a dedicated user (Optional but Recommended):**
   ```sql
   CREATE USER 'missedtask_user'@'localhost' IDENTIFIED BY 'your_secure_password';
   GRANT ALL PRIVILEGES ON missedtask.* TO 'missedtask_user'@'localhost';
   FLUSH PRIVILEGES;
   ```

### Step 2: Install Python Dependencies

Open your terminal/command prompt:

```bash
cd g:\Bharath\MissedTask-backend
pip install -r requirements.txt
```

This will install:
- `pymysql` - MySQL database connector
- `cryptography` - Required for secure MySQL connections
- `sqlalchemy` - ORM framework
- All other dependencies

### Step 3: Configure Environment Variables

1. **Create `.env` file:**
   ```bash
   cp .env.example .env
   ```

2. **Edit `.env` file** and update the DATABASE_URL:

   **If using root user:**
   ```bash
   DATABASE_URL=mysql+pymysql://root:your_mysql_password@localhost:3306/missedtask
   ```

   **If using dedicated user:**
   ```bash
   DATABASE_URL=mysql+pymysql://missedtask_user:your_secure_password@localhost:3306/missedtask
   ```

   **Format explained:**
   ```
   mysql+pymysql://username:password@host:port/database_name
   ```

   - `mysql+pymysql` - Use PyMySQL driver
   - `username` - Your MySQL username (root or missedtask_user)
   - `password` - Your MySQL password
   - `localhost` - MySQL server host (change if remote)
   - `3306` - MySQL default port
   - `missedtask` - Database name

3. **Complete `.env` file example:**
   ```bash
   # Application Settings
   SECRET_KEY=scope-secret-key-2024-change-in-production

   # Database Configuration
   DATABASE_URL=mysql+pymysql://root:yourpassword@localhost:3306/missedtask

   # API Configuration
   API_PORT=8000

   # CORS Allowed Origins
   ALLOWED_ORIGINS=http://localhost:3000,http://127.0.0.1:3000,http://localhost:5173
   ```

### Step 4: Run Migration

This will transfer all data from JSON files to MySQL database:

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

### Step 5: Verify Data in MySQL Workbench

Back in MySQL Workbench, run these queries to verify:

```sql
-- Use the database
USE missedtask;

-- Show all tables
SHOW TABLES;

-- Check table counts
SELECT 'organizations' as table_name, COUNT(*) as count FROM organizations
UNION ALL
SELECT 'users', COUNT(*) FROM users
UNION ALL
SELECT 'issues', COUNT(*) FROM issues
UNION ALL
SELECT 'channels', COUNT(*) FROM channels
UNION ALL
SELECT 'channel_memberships', COUNT(*) FROM channel_memberships
UNION ALL
SELECT 'conversations', COUNT(*) FROM conversations
UNION ALL
SELECT 'conversation_messages', COUNT(*) FROM conversation_messages;

-- View sample data
SELECT * FROM users LIMIT 5;
SELECT * FROM issues LIMIT 5;
SELECT * FROM organizations;
```

**Expected table counts:**
- organizations: 2
- users: 4
- issues: 7
- channels: 4
- channel_memberships: 12
- conversations: 19
- conversation_messages: 25

### Step 6: Start the Server

```bash
uvicorn api.main:app --reload --port 8000
```

**Expected output:**
```
INFO:     Uvicorn running on http://127.0.0.1:8000 (Press CTRL+C to quit)
INFO:     Started reloader process
INFO:     Started server process
INFO:     Waiting for application startup.
INFO:     Application startup complete.
```

### Step 7: Test the API

Open a new terminal and test:

```bash
# Health check
curl http://localhost:8000/health

# Get all users
curl http://localhost:8000/api/users

# Get all issues
curl http://localhost:8000/api/issues
```

## Viewing Data in MySQL Workbench

### Method 1: Using SQL Queries

```sql
USE missedtask;

-- View all users with their organizations
SELECT
    u.id,
    u.name,
    u.email,
    u.role,
    o.name as organization_name
FROM users u
JOIN organizations o ON u.organization_id = o.id;

-- View all issues with assignee and reporter
SELECT
    i.key,
    i.title,
    i.status,
    i.priority,
    a.name as assignee,
    r.name as reporter
FROM issues i
LEFT JOIN users a ON i.assignee_id = a.id
JOIN users r ON i.reporter_id = r.id;

-- View channel memberships
SELECT
    c.name as channel_name,
    u.name as member_name,
    cm.role,
    cm.joined_at
FROM channel_memberships cm
JOIN channels c ON cm.channel_id = c.id
JOIN users u ON cm.user_id = u.id
ORDER BY c.name, u.name;

-- View conversations with message counts
SELECT
    conv.id,
    conv.title,
    c.name as channel_name,
    COUNT(m.id) as message_count,
    conv.created_at
FROM conversations conv
JOIN channels c ON conv.channel_id = c.id
LEFT JOIN conversation_messages m ON m.conversation_id = conv.id
GROUP BY conv.id, conv.title, c.name, conv.created_at;
```

### Method 2: Using Table Inspector

1. In MySQL Workbench, navigate to **Schemas** panel (left side)
2. Expand your `missedtask` database
3. Expand **Tables**
4. Right-click on any table → **Select Rows - Limit 1000**

### Method 3: Using ER Diagram

View relationships visually:

1. Database → Reverse Engineer
2. Select your connection and database
3. Click through the wizard
4. View the Entity-Relationship diagram

## Database Schema

### Tables Created

```
organizations
├── id (VARCHAR(36), PK)
├── name (VARCHAR(255))
├── domain (VARCHAR(255))
├── settings (JSON)
└── created_at (DATETIME)

users
├── id (VARCHAR(36), PK)
├── email (VARCHAR(255), UNIQUE)
├── name (VARCHAR(255))
├── role (ENUM)
├── organization_id (VARCHAR(36), FK)
├── avatar (VARCHAR(10))
├── is_active (BOOLEAN)
├── password_hash (VARCHAR(255))
├── created_at (DATETIME)
└── profile_picture (TEXT)

issues
├── id (VARCHAR(36), PK)
├── key (VARCHAR(50), UNIQUE)
├── title (VARCHAR(500))
├── description (TEXT)
├── issue_type (ENUM)
├── status (ENUM)
├── priority (ENUM)
├── story_points (INT)
├── assignee_id (VARCHAR(36), FK)
├── reporter_id (VARCHAR(36), FK)
├── organization_id (VARCHAR(36), FK)
├── labels (JSON)
├── visibility (VARCHAR(50))
├── created_at (DATETIME)
├── updated_at (DATETIME)
├── due_date (DATETIME)
├── epic_id (VARCHAR(36))
└── sprint_id (VARCHAR(36))

channels
├── id (VARCHAR(36), PK)
├── name (VARCHAR(255))
├── description (TEXT)
├── organization_id (VARCHAR(36), FK)
├── is_private (BOOLEAN)
├── created_at (DATETIME)
└── created_by (VARCHAR(36))

channel_memberships
├── id (VARCHAR(36), PK)
├── channel_id (VARCHAR(36), FK)
├── user_id (VARCHAR(36), FK)
├── joined_at (DATETIME)
└── role (VARCHAR(50))

conversations
├── id (VARCHAR(36), PK)
├── channel_id (VARCHAR(36), FK)
├── organization_id (VARCHAR(36), FK)
├── title (VARCHAR(500))
├── created_at (DATETIME)
├── updated_at (DATETIME)
└── is_active (BOOLEAN)

conversation_messages
├── id (VARCHAR(36), PK)
├── conversation_id (VARCHAR(36), FK)
├── sender_id (VARCHAR(36), FK)
├── content (TEXT)
├── message_type (VARCHAR(50))
├── created_at (DATETIME)
├── edited_at (DATETIME)
├── is_edited (BOOLEAN)
└── metadata (JSON)
```

## Troubleshooting

### Issue 1: "Access denied for user"

**Solution:** Check your username and password in `.env`:
```bash
# Verify MySQL credentials
mysql -u root -p
# Enter password when prompted
```

If login works, update your `.env` file with the correct credentials.

### Issue 2: "Unknown database 'missedtask'"

**Solution:** Create the database in MySQL Workbench:
```sql
CREATE DATABASE missedtask
CHARACTER SET utf8mb4
COLLATE utf8mb4_unicode_ci;
```

### Issue 3: "Can't connect to MySQL server"

**Solution:**
1. Verify MySQL is running:
   - Windows: Check Services → MySQL80 is running
   - Or open MySQL Workbench and try to connect

2. Check port number (default is 3306)
   ```sql
   SHOW VARIABLES LIKE 'port';
   ```

### Issue 4: "ModuleNotFoundError: No module named 'pymysql'"

**Solution:** Install dependencies:
```bash
pip install -r requirements.txt
```

### Issue 5: Migration fails with "Foreign key constraint"

**Solution:** The migration script handles dependencies automatically. If it fails:

1. Drop all tables and retry:
   ```sql
   DROP DATABASE missedtask;
   CREATE DATABASE missedtask
   CHARACTER SET utf8mb4
   COLLATE utf8mb4_unicode_ci;
   ```

2. Run migration again:
   ```bash
   python -m api.migrate_json_to_db
   ```

### Issue 6: "Authentication plugin 'caching_sha2_password' cannot be loaded"

**Solution:** Update user authentication method:
```sql
ALTER USER 'root'@'localhost' IDENTIFIED WITH mysql_native_password BY 'your_password';
FLUSH PRIVILEGES;
```

Or use a newer version of PyMySQL (already in requirements.txt).

## Useful MySQL Workbench Tips

### Export Data
1. Server → Data Export
2. Select `missedtask` database
3. Choose export location
4. Click "Start Export"

### Import Data
1. Server → Data Import
2. Select import file
3. Choose `missedtask` database
4. Click "Start Import"

### Backup Database
```bash
mysqldump -u root -p missedtask > backup.sql
```

### Restore Database
```bash
mysql -u root -p missedtask < backup.sql
```

### Monitor Performance
1. Performance → Dashboard
2. View query performance, connections, etc.

## Optimizing MySQL for Production

Add these to your MySQL configuration (my.cnf or my.ini):

```ini
[mysqld]
# Increase max connections
max_connections = 200

# Optimize InnoDB
innodb_buffer_pool_size = 1G
innodb_log_file_size = 256M
innodb_flush_log_at_trx_commit = 2

# Character set
character-set-server = utf8mb4
collation-server = utf8mb4_unicode_ci
```

Restart MySQL after changes.

## Next Steps

1. ✅ **Test locally:** Verify all endpoints work
2. ✅ **Add indexes:** Optimize queries
   ```sql
   CREATE INDEX idx_user_email ON users(email);
   CREATE INDEX idx_issue_key ON issues(key);
   CREATE INDEX idx_issue_status ON issues(status);
   ```
3. ✅ **Set up backups:** Schedule regular mysqldump
4. ✅ **Monitor performance:** Use MySQL Workbench Performance Dashboard
5. ✅ **Deploy:** Follow [DEPLOYMENT.md](DEPLOYMENT.md) for cloud deployment

## Switching Between Databases

You can easily switch between SQLite, MySQL, and PostgreSQL by changing the `DATABASE_URL` in `.env`:

```bash
# SQLite (for quick testing)
DATABASE_URL=sqlite:///./missedtask.db

# MySQL (for local development)
DATABASE_URL=mysql+pymysql://root:password@localhost:3306/missedtask

# PostgreSQL (for production)
DATABASE_URL=postgresql://user:password@localhost:5432/missedtask
```

Just restart your server after changing the database URL.

## Support

- **MySQL Documentation:** https://dev.mysql.com/doc/
- **MySQL Workbench Manual:** https://dev.mysql.com/doc/workbench/en/
- **SQLAlchemy MySQL:** https://docs.sqlalchemy.org/en/20/dialects/mysql.html

## Common MySQL Queries for MissedTask

```sql
-- Find all issues assigned to a specific user
SELECT * FROM issues WHERE assignee_id = 'user-id-here';

-- Get channel members
SELECT u.name, u.email, cm.role
FROM channel_memberships cm
JOIN users u ON cm.user_id = u.id
WHERE cm.channel_id = 'channel-id-here';

-- Get conversation messages
SELECT
    m.content,
    u.name as sender,
    m.created_at
FROM conversation_messages m
JOIN users u ON m.sender_id = u.id
WHERE m.conversation_id = 'conversation-id-here'
ORDER BY m.created_at;

-- Count issues by status
SELECT status, COUNT(*) as count
FROM issues
GROUP BY status;

-- Count issues by priority
SELECT priority, COUNT(*) as count
FROM issues
GROUP BY priority;
```

---

**You're all set with MySQL!** 🎉

Your data is now in MySQL database and you can manage it using MySQL Workbench.
