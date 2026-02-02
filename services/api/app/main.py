## services/api/app/main.py

from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# --- Always load services/api/.env regardless of current working directory ---
ENV_PATH = Path(__file__).resolve().parents[1] / ".env"
load_dotenv(dotenv_path=ENV_PATH, override=False)

# IMPORTANT: import routers only AFTER env is loaded
from app.routers.admin_profile import router as admin_profile_router  # noqa: E402
from app.routers.admin_trust import router as admin_trust_router  # noqa: E402
from app.routers.auth import router as auth_router  # noqa: E402
from app.routers.health import router as health_router  # noqa: E402
from app.routers.match import router as match_router  # noqa: E402
from app.routers.matches import router as matches_router  # noqa: E402
from app.routers.onboarding import router as onboarding_router  # noqa: E402
from app.routers.onboarding_v1 import router as onboarding_v1_router
from app.routers.profile import router as profile_router  # noqa: E402
from app.routers.ready import router as ready_router  # noqa: E402
from app.routers.resume import router as resume_router  # noqa: E402
from app.routers.tailor import router as tailor_router  # noqa: E402
from app.routers.trust import router as trust_router  # noqa: E402
from app.routers.mjass import router as mjass_router
from app.routers.dashboard import router as dashboard_router

app = FastAPI(title="Winnow API", version="0.1.0")

# CORS for local dev (Next.js usually runs on 3000/3001)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://localhost:3001",
        "http://127.0.0.1:3000",
        "http://127.0.0.1:3001",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Routes
app.include_router(health_router)
app.include_router(ready_router)
app.include_router(auth_router)
app.include_router(onboarding_router)
app.include_router(onboarding_v1_router)
app.include_router(resume_router)
app.include_router(profile_router)
app.include_router(trust_router)
app.include_router(admin_trust_router)
app.include_router(admin_profile_router)
app.include_router(match_router)
app.include_router(matches_router)
app.include_router(tailor_router)
app.include_router(mjass_router)
app.include_router(dashboard_router)  # Dashboard metrics

