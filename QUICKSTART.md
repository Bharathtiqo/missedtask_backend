# Quick Start Guide

Get your MissedTask backend up and running in 5 minutes!

## Local Development (SQLite)

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Set up environment (uses SQLite by default)
cp .env.example .env

# 3. Migrate data from JSON to database
python -m api.migrate_json_to_db

# 4. Start the server
uvicorn api.main:app --reload --port 8000
```

✅ API running at http://localhost:8000

## Using Docker (PostgreSQL)

```bash
# Start everything with one command
docker-compose up -d

# View logs
docker-compose logs -f

# Stop
docker-compose down
```

✅ API running at http://localhost:8000
✅ PostgreSQL running on port 5432

## Deploy to Cloud (Render)

```bash
# 1. Push to GitHub
git add .
git commit -m "Initial commit"
git push origin main

# 2. Go to https://render.com
# 3. Click "New" → "Blueprint"
# 4. Connect your GitHub repo
# 5. Deploy!
```

✅ Automatic deployment with PostgreSQL database

## Verify Everything Works

```bash
# Health check
curl http://localhost:8000/health

# Get users
curl http://localhost:8000/api/users

# Get issues
curl http://localhost:8000/api/issues
```

## Next Steps

- 📖 Read [DATABASE_MIGRATION.md](DATABASE_MIGRATION.md) for migration details
- 🚀 Read [DEPLOYMENT.md](DEPLOYMENT.md) for production deployment
- 🔧 Configure your frontend to use the API URL

## Need Help?

- Check the logs: `docker-compose logs -f` or `uvicorn` output
- Verify `.env` configuration
- Ensure JSON files exist in `api/data/`
