# Deployment Guide

This guide covers deploying the MissedTask Backend API to various platforms.

## Table of Contents
- [Prerequisites](#prerequisites)
- [Database Migration](#database-migration)
- [Local Development](#local-development)
- [Production Deployment](#production-deployment)
  - [Render](#deploy-to-render)
  - [Railway](#deploy-to-railway)
  - [Heroku](#deploy-to-heroku)
  - [Docker](#deploy-with-docker)

## Prerequisites

1. Python 3.10 or higher
2. PostgreSQL database (for production)
3. Git

## Database Migration

### Initial Setup

1. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

2. **Set up environment variables:**
   ```bash
   cp .env.example .env
   # Edit .env with your configuration
   ```

3. **Run migration from JSON to Database:**
   ```bash
   python -m api.migrate_json_to_db
   ```

This will:
- Create all database tables
- Migrate data from JSON files in `api/data/` to the database
- Organizations → Users → Issues → Channels → Conversations → Messages (in dependency order)

### Environment Variables

Required environment variables:

| Variable | Description | Example |
|----------|-------------|---------|
| `DATABASE_URL` | Database connection string | `postgresql://user:pass@localhost:5432/dbname` |
| `SECRET_KEY` | Application secret key | `your-secret-key-change-in-production` |

## Local Development

### Using SQLite (Quick Start)

```bash
# Use default SQLite database
export DATABASE_URL=sqlite:///./missedtask.db

# Run migration
python -m api.migrate_json_to_db

# Start server
uvicorn api.main:app --reload --port 8000
```

### Using Docker Compose (Recommended)

```bash
# Start all services (PostgreSQL + API)
docker-compose up -d

# View logs
docker-compose logs -f api

# Stop services
docker-compose down
```

This will:
- Start PostgreSQL database
- Build and run the API
- Automatically run migrations
- API available at http://localhost:8000

## Production Deployment

### Deploy to Render

Render provides free PostgreSQL databases and web services.

#### Method 1: Using render.yaml (Recommended)

1. **Push code to GitHub**

2. **Connect to Render:**
   - Go to https://render.com
   - Click "New" → "Blueprint"
   - Connect your GitHub repository
   - Render will automatically detect `render.yaml`

3. **Configuration:**
   - Database and web service will be created automatically
   - Environment variables are auto-configured
   - Migration runs automatically on deployment

#### Method 2: Manual Setup

1. **Create PostgreSQL Database:**
   - Dashboard → New → PostgreSQL
   - Choose free tier
   - Copy the "Internal Database URL"

2. **Create Web Service:**
   - Dashboard → New → Web Service
   - Connect your repository
   - Settings:
     - **Environment:** Python 3
     - **Build Command:** `pip install -r requirements.txt`
     - **Start Command:** `python -m api.migrate_json_to_db && uvicorn api.main:app --host 0.0.0.0 --port $PORT`

3. **Environment Variables:**
   - `DATABASE_URL`: Paste the internal database URL
   - `SECRET_KEY`: Generate a secure random key
   - `PYTHON_VERSION`: 3.10.0

4. **Deploy:**
   - Click "Create Web Service"
   - Wait for deployment to complete

#### Setting up CI/CD with Render

1. **Get Deploy Hook:**
   - Go to your web service settings
   - Copy the "Deploy Hook" URL

2. **Add to GitHub Secrets:**
   - Repository Settings → Secrets → Actions
   - Add secret: `RENDER_DEPLOY_HOOK` with the URL

3. **Automatic Deployment:**
   - Push to `main` branch triggers deployment via GitHub Actions

### Deploy to Railway

Railway offers simple deployment with PostgreSQL.

#### Quick Deploy

1. **Install Railway CLI:**
   ```bash
   npm install -g @railway/cli
   ```

2. **Login:**
   ```bash
   railway login
   ```

3. **Initialize Project:**
   ```bash
   railway init
   ```

4. **Add PostgreSQL:**
   ```bash
   railway add postgresql
   ```

5. **Deploy:**
   ```bash
   railway up
   ```

6. **Set Environment Variables:**
   ```bash
   railway variables set SECRET_KEY=your-secret-key-here
   ```

#### Using GitHub Integration

1. **Connect Repository:**
   - Go to https://railway.app
   - New Project → Deploy from GitHub
   - Select your repository

2. **Add Database:**
   - Click "New" → Database → PostgreSQL
   - Railway automatically sets `DATABASE_URL`

3. **Configure:**
   - Settings → Environment Variables
   - Add `SECRET_KEY`

4. **Deploy:**
   - Automatic deployment on push to main

#### CI/CD Setup

1. **Get Railway Token:**
   - Dashboard → Account Settings → Tokens
   - Create new token

2. **Add to GitHub Secrets:**
   - `RAILWAY_TOKEN`: Your Railway token

3. **Deployment:**
   - GitHub Actions automatically deploys on push

### Deploy to Heroku

1. **Install Heroku CLI:**
   ```bash
   npm install -g heroku
   ```

2. **Login:**
   ```bash
   heroku login
   ```

3. **Create App:**
   ```bash
   heroku create missedtask-api
   ```

4. **Add PostgreSQL:**
   ```bash
   heroku addons:create heroku-postgresql:mini
   ```

5. **Set Environment Variables:**
   ```bash
   heroku config:set SECRET_KEY=your-secret-key-here
   ```

6. **Create Procfile:**
   ```bash
   echo "web: python -m api.migrate_json_to_db && uvicorn api.main:app --host 0.0.0.0 --port \$PORT" > Procfile
   ```

7. **Deploy:**
   ```bash
   git push heroku main
   ```

### Deploy with Docker

#### Build and Run

```bash
# Build image
docker build -t missedtask-api .

# Run with SQLite
docker run -p 8000:8000 missedtask-api

# Run with PostgreSQL
docker run -p 8000:8000 \
  -e DATABASE_URL=postgresql://user:pass@host:5432/db \
  -e SECRET_KEY=your-secret-key \
  missedtask-api
```

#### Push to Container Registry

```bash
# GitHub Container Registry
docker tag missedtask-api ghcr.io/yourusername/missedtask-api:latest
docker push ghcr.io/yourusername/missedtask-api:latest

# Docker Hub
docker tag missedtask-api yourusername/missedtask-api:latest
docker push yourusername/missedtask-api:latest
```

## Post-Deployment

### Verify Deployment

1. **Health Check:**
   ```bash
   curl https://your-app-url.com/health
   ```

   Should return:
   ```json
   {
     "ok": true,
     "service": "Scope API",
     "version": "1.0.0",
     "timestamp": "2025-10-13T..."
   }
   ```

2. **Test API:**
   ```bash
   curl https://your-app-url.com/api/users
   ```

### Update Frontend

Update your frontend `.env` file with the deployed API URL:

```bash
REACT_APP_API_URL=https://your-app-url.com
REACT_APP_WS_URL=wss://your-app-url.com
```

## Troubleshooting

### Database Connection Issues

1. **Check DATABASE_URL format:**
   - PostgreSQL: `postgresql://user:password@host:port/database`
   - SQLite: `sqlite:///./database.db`

2. **Verify database is accessible:**
   ```bash
   psql $DATABASE_URL
   ```

### Migration Issues

1. **Check logs:**
   ```bash
   # Render
   View logs in dashboard

   # Railway
   railway logs

   # Docker
   docker logs container-name
   ```

2. **Manual migration:**
   ```bash
   # SSH into your server
   python -m api.migrate_json_to_db
   ```

### CORS Issues

If frontend can't connect:

1. **Check CORS configuration in** [api/main.py](api/main.py:59-75)
2. **Add your frontend URL to allowed origins**
3. **Redeploy**

## CI/CD Pipeline

The project includes a GitHub Actions workflow (`.github/workflows/ci-cd.yml`) that:

1. **Tests:** Runs linting and tests on every push/PR
2. **Builds:** Creates Docker image and pushes to GitHub Container Registry
3. **Deploys:** Automatically deploys to Render/Railway on main branch

### Setup GitHub Secrets

Add these secrets to your repository:

- `RENDER_DEPLOY_HOOK`: Render deploy hook URL (optional)
- `RAILWAY_TOKEN`: Railway API token (optional)

## Monitoring

### Logs

- **Render:** Dashboard → Logs tab
- **Railway:** `railway logs` or Dashboard
- **Heroku:** `heroku logs --tail`
- **Docker:** `docker logs -f container-name`

### Health Checks

All platforms support health checks:
- **Path:** `/health` or `/healthz`
- **Expected:** HTTP 200 with JSON response

## Backup

### Database Backup

```bash
# PostgreSQL
pg_dump $DATABASE_URL > backup.sql

# Restore
psql $DATABASE_URL < backup.sql
```

### JSON Backup

Your original JSON files in `api/data/` serve as backup. Keep them safe!

## Scaling

### Horizontal Scaling

Most platforms support auto-scaling:
- **Render:** Pro plan and above
- **Railway:** Automatic with usage-based pricing
- **Heroku:** Add more dynos

### Database Optimization

1. **Add indexes** for frequently queried fields
2. **Use connection pooling** (already configured in database.py)
3. **Upgrade database plan** as needed

## Support

For issues:
- Check logs first
- Review environment variables
- Verify database connectivity
- Check GitHub Actions for CI/CD failures

## Next Steps

1. ✅ Deploy to your chosen platform
2. ✅ Run database migration
3. ✅ Update frontend configuration
4. ✅ Test all endpoints
5. ✅ Set up monitoring
6. ✅ Configure domain (optional)
7. ✅ Set up SSL (usually automatic on platforms)
