# Virtual Environment Setup

## Quick Fix for Your Issue

You're using a virtual environment from another project. Let's create a fresh one:

### Step 1: Create New Virtual Environment

```powershell
# In PowerShell (as you're using)
cd G:\Bharath\MissedTask-backend

# Create virtual environment
python -m venv venv
```

### Step 2: Activate Virtual Environment

```powershell
# Activate it
.\venv\Scripts\Activate.ps1
```

**If you get an execution policy error:**
```powershell
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
```

Then activate again:
```powershell
.\venv\Scripts\Activate.ps1
```

### Step 3: Upgrade pip

```powershell
python -m pip install --upgrade pip
```

### Step 4: Install Requirements

```powershell
pip install -r requirements.txt
```

### Step 5: Verify Installation

```powershell
pip list
```

You should see all packages including:
- fastapi
- uvicorn
- sqlalchemy
- pymysql
- etc.

---

## Alternative: Install Directly (Without Virtual Environment)

If you prefer not to use a virtual environment:

```powershell
# Upgrade pip first
python -m pip install --upgrade pip

# Install requirements
python -m pip install -r requirements.txt
```

---

## Next Steps

Once packages are installed, continue with MySQL setup:

```powershell
# 1. Create database in MySQL Workbench
# Run: CREATE DATABASE missedtask CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;

# 2. Create .env file
copy .env.example .env

# 3. Edit .env with your MySQL password
# DATABASE_URL=mysql+pymysql://root:YOUR_PASSWORD@localhost:3306/missedtask

# 4. Run migration
python -m api.migrate_json_to_db

# 5. Start server
uvicorn api.main:app --reload
```

---

## Troubleshooting

### PowerShell Execution Policy Error

If you see:
```
File cannot be loaded because running scripts is disabled on this system
```

**Solution:**
```powershell
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
```

### pip is Outdated

**Solution:**
```powershell
python -m pip install --upgrade pip setuptools wheel
```

### Still Getting Import Errors

**Solution:** Create a completely fresh environment:
```powershell
# Remove old venv if exists
Remove-Item -Recurse -Force venv

# Create fresh one
python -m venv venv

# Activate
.\venv\Scripts\Activate.ps1

# Upgrade pip
python -m pip install --upgrade pip

# Install
pip install -r requirements.txt
```
