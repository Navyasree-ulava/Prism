from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.admin import router as admin_router
from app.api.chat import router as chat_router
from app.api.health import router as health_router
from app.api.models import router as models_router

app = FastAPI(
    title="Prism LLM Gateway",
    description="OpenAI-compatible LLM routing gateway",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health_router)
app.include_router(models_router, prefix="/v1")
app.include_router(chat_router, prefix="/v1")
app.include_router(admin_router, prefix="/admin")
