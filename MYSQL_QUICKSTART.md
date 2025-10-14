# MySQL Quick Start Guide

## 🚀 Get Started in 5 Steps

### Step 1: Create Database in MySQL Workbench
```sql
CREATE DATABASE missedtask
CHARACTER SET utf8mb4
COLLATE utf8mb4_unicode_ci;
```

### Step 2: Install Dependencies
```bash
pip install -r requirements.txt
```

### Step 3: Configure Database Connection
Create `.env` file:
```bash
DATABASE_URL=mysql+pymysql://root:YOUR_PASSWORD@localhost:3306/missedtask
SECRET_KEY=scope-secret-key-2024
```

**Replace `YOUR_PASSWORD` with your actual MySQL root password!**

### Step 4: Migrate Data
```bash
python -m api.migrate_json_to_db
```

Expected output:
```
Migrated 2 organizations
Migrated 4 users
Migrated 7 issues
Migrated 4 channels and 12 memberships
Migrated 19 conversations
Migrated 25 messages
✅ Migration completed successfully!
```

### Step 5: Start Server
```bash
uvicorn api.main:app --reload --port 8000
```

## ✅ Verify It Works

### In MySQL Workbench:
```sql
USE missedtask;
SHOW TABLES;

SELECT COUNT(*) as user_count FROM users;
SELECT COUNT(*) as issue_count FROM issues;
```

### In Browser or cURL:
```bash
# Health check
curl http://localhost:8000/health

# Get users
curl http://localhost:8000/api/users
```

## 🎯 Common Commands

### View Data in MySQL Workbench
```sql
USE missedtask;

-- All users
SELECT * FROM users;

-- All issues
SELECT * FROM issues;

-- Issues with assignees
SELECT i.key, i.title, i.status, u.name as assignee
FROM issues i
LEFT JOIN users u ON i.assignee_id = u.id;
```

### Connection String Format
```
mysql+pymysql://username:password@host:port/database
```

Examples:
```bash
# Local with root
DATABASE_URL=mysql+pymysql://root:mypassword@localhost:3306/missedtask

# Local with custom user
DATABASE_URL=mysql+pymysql://missedtask_user:secure123@localhost:3306/missedtask

# Remote server
DATABASE_URL=mysql+pymysql://user:pass@192.168.1.100:3306/missedtask
```

## 🔧 Troubleshooting

### Can't connect to database?
1. Check MySQL is running (MySQL Workbench → Connect)
2. Verify password in `.env` matches MySQL password
3. Verify port is 3306: `SHOW VARIABLES LIKE 'port';`

### Database doesn't exist?
```sql
CREATE DATABASE missedtask
CHARACTER SET utf8mb4
COLLATE utf8mb4_unicode_ci;
```

### Migration fails?
1. Drop and recreate database:
   ```sql
   DROP DATABASE missedtask;
   CREATE DATABASE missedtask CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
   ```
2. Run migration again:
   ```bash
   python -m api.migrate_json_to_db
   ```

## 📊 View Your Data

### Organizations
```sql
SELECT * FROM organizations;
```

### Users with Organizations
```sql
SELECT u.name, u.email, u.role, o.name as org_name
FROM users u
JOIN organizations o ON u.organization_id = o.id;
```

### Issues by Status
```sql
SELECT status, COUNT(*) as count
FROM issues
GROUP BY status;
```

### Channel Members
```sql
SELECT c.name as channel, u.name as member, cm.role
FROM channel_memberships cm
JOIN channels c ON cm.channel_id = c.id
JOIN users u ON cm.user_id = u.id;
```

## 🐳 Using Docker with MySQL

Start with Docker:
```bash
docker-compose -f docker-compose.mysql.yml up -d
```

Stop:
```bash
docker-compose -f docker-compose.mysql.yml down
```

## 📚 Full Documentation

For detailed setup, troubleshooting, and advanced features:
- **[MYSQL_SETUP.md](MYSQL_SETUP.md)** - Complete MySQL guide

---

**That's it! Your application is now using MySQL!** 🎉

Access API at: http://localhost:8000
View data in: MySQL Workbench
