# TalkFiesta Backend - FastAPI

## Setup Instructions

### 1. Virtual Environment

The virtual environment has been created. To activate it:

**Windows (PowerShell):**

```powershell
.\venv\Scripts\Activate.ps1
```

**Windows (CMD):**

```cmd
.\venv\Scripts\activate.bat
```

### 2. Install Dependencies

The core packages are currently being installed. If the installation is still running, wait for it to complete.

If you need to install manually:

```powershell
# Activate virtual environment first
.\venv\Scripts\Activate.ps1

# Install core packages
pip install fastapi uvicorn python-multipart sqlalchemy python-jose passlib pydantic pydantic-settings python-dotenv httpx

# Install additional packages (optional, install as needed)
pip install alembic psycopg2-binary google-auth google-auth-oauthlib
pip install openai google-generativeai deepgram-sdk elevenlabs
pip install boto3 redis
```

### 3. Environment Variables

Create a `.env` file in the backend directory:

```env
# App
APP_NAME=TalkFiesta
DEBUG=True
API_V1_PREFIX=/api/v1

# Database
DATABASE_URL=postgresql://user:password@localhost:5432/talkfiesta

# Auth
JWT_SECRET_KEY=your-secret-key-here-change-in-production
JWT_ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=30
REFRESH_TOKEN_EXPIRE_DAYS=7

# Google OAuth
GOOGLE_CLIENT_ID=your-google-client-id
GOOGLE_CLIENT_SECRET=your-google-client-secret
GOOGLE_REDIRECT_URI=http://localhost:3000/auth/google/callback

# Email (Optional)
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=your-email@gmail.com
SMTP_PASSWORD=your-app-password
EMAILS_FROM_EMAIL=noreply@talkfiesta.com
EMAILS_FROM_NAME=TalkFiesta

# AI Services (Optional - add when needed)
OPENAI_API_KEY=
GEMINI_API_KEY=
DEEPGRAM_API_KEY=
ELEVENLABS_API_KEY=

# Storage (Optional - add when needed)
AWS_ACCESS_KEY_ID=
AWS_SECRET_ACCESS_KEY=
AWS_S3_BUCKET=
AWS_REGION=us-east-1

# Redis (Optional)
REDIS_URL=redis://localhost:6379

# CORS
ALLOWED_ORIGINS=["http://localhost:3000"]
```

### 4. Run Development Server

```powershell
# Activate virtual environment
.\venv\Scripts\Activate.ps1

# Run server
uvicorn app.main:app --reload --port 8000
```

The API will be available at:

- API: http://localhost:8000
- Swagger Docs: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

## Project Structure

```
backend/
├── app/
│   ├── api/
│   │   └── v1/
│   │       └── endpoints/     # API endpoint files
│   ├── core/                  # Core utilities (security, config)
│   ├── db/                    # Database setup
│   ├── models/                # SQLAlchemy models
│   ├── schemas/               # Pydantic schemas
│   ├── services/              # Business logic
│   │   ├── ai/               # AI service integrations
│   │   └── storage/          # File storage services
│   ├── utils/                 # Utility functions
│   └── tests/                 # Test files
├── alembic/                   # Database migrations
│   └── versions/
├── scripts/                   # Utility scripts
├── venv/                      # Virtual environment
├── requirements.txt           # All dependencies
├── requirements-core.txt      # Core dependencies only
└── .env                       # Environment variables (create this)
```

## Next Steps

1. Wait for package installation to complete
2. Create `.env` file with your configuration
3. Set up PostgreSQL database
4. Create database models and migrations
5. Implement API endpoints
6. Test with Swagger UI at http://localhost:8000/docs

## Useful Commands

```powershell
# Check installed packages
pip list

# Install specific package
pip install package-name

# Freeze requirements
pip freeze > requirements.txt

# Run tests
pytest

# Format code
black app/

# Lint code
flake8 app/
```
