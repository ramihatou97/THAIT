"""
NeuroscribeAI - Graph Synchronization Tasks
Celery tasks for syncing clinical facts to Neo4j knowledge graph
"""

import logging
from typing import List, Dict
from app.celery_app import celery_app

logger = logging.getLogger(__name__)


@celery_app.task(name="app.tasks.graph_sync.sync_patient_to_graph", bind=True, max_retries=3)
def sync_patient_to_graph_task(self, patient_id: int) -> dict:
    """
    Synchronize patient and all their facts to Neo4j graph

    Args:
        patient_id: Patient ID

    Returns:
        Sync statistics
    """
    try:
        logger.info(f"Starting graph sync for patient {patient_id}")

        # Get patient data and facts from database
        from sqlalchemy import create_engine
        from sqlalchemy.orm import sessionmaker
        from app.config import settings
        from app.models import Patient, AtomicClinicalFact as FactModel

        engine = create_engine(settings.get_database_url(for_alembic=True))
        Session = sessionmaker(bind=engine)

        with Session() as session:
            # Get patient
            patient = session.query(Patient).filter(Patient.id == patient_id).first()
            if not patient:
                raise ValueError(f"Patient {patient_id} not found")

            patient_data = {
                "id": patient.id,
                "mrn": patient.mrn,
                "age": patient.age,
                "sex": patient.sex,
                "primary_diagnosis": patient.primary_diagnosis,
                "updated_at": patient.updated_at
            }

            # Get all facts
            facts_db = session.query(FactModel).filter(
                FactModel.patient_id == patient_id
            ).all()

        # Convert to schema objects
        from app.schemas import AtomicClinicalFact
        facts = [
            AtomicClinicalFact(
                entity_type=f.entity_type,
                entity_name=f.entity_name,
                extracted_text=f.extracted_text,
                source_snippet=f.source_snippet,
                confidence_score=f.confidence_score,
                extraction_method=f.extraction_method,
                anatomical_context=f.anatomical_context,
                medication_detail=f.medication_detail,
                temporal_context=f.temporal_context,
                is_negated=f.is_negated,
                is_historical=f.is_historical
            )
            for f in facts_db
        ]

        # Sync to Neo4j
        from app.services.neo4j_service import sync_patient_facts_to_graph
        stats = sync_patient_facts_to_graph(patient_id, patient_data, facts)

        logger.info(f"✓ Graph sync complete: {stats['nodes_created']} nodes, "
                   f"{stats['relationships_created']} relationships")

        return {
            "patient_id": patient_id,
            "status": "success",
            "stats": stats
        }

    except Exception as e:
        logger.error(f"Graph sync task failed: {e}", exc_info=True)
        raise self.retry(exc=e, countdown=60 * (2 ** self.request.retries))


@celery_app.task(name="app.tasks.graph_sync.batch_sync_patients")
def batch_sync_patients_task(patient_ids: List[int]) -> Dict:
    """
    Batch sync multiple patients to graph

    Args:
        patient_ids: List of patient IDs

    Returns:
        Batch sync results
    """
    results = {
        "total": len(patient_ids),
        "successful": 0,
        "failed": 0,
        "errors": []
    }

    for patient_id in patient_ids:
        try:
            sync_patient_to_graph_task(patient_id)
            results["successful"] += 1
        except Exception as e:
            logger.error(f"Failed to sync patient {patient_id}: {e}")
            results["failed"] += 1
            results["errors"].append({
                "patient_id": patient_id,
                "error": str(e)
            })

    logger.info(f"Batch sync complete: {results['successful']}/{results['total']} successful")
    return results
