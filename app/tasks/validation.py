"""
NeuroscribeAI - Validation Tasks
Celery tasks for asynchronous clinical data validation
"""

import logging
from app.celery_app import celery_app

logger = logging.getLogger(__name__)


@celery_app.task(name="app.tasks.validation.validate_patient_data", bind=True, max_retries=3)
def validate_patient_data_task(self, patient_id: int) -> dict:
    """
    Validate patient clinical data asynchronously

    Args:
        patient_id: Patient ID

    Returns:
        Validation report as dictionary
    """
    try:
        logger.info(f"Starting async validation for patient {patient_id}")

        # Get all facts for patient from database
        from sqlalchemy import create_engine
        from sqlalchemy.orm import sessionmaker
        from app.config import settings
        from app.models import AtomicClinicalFact as FactModel, Document

        engine = create_engine(settings.get_database_url(for_alembic=True))
        Session = sessionmaker(bind=engine)

        with Session() as session:
            # Get all facts for patient
            facts_db = session.query(FactModel).filter(
                FactModel.patient_id == patient_id
            ).all()

            # Get all document text for source text validation
            documents = session.query(Document).filter(
                Document.patient_id == patient_id
            ).all()

            # Combine document texts
            combined_text = "\n\n".join([doc.content or "" for doc in documents if doc.content])

        # Convert to schema objects
        from app.schemas import AtomicClinicalFact
        facts = [
            AtomicClinicalFact(
                entity_type=f.entity_type,
                entity_name=f.entity_name,
                extracted_text=f.extracted_text,
                source_snippet=f.source_snippet,
                confidence_score=f.confidence_score,
                extraction_method=f.extraction_method
            )
            for f in facts_db
        ]

        # Run validation
        from app.modules.validation import validate_clinical_data
        report = validate_clinical_data(facts, combined_text, patient_id)

        logger.info(f"✓ Validation complete: Score {report.overall_quality_score}%")
        return report.dict()

    except Exception as e:
        logger.error(f"Validation task failed: {e}", exc_info=True)
        raise self.retry(exc=e, countdown=60 * (2 ** self.request.retries))

    except Exception as e:
        logger.error(f"Validation failed: {e}", exc_info=True)
        raise self.retry(exc=e, countdown=60 * (2 ** self.request.retries))
