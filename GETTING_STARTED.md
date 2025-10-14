# 🚀 Getting Started with Database & Deployment

## What's New?

Your application now has:
- 💾 **Database support** (PostgreSQL/SQLite instead of JSON files)
- 🐳 **Docker containerization** (easy deployment)
- 🔄 **CI/CD pipeline** (automatic testing & deployment)
- 📦 **Migration script** (transfer JSON → Database)

## Quick Start (3 Options)

### ⚡ Option 1: Local SQLite (Fastest)

Perfect for testing and development:

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Copy environment file
cp .env.example .env
# (Edit .env if needed - defaults to SQLite)

# 3. Migrate your JSON data to database
python -m api.migrate_json_to_db

# 4. Start the server
uvicorn api.main:app --reload --port 8000
```

**Expected Output:**
```
Migrated 2 organizations
Migrated 4 users
Migrated 7 issues
Migrated 4 channels and 12 memberships
Migrated 19 conversations
Migrated 25 messages
✅ Migration completed successfully!
```

**Test it:**
```bash
curl http://localhost:8000/health
# Should return: {"ok": true, "service": "Scope API", ...}
```

---

### 🐳 Option 2: Docker (Most Production-Like)

Use PostgreSQL in containers:

```bash
# One command to start everything!
docker-compose up -d

# View logs
docker-compose logs -f api

# Stop when done
docker-compose down
```

**What it does:**
- ✅ Starts PostgreSQL database
- ✅ Builds API container
- ✅ Runs migration automatically
- ✅ Starts API server

**API available at:** http://localhost:8000

---

### ☁️ Option 3: Deploy to Cloud (Production)

#### Render (Recommended - Free Tier Available)

1. **Push to GitHub:**
   ```bash
   git add .
   git commit -m "Add database and CI/CD"
   git push origin main
   ```

2. **Deploy on Render:**
   - Go to https://render.com
   - Click "New" → "Blueprint"
   - Connect your GitHub repository
   - Render detects `render.yaml` automatically
   - Click "Apply" and wait ~5 minutes

3. **Done!** Your API is live with PostgreSQL database

#### Railway (Alternative - Also Free Tier)

```bash
# Install Railway CLI
npm install -g @railway/cli

# Login and deploy
railway login
railway init
railway add postgresql
railway up
```

---

## 📋 Files Created

Here's what was added to your project:

### Core Database Files
- `api/models.py` - Database models (SQLAlchemy ORM)
- `api/database.py` - Database connection & configuration
- `api/migrate_json_to_db.py` - JSON → Database migration script

### Docker Files
- `Dockerfile` - Container definition
- `docker-compose.yml` - Multi-container setup (PostgreSQL + API)
- `.dockerignore` - Optimize Docker builds

### Deployment Files
- `render.yaml` - Render platform configuration
- `railway.json` - Railway platform configuration
- `Procfile` - Heroku deployment
- `.github/workflows/ci-cd.yml` - GitHub Actions CI/CD

### Documentation
- `QUICKSTART.md` - 5-minute quick start
- `DATABASE_MIGRATION.md` - Detailed migration guide
- `DEPLOYMENT.md` - Complete deployment guide
- `SETUP_SUMMARY.md` - Technical summary
- `GETTING_STARTED.md` - This file!

### Updated Files
- `requirements.txt` - Added SQLAlchemy, psycopg2, alembic
- `.env.example` - Environment variable template
- `api/main.py` - Added `/health` endpoint

### Tests
- `tests/test_health.py` - Basic health check tests

---

## 🗄️ Database Schema

Your data structure:

```
Organizations (2 records)
 ├── Users (4 records)
 ├── Issues (7 records)
 ├── Channels (4 records)
 │    └── Memberships (12 records)
 └── Conversations (19 records)
      └── Messages (25 records)
