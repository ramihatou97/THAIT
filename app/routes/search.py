"""
NeuroscribeAI - Vector Search API Routes
Semantic similarity search endpoints
"""

import logging
from typing import List, Dict, Optional
from fastapi import APIRouter, HTTPException, Query, status, Body

from app.services.vector_search import (
    get_vector_search_service,
    index_document,
    search_documents,
    find_similar_patients_by_embeddings
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/search", tags=["Vector Search"])


@router.get("/stats")
async def get_search_stats():
    """Get vector search statistics"""
    try:
        service = get_vector_search_service()
        stats = service.get_embedding_stats()
        return stats
    except Exception as e:
        logger.error(f"Failed to get search stats: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve statistics: {str(e)}"
        )


@router.post("/index/document/{document_id}")
async def index_document_endpoint(
    document_id: int,
    text: str = Body(..., embed=True)
):
    """
    Index a document for semantic search

    Creates chunks and generates embeddings for vector similarity search.
    """
    try:
        logger.info(f"Indexing document {document_id} for vector search")
        result = index_document(document_id, text)
        return {
            "status": "success",
            "message": f"Document {document_id} indexed successfully",
            "stats": result
        }
    except Exception as e:
        logger.error(f"Document indexing failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Indexing failed: {str(e)}"
        )


@router.get("/semantic")
async def semantic_search(
    query: str = Query(..., description="Semantic search query"),
    top_k: int = Query(10, ge=1, le=50, description="Number of results"),
    threshold: float = Query(0.7, ge=0.0, le=1.0, description="Minimum similarity score")
):
    """
    Semantic search across all clinical documents

    Examples:
    - "glioblastoma patients with motor deficits"
    - "postoperative complications after craniotomy"
    - "steroid taper protocols"
    """
    try:
        logger.info(f"Semantic search: '{query}' (top_k={top_k})")
        service = get_vector_search_service()
        results = service.semantic_search(
            query=query,
            top_k=top_k,
            similarity_threshold=threshold
        )

        return {
            "query": query,
            "results": results,
            "result_count": len(results)
        }

    except Exception as e:
        logger.error(f"Semantic search failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Search failed: {str(e)}"
        )


@router.get("/similar-documents/{document_id}")
async def find_similar_documents(
    document_id: int,
    top_k: int = Query(10, ge=1, le=50),
    exclude_same_patient: bool = Query(False, description="Exclude documents from same patient")
):
    """
    Find documents semantically similar to a given document

    Use cases:
    - Find similar cases for comparison
    - Identify similar documentation patterns
    - Research cohort building
    """
    try:
        logger.info(f"Finding documents similar to {document_id}")
        service = get_vector_search_service()
        results = service.find_similar_documents(
            document_id=document_id,
            top_k=top_k,
            exclude_same_patient=exclude_same_patient
        )

        return {
            "source_document_id": document_id,
            "similar_documents": results,
            "count": len(results)
        }

    except Exception as e:
        logger.error(f"Similar documents search failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Search failed: {str(e)}"
        )


@router.get("/similar-patients/{patient_id}")
async def find_similar_patients(
    patient_id: int,
    top_k: int = Query(10, ge=1, le=50)
):
    """
    Find patients with similar clinical profiles

    Uses document embeddings to find patients with similar:
    - Diagnoses and clinical features
    - Treatment patterns
    - Documentation style and complexity

    Useful for:
    - Case-based reasoning
    - Treatment planning
    - Outcome prediction
    - Research cohorts
    """
    try:
        logger.info(f"Finding patients similar to {patient_id}")
        results = find_similar_patients_by_embeddings(patient_id, top_k=top_k)

        return {
            "source_patient_id": patient_id,
            "similar_patients": results,
            "count": len(results)
        }

    except Exception as e:
        logger.error(f"Similar patients search failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Search failed: {str(e)}"
        )


@router.post("/evidence")
async def find_evidence(
    fact_text: str = Body(..., embed=True),
    patient_id: Optional[int] = Body(None, embed=True),
    top_k: int = Body(5, embed=True, ge=1, le=20)
):
    """
    Find documentary evidence supporting or contradicting a clinical fact

    Use cases:
    - Validate extracted facts
    - Find additional context
    - Cross-reference documentation
    """
    try:
        logger.info(f"Finding evidence for: '{fact_text[:50]}...'")
        service = get_vector_search_service()
        evidence = service.find_evidence_for_fact(
            fact_text=fact_text,
            patient_id=patient_id,
            top_k=top_k
        )

        return {
            "fact": fact_text,
            "evidence_found": len(evidence),
            "evidence": evidence
        }

    except Exception as e:
        logger.error(f"Evidence search failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Search failed: {str(e)}"
        )


@router.post("/features")
async def search_by_features(
    features: List[str] = Body(..., description="List of clinical features"),
    top_k: int = Body(20, ge=1, le=100)
):
    """
    Search by multiple clinical features

    Example:
    {
      "features": ["glioblastoma", "frontal lobe", "motor weakness", "postoperative"],
      "top_k": 20
    }

    Useful for research queries and cohort identification.
    """
    try:
        logger.info(f"Searching by features: {features}")
        service = get_vector_search_service()
        results = service.search_by_clinical_features(features, top_k=top_k)

        return {
            "features": features,
            "results": results,
            "count": len(results)
        }

    except Exception as e:
        logger.error(f"Feature search failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Search failed: {str(e)}"
        )


@router.post("/hybrid")
async def hybrid_search(
    query: str = Body(..., description="Semantic query text"),
    keywords: Optional[List[str]] = Body(None, description="Optional exact keyword matches"),
    top_k: int = Body(10, ge=1, le=50)
):
    """
    Hybrid search: Combines semantic similarity with keyword matching

    Best of both worlds:
    - Semantic understanding (finds synonyms, related concepts)
    - Exact keyword matching (ensures specific terms are present)

    Example:
    {
      "query": "patients with brain tumors",
      "keywords": ["glioblastoma", "craniotomy"],
      "top_k": 10
    }
    """
    try:
        logger.info(f"Hybrid search: '{query}' with keywords: {keywords}")
        service = get_vector_search_service()
        results = service.hybrid_search(query, keywords=keywords, top_k=top_k)

        return {
            "query": query,
            "keywords": keywords,
            "results": results,
            "count": len(results)
        }

    except Exception as e:
        logger.error(f"Hybrid search failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Search failed: {str(e)}"
        )
