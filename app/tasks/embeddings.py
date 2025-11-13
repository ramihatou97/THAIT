"""
NeuroscribeAI - Embedding Generation Tasks
Celery tasks for document indexing and vector embedding generation
"""

import logging
from typing import Dict
from app.celery_app import celery_app

logger = logging.getLogger(__name__)


@celery_app.task(name="app.tasks.embeddings.generate_document_embeddings", bind=True, max_retries=3)
def generate_document_embeddings_task(self, document_id: int, text: str) -> dict:
    """
    Generate embeddings for document and store in vector database

    Args:
        document_id: Document ID
        text: Document text

    Returns:
        Indexing statistics
    """
    try:
        logger.info(f"Starting embedding generation for document {document_id}")

        # Generate embeddings and store
        from app.services.vector_search import index_document
        result = index_document(document_id, text)

        logger.info(f"✓ Document {document_id} indexed: {result['chunks_created']} chunks")

        return {
            "document_id": document_id,
            "status": "success",
            "chunks_created": result["chunks_created"],
            "chunks_stored": result["chunks_stored"]
        }

    except Exception as e:
        logger.error(f"Embedding generation task failed: {e}", exc_info=True)
        raise self.retry(exc=e, countdown=60 * (2 ** self.request.retries))


@celery_app.task(name="app.tasks.embeddings.batch_index_documents")
def batch_index_documents_task(documents: list) -> dict:
    """
    Batch index multiple documents

    Args:
        documents: List of {document_id, text} dicts

    Returns:
        Batch indexing results
    """
    results = {
        "total": len(documents),
        "successful": 0,
        "failed": 0,
        "total_chunks": 0,
        "errors": []
    }

    for doc in documents:
        try:
            result = generate_document_embeddings_task(doc["document_id"], doc["text"])
            results["successful"] += 1
            results["total_chunks"] += result.get("chunks_created", 0)
        except Exception as e:
            logger.error(f"Failed to index document {doc.get('document_id')}: {e}")
            results["failed"] += 1
            results["errors"].append({
                "document_id": doc.get("document_id"),
                "error": str(e)
            })

    logger.info(f"Batch indexing complete: {results['successful']}/{results['total']} successful, "
               f"{results['total_chunks']} chunks created")

    return results


@celery_app.task(name="app.tasks.embeddings.reindex_all_documents")
def reindex_all_documents_task() -> dict:
    """
    Reindex all documents in the database (maintenance task)

    Returns:
        Reindexing statistics
    """
    try:
        logger.info("Starting full document reindexing")

        # Get all documents from database
        from sqlalchemy import create_engine
        from sqlalchemy.orm import sessionmaker
        from app.config import settings
        from app.models import Document

        engine = create_engine(settings.get_database_url(for_alembic=True))
        Session = sessionmaker(bind=engine)

        with Session() as session:
            documents = session.query(Document).filter(
                Document.content.isnot(None)
            ).all()

        logger.info(f"Found {len(documents)} documents to reindex")

        # Batch index
        doc_list = [
            {"document_id": doc.id, "text": doc.content}
            for doc in documents
            if doc.content
        ]

        result = batch_index_documents_task(doc_list)

        logger.info(f"✓ Reindexing complete: {result['successful']} documents indexed")
        return result

    except Exception as e:
        logger.error(f"Reindexing failed: {e}", exc_info=True)
        return {
            "status": "failed",
            "error": str(e)
        }
