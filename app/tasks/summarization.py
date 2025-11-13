"""
NeuroscribeAI - Summarization Tasks
Celery tasks for asynchronous clinical summary generation
"""

import logging
from app.celery_app import celery_app

logger = logging.getLogger(__name__)


@celery_app.task(name="app.tasks.summarization.generate_summary", bind=True, max_retries=3)
def generate_summary_task(self, patient_id: int, summary_type: str = "discharge_summary") -> dict:
    """
    Generate clinical summary asynchronously

    Args:
        patient_id: Patient ID
        summary_type: Type of summary to generate

    Returns:
        Generated summary as dictionary
    """
    try:
        logger.info(f"Starting async summary generation: {summary_type} for patient {patient_id}")

        # Get all facts and alerts for patient from database
        from sqlalchemy import create_engine
        from sqlalchemy.orm import sessionmaker
        from app.config import settings
        from app.models import AtomicClinicalFact as FactModel, ClinicalAlert as AlertModel, Patient

        engine = create_engine(settings.get_database_url(for_alembic=True))
        Session = sessionmaker(bind=engine)

        with Session() as session:
            # Get patient data
            patient = session.query(Patient).filter(Patient.id == patient_id).first()
            if not patient:
                raise ValueError(f"Patient {patient_id} not found")

            patient_data = {
                "mrn": patient.mrn,
                "age": patient.age,
                "sex": patient.sex,
                "primary_diagnosis": patient.primary_diagnosis
            }

            # Get all facts
            facts_db = session.query(FactModel).filter(
                FactModel.patient_id == patient_id
            ).all()

            # Get alerts
            alerts_db = session.query(AlertModel).filter(
                AlertModel.patient_id == patient_id
            ).all()

        # Convert to schema objects
        from app.schemas import AtomicClinicalFact, ClinicalAlert, SummaryRequest
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

        alerts = [
            ClinicalAlert(
                alert_type=a.alert_type,
                category=a.category,
                severity=a.severity,
                title=a.title,
                message=a.message,
                recommendation=a.recommendation,
                triggered_by_rule=a.triggered_by_rule,
                rule_logic=a.rule_logic,
                evidence_fact_ids=[],
                evidence_summary=a.evidence_summary
            )
            for a in alerts_db
        ]

        # Build summary request
        summary_request = SummaryRequest(
            patient_mrn=patient.mrn,
            patient_id=patient_id,
            summary_type=summary_type,
            facts=facts,
            alerts=alerts,
            patient_data=patient_data
        )

        # Generate summary
        from app.modules.summarization import generate_clinical_summary
        summary = generate_clinical_summary(
            request=summary_request,
            facts=facts,
            alerts=alerts,
            patient_data=patient_data
        )

        logger.info(f"✓ Summary generated: {len(summary.sections)} sections")
        return summary.dict()

    except Exception as e:
        logger.error(f"Summary generation task failed: {e}", exc_info=True)
        raise self.retry(exc=e, countdown=60 * (2 ** self.request.retries))

    except Exception as e:
        logger.error(f"Summary generation failed: {e}", exc_info=True)
        raise self.retry(exc=e, countdown=60 * (2 ** self.request.retries))
