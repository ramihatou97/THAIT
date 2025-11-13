"""
NeuroscribeAI - Main FastAPI Application
Production-grade clinical summary generator for neurosurgical patients
"""

import logging
from typing import List, Optional
from datetime import datetime
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, UploadFile, File, Depends, status, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import uvicorn

from app.config import settings
from app.schemas import (
    AtomicClinicalFact, SummaryRequest, SummaryResponse,
    ValidationReport, ClinicalAlert
)
from app.modules.extraction import extract_clinical_facts, ner_models
from app.modules.temporal_reasoning import build_patient_timeline
from app.modules.clinical_rules import evaluate_clinical_rules
from app.modules.validation import validate_clinical_data
from app.modules.summarization import generate_clinical_summary

# Configure logging
logging.basicConfig(
    level=getattr(logging, settings.log_level),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


# =============================================================================
# Application Lifecycle
# =============================================================================

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan events"""
    # Startup
    logger.info("Starting NeuroscribeAI application...")
    logger.info(f"Environment: {settings.environment}")
    logger.info(f"LLM Provider: {settings.llm_provider}")

    # Load NER models
    try:
        logger.info("Loading NER models...")
        ner_models.load_models()
        logger.info("NER models loaded successfully")
    except Exception as e:
        logger.error(f"Failed to load NER models: {e}")

    yield

    # Shutdown
    logger.info("Shutting down NeuroscribeAI application...")


# =============================================================================
# FastAPI Application
# =============================================================================

app = FastAPI(
    title="NeuroscribeAI",
    description="Production-grade clinical summary generator for neurosurgical patients",
    version="1.0.0",
    lifespan=lifespan
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=settings.cors_allow_credentials,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
from app.routes import graph as graph_routes, search as search_routes
app.include_router(graph_routes.router)
app.include_router(search_routes.router)


# =============================================================================
# Health Check Endpoints
# =============================================================================

@app.get("/health", tags=["health"])
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "version": "1.0.0",
        "environment": settings.environment
    }


@app.get("/health/ready", tags=["health"])
async def readiness_check():
    """Readiness check endpoint"""
    # Check if NER models are loaded
    models_ready = ner_models.loaded

    if not models_ready:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="NER models not loaded"
        )

    return {
        "status": "ready",
        "models_loaded": models_ready,
        "timestamp": datetime.now().isoformat()
    }


# =============================================================================
# Extraction Endpoints
# =============================================================================

@app.post("/api/v1/extract", response_model=List[AtomicClinicalFact], tags=["extraction"])
async def extract_facts(
    text: str,
    patient_id: int,
    document_id: int,
    use_cache: bool = Query(True, description="Use cached results if available")
):
    """
    Extract clinical facts from text with optional caching

    Args:
        text: Clinical text to extract from
        patient_id: Patient ID
        document_id: Document ID
        use_cache: Whether to use cached results (default: True)

    Returns:
        List of extracted atomic clinical facts
    """
    try:
        logger.info(f"Extracting facts for patient {patient_id}, document {document_id}")

        # Try cache first
        if use_cache:
            from app.services.cache_service import get_cached_facts, cache_facts
            cached = get_cached_facts(document_id)

            if cached:
                # Convert cached dicts back to AtomicClinicalFact objects
                facts = [AtomicClinicalFact(**f) for f in cached]
                logger.info(f"✓ Cache HIT: Returning {len(facts)} cached facts")
                return facts

        # Cache miss or cache disabled - perform extraction
        facts = extract_clinical_facts(text, patient_id, document_id)
        logger.info(f"Extracted {len(facts)} facts")

        # Cache results for future requests
        if use_cache:
            from app.services.cache_service import cache_facts
            cache_facts(document_id, facts)

        return facts

    except Exception as e:
        logger.error(f"Error in extraction: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Extraction failed: {str(e)}"
        )


@app.post("/api/v1/extract/file", response_model=List[AtomicClinicalFact], tags=["extraction"])
async def extract_from_file(
    file: UploadFile = File(...),
    patient_id: int = 1,
    document_id: int = 1
):
    """
    Extract clinical facts from uploaded file

    Args:
        file: Uploaded text file
        patient_id: Patient ID
        document_id: Document ID

    Returns:
        List of extracted atomic clinical facts
    """
    try:
        # Read file content
        content = await file.read()
        text = content.decode('utf-8')

        logger.info(f"Extracting from file: {file.filename} ({len(text)} chars)")

        # Extract facts
        facts = extract_clinical_facts(text, patient_id, document_id)

        logger.info(f"Extracted {len(facts)} facts from file")

        return facts

    except UnicodeDecodeError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="File must be UTF-8 encoded text"
        )
    except Exception as e:
        logger.error(f"Error extracting from file: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"File extraction failed: {str(e)}"
        )


# =============================================================================
# Validation Endpoints
# =============================================================================

@app.post("/api/v1/validate", response_model=ValidationReport, tags=["validation"])
async def validate_facts(
    facts: List[AtomicClinicalFact],
    source_text: str,
    patient_id: int
):
    """
    Validate extracted clinical facts

    Args:
        facts: List of clinical facts to validate
        source_text: Original source document text
        patient_id: Patient ID

    Returns:
        Comprehensive validation report
    """
    try:
        logger.info(f"Validating {len(facts)} facts for patient {patient_id}")

        validation_report = validate_clinical_data(facts, source_text, patient_id)

        logger.info(
            f"Validation complete: Score {validation_report.overall_quality_score:.1f}%, "
            f"Safe: {validation_report.safe_for_clinical_use}"
        )

        return validation_report

    except Exception as e:
        logger.error(f"Error in validation: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Validation failed: {str(e)}"
        )


# =============================================================================
# Clinical Rules Endpoints
# =============================================================================

@app.post("/api/v1/rules/evaluate", response_model=List[ClinicalAlert], tags=["clinical_rules"])
async def evaluate_rules(
    facts: List[AtomicClinicalFact],
    patient_context: Optional[dict] = None
):
    """
    Evaluate clinical rules and generate alerts

    Args:
        facts: List of clinical facts
        patient_context: Optional patient context (POD, etc.)

    Returns:
        List of clinical alerts from triggered rules
    """
    try:
        logger.info(f"Evaluating clinical rules for {len(facts)} facts")

        alerts = evaluate_clinical_rules(facts, patient_context)

        logger.info(f"Generated {len(alerts)} clinical alerts")

        return alerts

    except Exception as e:
        logger.error(f"Error evaluating rules: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Rule evaluation failed: {str(e)}"
        )


# =============================================================================
# Temporal Reasoning Endpoints
# =============================================================================

@app.post("/api/v1/temporal/timeline", tags=["temporal"])
async def build_timeline(
    facts: List[AtomicClinicalFact],
    patient_id: int,
    anchor_date: Optional[datetime] = None
):
    """
    Build patient timeline from clinical facts

    Args:
        facts: List of clinical facts
        patient_id: Patient ID
        anchor_date: Optional anchor date (surgery/admission)

    Returns:
        Patient timeline summary
    """
    try:
        logger.info(f"Building timeline for patient {patient_id}")

        timeline = build_patient_timeline(facts, patient_id, anchor_date)

        summary = timeline.get_timeline_summary()

        logger.info(f"Timeline built: {summary['total_events']} events")

        return summary

    except Exception as e:
        logger.error(f"Error building timeline: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Timeline construction failed: {str(e)}"
        )


# =============================================================================
# Summarization Endpoints
# =============================================================================

@app.post("/api/v1/summarize", response_model=SummaryResponse, tags=["summarization"])
async def generate_summary(request: SummaryRequest):
    """
    Generate clinical summary from extracted facts

    The SummaryRequest should contain:
    - facts: List of clinical facts
    - alerts: Optional clinical alerts
    - patient_data: Optional patient demographic data
    - patient_context: Optional context (e.g., POD)

    Returns:
        Generated clinical summary
    """
    try:
        patient_id = request.patient_id or request.patient_mrn
        logger.info(f"Generating {request.summary_type} summary for patient {patient_id}")

        # Use embedded data from request
        summary = generate_clinical_summary(
            request=request,
            facts=request.facts,
            alerts=request.alerts,
            patient_data=request.patient_data
        )

        logger.info(f"Summary generated: {len(summary.sections)} sections")
        return summary

    except Exception as e:
        logger.error(f"Error generating summary: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Summary generation failed: {str(e)}"
        )


# =============================================================================
# Complete Pipeline Endpoint
# =============================================================================

@app.post("/api/v1/pipeline/complete", tags=["pipeline"])
async def complete_pipeline(
    text: str,
    patient_id: int,
    document_id: int,
    summary_type: str = "discharge_summary",
    patient_context: Optional[dict] = None,
    patient_data: Optional[dict] = None
):
    """
    Run complete extraction → validation → rules → summarization pipeline

    Args:
        text: Clinical text to process
        patient_id: Patient ID
        document_id: Document ID
        summary_type: Type of summary to generate
        patient_context: Optional patient context (POD, etc.)
        patient_data: Optional patient demographic data

    Returns:
        Complete pipeline results including summary, validation, and alerts
    """
    try:
        logger.info(f"Running complete pipeline for patient {patient_id}")

        # Step 1: Extraction
        logger.info("Step 1: Extracting clinical facts...")
        facts = extract_clinical_facts(text, patient_id, document_id)
        logger.info(f"Extracted {len(facts)} facts")

        # Step 2: Validation
        logger.info("Step 2: Validating extracted facts...")
        validation_report = validate_clinical_data(facts, text, patient_id)
        logger.info(f"Validation score: {validation_report.overall_quality_score:.1f}%")

        # Step 3: Clinical Rules
        logger.info("Step 3: Evaluating clinical rules...")
        alerts = evaluate_clinical_rules(facts, patient_context)
        logger.info(f"Generated {len(alerts)} alerts")

        # Step 4: Summarization
        logger.info("Step 4: Generating clinical summary...")

        # Ensure patient_data has MRN
        patient_data = patient_data or {}
        patient_data.setdefault("mrn", str(patient_id))

        # Build complete SummaryRequest with all aggregated data
        summary_request = SummaryRequest(
            patient_mrn=str(patient_id),
            patient_id=patient_id,
            summary_type=summary_type,
            format="markdown",
            include_alerts=True,
            include_timeline=True,
            facts=facts,  # Embed extracted facts
            alerts=alerts,  # Embed alerts
            patient_data=patient_data,  # Embed patient data
            patient_context=patient_context or {}  # Embed context
        )

        summary = generate_clinical_summary(
            request=summary_request,
            facts=facts,
            alerts=alerts,
            patient_data=patient_data
        )
        logger.info(f"Summary generated with {len(summary.sections)} sections")

        # Compile results
        results = {
            "summary": summary,
            "validation": validation_report,
            "alerts": alerts,
            "facts_extracted": len(facts),
            "safe_for_clinical_use": validation_report.safe_for_clinical_use,
            "requires_review": validation_report.requires_review,
            "pipeline_timestamp": datetime.now().isoformat()
        }

        logger.info("Complete pipeline finished successfully")

        return results

    except Exception as e:
        logger.error(f"Error in complete pipeline: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Pipeline failed: {str(e)}"
        )


# =============================================================================
# Error Handlers
# =============================================================================

@app.exception_handler(HTTPException)
async def http_exception_handler(request, exc):
    """Handle HTTP exceptions"""
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": exc.detail,
            "timestamp": datetime.now().isoformat()
        }
    )


@app.exception_handler(Exception)
async def general_exception_handler(request, exc):
    """Handle general exceptions"""
    logger.error(f"Unhandled exception: {exc}", exc_info=True)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "error": "Internal server error",
            "detail": str(exc) if settings.debug else "An error occurred",
            "timestamp": datetime.now().isoformat()
        }
    )


# =============================================================================
# Main Entry Point
# =============================================================================

if __name__ == "__main__":
    uvicorn.run(
        "app.main:app",
        host=settings.api_host,
        port=settings.api_port,
        reload=settings.api_reload,
        log_level=settings.log_level.lower()
    )
