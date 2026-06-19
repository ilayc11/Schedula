from fastapi import FastAPI
from fastapi.responses import PlainTextResponse
import uvicorn
import asyncio
import logging
from contextlib import asynccontextmanager

from src.database.database import db
from src.rabbitmq.rabbitmq import rabbitmq
from src.config import settings
from src.routes import db as db_router
from src.routes import rabbitmq as rabbitmq_router
from src.routes import ws as ws_router
from src.middleware.logging import LoggingMiddleware
from src.middleware.auth import AuthenticationMiddleware
from src.routes.external.lecturer import lecturer_router
from src.routes.external import auth
from src.routes.external.secretary import secretary_router
from src.routes import webhooks as webhooks_router
from src.rabbitmq.consumer import start_consumer
from src.scheduler import start_scheduler, stop_scheduler
from fastapi.middleware.cors import CORSMiddleware
# Disable FastAPI and uvicorn default logging
logging.getLogger("uvicorn").setLevel(logging.WARNING)
logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
logging.getLogger("fastapi").setLevel(logging.WARNING)

@asynccontextmanager
async def lifespan(app: FastAPI):
    await db.connect()
    await rabbitmq.connect()
    
    # Start the consumer for solver responses as a background task
    consumer_task = asyncio.create_task(start_consumer())
    
    # Start the scheduler for automated tasks (nightly solver runs, etc.)
    start_scheduler()
    
    try:
        yield
    finally:
        # Stop the scheduler
        stop_scheduler()
        
        # Cancel the consumer task on shutdown
        consumer_task.cancel()
        try:
            await consumer_task
        except asyncio.CancelledError:
            pass
        
        await rabbitmq.disconnect()
        await db.disconnect()


app = FastAPI(title=settings.app_name, docs_url="/docs", redoc_url="/redoc", lifespan=lifespan)

app.include_router(db_router.router)
app.include_router(auth.router)
app.include_router(lecturer_router)
app.include_router(secretary_router)
app.include_router(ws_router.router)
app.include_router(webhooks_router.router)

app.include_router(rabbitmq_router.router)

# Add authentication middleware (processes requests before endpoints)
app.add_middleware(AuthenticationMiddleware)
# Add logging middleware (processes requests after authentication)
app.add_middleware(LoggingMiddleware)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include dev routes if enabled (DEV ONLY - DO NOT USE IN PRODUCTION)
if settings.enable_dev_routes:
    from src.routes.dev_routes import dev_router
    app.include_router(dev_router)
    print("⚠️  DEV ROUTES ENABLED - DO NOT USE IN PRODUCTION ⚠️")


@app.get(
    "/health",
    response_class=PlainTextResponse,
    responses={
        200: {
            "description": "Application is healthy",
            "content": {"text/plain": {"example": "OK"}},
        }
    },
)
async def health():
    return "OK"

def main():
    uvicorn.run(
        "src.main:app",
        host="0.0.0.0",
        port=8000,
        reload=False,
        log_config=None,  # Disable uvicorn's default logging
        access_log=False,  # Disable access logging
    )


if __name__ == "__main__":
    main()