```

**All relationships preserved!** Foreign keys ensure data integrity.

---

## 🔐 Environment Variables

Create a `.env` file (copy from `.env.example`):

### For Local Development (SQLite)
```bash
DATABASE_URL=sqlite:///./missedtask.db
SECRET_KEY=scope-secret-key-2024-change-in-production
```

### For Production (PostgreSQL)
```bash
DATABASE_URL=postgresql://username:password@host:5432/database
SECRET_KEY=generate-a-secure-random-key-here
```

**Note:** Cloud platforms (Render, Railway) provide `DATABASE_URL` automatically!

---

## ✅ Verify Everything Works

### 1. Check Health
```bash
curl http://localhost:8000/health
```

**Expected response:**
```json
{
  "ok": true,
  "service": "Scope API",
  "version": "1.0.0",
  "timestamp": "2025-10-13T..."
}
```

### 2. Check Users
```bash
curl http://localhost:8000/api/users
```

Should return all 4 users from your JSON data.

### 3. Check Issues
```bash
curl http://localhost:8000/api/issues
```

Should return all 7 issues.

---

## 🔄 CI/CD Pipeline

Your GitHub Actions workflow automatically:

1. **On every push/PR:**
   - ✅ Runs linting (flake8)
   - ✅ Runs tests (pytest)
   - ✅ Reports coverage

2. **On push to main:**
   - ✅ Builds Docker image
   - ✅ Pushes to GitHub Container Registry
   - ✅ Triggers deployment to Render/Railway

### Set Up Automatic Deployment

Add these secrets to your GitHub repository:

**Settings → Secrets → Actions → New repository secret**

- `RENDER_DEPLOY_HOOK` - Get from Render dashboard → Settings → Deploy Hook
- `RAILWAY_TOKEN` - Get from Railway dashboard → Account Settings → Tokens

---

## 🎯 Next Steps

### 1. Test Locally ✅
```bash
python -m api.migrate_json_to_db
uvicorn api.main:app --reload
```

### 2. Commit Changes ✅
```bash
git add .
git commit -m "Add database support and CI/CD pipeline"
git push origin main
```

### 3. Deploy to Cloud ✅
Choose your platform:
- **Render:** Follow steps in [DEPLOYMENT.md](DEPLOYMENT.md#deploy-to-render)
- **Railway:** Follow steps in [DEPLOYMENT.md](DEPLOYMENT.md#deploy-to-railway)
- **Heroku:** Follow steps in [DEPLOYMENT.md](DEPLOYMENT.md#deploy-to-heroku)

### 4. Update Frontend ✅
Edit your frontend `.env`:
```bash
REACT_APP_API_URL=https://your-api-url.com
REACT_APP_WS_URL=wss://your-api-url.com
```

---

## 🆘 Troubleshooting

### "ModuleNotFoundError: No module named 'api'"
**Solution:** Run from project root:
```bash
cd g:\Bharath\MissedTask-backend
python -m api.migrate_json_to_db
```

### "FileNotFoundError: api/data/users.json"
**Solution:** Ensure JSON files exist:
```bash
ls api/data/
# Should show: users.json, organizations.json, issues.json, etc.
```

### "Database connection failed"
**Solution:** Check your `.env` file:
```bash
cat .env
# Verify DATABASE_URL is correct
```

### Docker build fails
**Solution:** Rebuild without cache:
```bash
docker-compose build --no-cache
docker-compose up
```

### Migration runs but data not showing
**Solution:** Check database connection:
```bash
# For SQLite
ls -lh missedtask.db

# For PostgreSQL
psql $DATABASE_URL -c "SELECT count(*) FROM users;"
```

---

## 📚 Additional Resources

- **[QUICKSTART.md](QUICKSTART.md)** - Fastest way to get started
- **[DATABASE_MIGRATION.md](DATABASE_MIGRATION.md)** - Detailed migration guide, schema documentation
- **[DEPLOYMENT.md](DEPLOYMENT.md)** - Complete deployment instructions for all platforms
- **[SETUP_SUMMARY.md](SETUP_SUMMARY.md)** - Technical overview of all changes

---

## 🎉 You're All Set!

Your application now has:
- ✅ Production-ready database
- ✅ Docker containerization
- ✅ Automated CI/CD
- ✅ Multiple deployment options
- ✅ Complete documentation

**Choose your path and deploy!** 🚀

### Recommended Path
1. Test locally with SQLite (5 minutes)
2. Test with Docker (2 minutes)
3. Deploy to Render (10 minutes)
4. Set up CI/CD (5 minutes)

**Total time: ~20 minutes to production!**

---

## Need Help?

1. Check the troubleshooting section above
2. Review relevant documentation:
   - Migration issues → [DATABASE_MIGRATION.md](DATABASE_MIGRATION.md)
   - Deployment issues → [DEPLOYMENT.md](DEPLOYMENT.md)
3. Check logs:
   - Local: Check terminal output
   - Docker: `docker-compose logs -f`
   - Cloud: Check platform dashboard

---

**Ready to go? Start with Option 1 above!** ⚡
