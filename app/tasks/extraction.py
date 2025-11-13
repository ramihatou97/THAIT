"""
NeuroscribeAI - Extraction Tasks
Celery tasks for asynchronous clinical fact extraction
"""

import logging
from typing import List
from app.celery_app import celery_app
from app.modules.extraction import extract_clinical_facts
from app.schemas import AtomicClinicalFact

logger = logging.getLogger(__name__)


@celery_app.task(name="app.tasks.extraction.extract_facts", bind=True, max_retries=3)
def extract_facts_task(self, text: str, patient_id: int, document_id: int) -> List[dict]:
    """
    Extract clinical facts from text asynchronously

    Args:
        text: Clinical text to extract from
        patient_id: Patient ID
        document_id: Document ID

    Returns:
        List of extracted facts as dictionaries
    """
    try:
        logger.info(f"Starting extraction for document {document_id}, patient {patient_id}")

        # Extract facts
        facts = extract_clinical_facts(text, patient_id, document_id)

        # Convert to dictionaries for JSON serialization
        facts_dict = [fact.dict() for fact in facts]

        logger.info(f"Extraction complete: {len(facts_dict)} facts extracted")
        return facts_dict

    except Exception as e:
        logger.error(f"Extraction failed: {e}", exc_info=True)
        # Retry with exponential backoff
        raise self.retry(exc=e, countdown=60 * (2 ** self.request.retries))


@celery_app.task(name="app.tasks.extraction.batch_extract")
def batch_extract_task(documents: List[dict]) -> List[dict]:
    """
    Batch extraction for multiple documents

    Args:
        documents: List of documents with text, patient_id, document_id

    Returns:
        List of extraction results
    """
    results = []
    for doc in documents:
        try:
            facts = extract_clinical_facts(
                doc["text"],
                doc["patient_id"],
                doc["document_id"]
            )
            results.append({
                "document_id": doc["document_id"],
                "facts": [f.dict() for f in facts],
                "status": "success"
            })
        except Exception as e:
            logger.error(f"Batch extraction failed for doc {doc.get('document_id')}: {e}")
            results.append({
                "document_id": doc.get("document_id"),
                "error": str(e),
                "status": "failed"
            })

    return results
