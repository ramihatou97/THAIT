"""
NeuroscribeAI - Celery Application Configuration
Handles asynchronous task processing for extraction and summarization
"""

import logging
from celery import Celery
from app.config import settings

# Configure logging
logging.basicConfig(
    level=getattr(logging, settings.log_level),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Create Celery application
celery_app = Celery(
    "neuroscribe",
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend,
    include=[
        "app.tasks.extraction",
        "app.tasks.summarization",
        "app.tasks.validation",
        "app.tasks.graph_sync",
        "app.tasks.embeddings",
    ]
)

# Configure Celery
celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_time_limit=settings.task_time_limit,
    task_soft_time_limit=settings.task_soft_time_limit,
    worker_prefetch_multiplier=settings.worker_prefetch_multiplier,
    worker_max_tasks_per_child=1000,
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    result_expires=3600,
    task_always_eager=settings.celery_task_always_eager,
)

# Task routes (if needed in the future)
celery_app.conf.task_routes = {
    "app.tasks.extraction.*": {"queue": "extraction"},
    "app.tasks.summarization.*": {"queue": "summarization"},
    "app.tasks.validation.*": {"queue": "validation"},
    "app.tasks.graph_sync.*": {"queue": "graph"},
    "app.tasks.embeddings.*": {"queue": "embeddings"},
}

logger.info("Celery application configured successfully")
logger.info(f"Broker: {settings.celery_broker_url}")
logger.info(f"Backend: {settings.celery_result_backend}")

if __name__ == "__main__":
    celery_app.start()
