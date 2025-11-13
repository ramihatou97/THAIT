"""
NeuroscribeAI - Knowledge Graph API Routes
Endpoints for querying clinical knowledge graph
"""

import logging
from typing import List, Dict, Optional, Any
from fastapi import APIRouter, HTTPException, Query, status

from app.services.neo4j_service import neo4j_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/graph", tags=["Knowledge Graph"])


@router.get("/health")
async def graph_health():
    """Check Neo4j graph database health"""
    try:
        healthy = neo4j_service.connection.health_check()
        if healthy:
            return {"status": "healthy", "message": "Neo4j is accessible"}
        else:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Neo4j is not responding"
            )
    except Exception as e:
        logger.error(f"Graph health check failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Graph health check failed: {str(e)}"
        )


@router.post("/initialize")
async def initialize_graph_schema():
    """Initialize graph schema (indexes and constraints)"""
    try:
        neo4j_service.initialize_graph_schema()
        return {"status": "success", "message": "Graph schema initialized"}
    except Exception as e:
        logger.error(f"Schema initialization failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to initialize schema: {str(e)}"
        )


@router.get("/stats")
async def get_graph_stats():
    """Get knowledge graph statistics"""
    try:
        stats = neo4j_service.get_graph_statistics()
        return stats
    except Exception as e:
        logger.error(f"Failed to get graph stats: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve statistics: {str(e)}"
        )


@router.get("/similar-patients/{patient_mrn}")
async def find_similar_patients(
    patient_mrn: str,
    min_shared_diagnoses: int = Query(2, ge=1, le=10),
    limit: int = Query(10, ge=1, le=50)
):
    """Find patients with similar clinical profiles"""
    try:
        similar = neo4j_service.find_similar_patients(
            patient_mrn,
            min_shared_diagnoses,
            limit
        )
        return {
            "target_patient": patient_mrn,
            "similar_patients": similar,
            "count": len(similar)
        }
    except Exception as e:
        logger.error(f"Similar patients query failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Query failed: {str(e)}"
        )


@router.get("/pathway/{patient_mrn}")
async def get_treatment_pathway(patient_mrn: str):
    """Get chronological treatment pathway for patient"""
    try:
        pathway = neo4j_service.get_treatment_pathway(patient_mrn)
        return {
            "patient_mrn": patient_mrn,
            "pathway": pathway,
            "event_count": len(pathway)
        }
    except Exception as e:
        logger.error(f"Treatment pathway query failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Query failed: {str(e)}"
        )


@router.get("/protocol/medications")
async def get_medication_protocol(
    diagnosis: str = Query(..., description="Diagnosis name to search"),
    total_patients: int = Query(100, description="Total patients for percentage calculation")
):
    """Get common medication protocols for a diagnosis"""
    try:
        protocols = neo4j_service.get_medication_protocol(diagnosis)
        return {
            "diagnosis": diagnosis,
            "protocols": protocols,
            "protocol_count": len(protocols)
        }
    except Exception as e:
        logger.error(f"Medication protocol query failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Query failed: {str(e)}"
        )


@router.get("/complications/{procedure_name}")
async def find_procedure_complications(
    procedure_name: str,
    days_window: int = Query(30, ge=1, le=90, description="Days after procedure to look for complications")
):
    """Find common complications after a procedure"""
    try:
        complications = neo4j_service.find_complications(procedure_name, days_window)
        return {
            "procedure": procedure_name,
            "complications": complications,
            "complication_count": len(complications)
        }
    except Exception as e:
        logger.error(f"Complications query failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Query failed: {str(e)}"
        )


@router.post("/query")
async def execute_custom_query(
    cypher_query: str,
    parameters: Optional[Dict[str, Any]] = None
):
    """Execute custom Cypher query (admin only - should add auth)"""
    try:
        # TODO: Add authentication check for admin role
        results = neo4j_service.query_graph(cypher_query, parameters)
        return {
            "query": cypher_query,
            "results": results,
            "result_count": len(results)
        }
    except Exception as e:
        logger.error(f"Custom query failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Query execution failed: {str(e)}"
        )
