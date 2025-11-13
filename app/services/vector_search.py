"""
NeuroscribeAI - Vector Search Service
Semantic similarity search using pgvector and sentence-transformers
"""

import logging
import numpy as np
from typing import List, Dict, Optional, Any, Tuple
from sentence_transformers import SentenceTransformer
from sqlalchemy import create_engine, text as sql_text
from sqlalchemy.orm import sessionmaker

from app.config import settings

logger = logging.getLogger(__name__)


# =============================================================================
# Vector Search Service
# =============================================================================

class VectorSearchService:
    """Service for semantic search using embeddings and pgvector"""

    def __init__(self):
        """Initialize vector search service"""
        # Initialize sentence transformer model
        self.model_name = "sentence-transformers/all-MiniLM-L6-v2"
        self.embedding_dim = 384
        self.model: Optional[SentenceTransformer] = None

        # Database connection
        self.engine = None
        self.Session = None

        self._initialize_model()
        self._initialize_db()

    def _initialize_model(self):
        """Load sentence transformer model"""
        try:
            logger.info(f"Loading embedding model: {self.model_name}")
            self.model = SentenceTransformer(self.model_name)
            logger.info(f"✓ Embedding model loaded (dim={self.embedding_dim})")
        except Exception as e:
            logger.error(f"Failed to load embedding model: {e}")
            raise

    def _initialize_db(self):
        """Initialize database connection for vector queries"""
        try:
            # Use sync connection for vector queries (pgvector doesn't support async yet)
            db_url = settings.get_database_url(for_alembic=True)
            self.engine = create_engine(db_url, pool_pre_ping=True)
            self.Session = sessionmaker(bind=self.engine)
            logger.info("✓ Vector search database connection initialized")
        except Exception as e:
            logger.error(f"Failed to initialize vector search DB: {e}")
            raise

    # =========================================================================
    # Embedding Generation
    # =========================================================================

    def generate_embedding(self, text: str) -> List[float]:
        """
        Generate embedding vector for text

        Args:
            text: Input text (will be truncated to model max length)

        Returns:
            384-dimensional embedding vector
        """
        if not self.model:
            raise RuntimeError("Embedding model not initialized")

        try:
            # Generate embedding
            embedding = self.model.encode(
                text,
                convert_to_numpy=True,
                show_progress_bar=False,
                normalize_embeddings=True  # L2 normalization for better cosine similarity
            )

            return embedding.tolist()

        except Exception as e:
            logger.error(f"Embedding generation failed: {e}")
            raise

    def generate_embeddings_batch(self, texts: List[str]) -> List[List[float]]:
        """Generate embeddings for multiple texts (more efficient)"""
        if not self.model:
            raise RuntimeError("Embedding model not initialized")

        try:
            embeddings = self.model.encode(
                texts,
                convert_to_numpy=True,
                show_progress_bar=len(texts) > 10,
                normalize_embeddings=True,
                batch_size=32
            )

            return embeddings.tolist()

        except Exception as e:
            logger.error(f"Batch embedding generation failed: {e}")
            raise

    # =========================================================================
    # Document Chunking
    # =========================================================================

    def chunk_document(
        self,
        text: str,
        chunk_size: int = None,
        overlap: int = None
    ) -> List[Dict[str, Any]]:
        """
        Split document into overlapping chunks

        Args:
            text: Document text
            chunk_size: Characters per chunk (default from settings)
            overlap: Overlap between chunks (default from settings)

        Returns:
            List of chunk dictionaries with text and positions
        """
        chunk_size = chunk_size or settings.chunk_size
        overlap = overlap or settings.chunk_overlap
        stride = chunk_size - overlap

        if stride <= 0:
            raise ValueError("Overlap must be less than chunk_size")

        chunks = []
        chunk_index = 0

        for i in range(0, len(text), stride):
            chunk_text = text[i:i + chunk_size]

            # Skip very short chunks at the end
            if len(chunk_text) < 50:
                continue

            chunks.append({
                "chunk_index": chunk_index,
                "chunk_text": chunk_text,
                "char_start": i,
                "char_end": i + len(chunk_text),
                "token_count": len(chunk_text.split()),
            })

            chunk_index += 1

        logger.info(f"Document chunked into {len(chunks)} chunks (size={chunk_size}, overlap={overlap})")
        return chunks

    def chunk_and_embed_document(self, text: str) -> List[Dict[str, Any]]:
        """Chunk document and generate embeddings for each chunk"""
        chunks = self.chunk_document(text)

        # Extract texts for batch embedding
        chunk_texts = [c["chunk_text"] for c in chunks]

        # Generate embeddings in batch (more efficient)
        embeddings = self.generate_embeddings_batch(chunk_texts)

        # Attach embeddings to chunks
        for chunk, embedding in zip(chunks, embeddings):
            chunk["embedding"] = embedding

        return chunks

    # =========================================================================
    # Storage Operations
    # =========================================================================

    def store_document_chunks(
        self,
        document_id: int,
        chunks_with_embeddings: List[Dict[str, Any]]
    ) -> int:
        """
        Store document chunks with embeddings in database

        Args:
            document_id: Document ID
            chunks_with_embeddings: Chunks with embedding vectors

        Returns:
            Number of chunks stored
        """
        with self.Session() as session:
            try:
                # Clear existing chunks for this document
                session.execute(
                    sql_text("DELETE FROM document_chunks WHERE document_id = :doc_id"),
                    {"doc_id": document_id}
                )

                # Insert new chunks
                for chunk in chunks_with_embeddings:
                    session.execute(
                        sql_text("""
                            INSERT INTO document_chunks (
                                document_id, chunk_index, chunk_text,
                                char_start, char_end, embedding, token_count,
                                contains_clinical_entities
                            ) VALUES (
                                :doc_id, :chunk_idx, :text,
                                :start, :end, :embedding::vector, :tokens,
                                :has_entities
                            )
                        """),
                        {
                            "doc_id": document_id,
                            "chunk_idx": chunk["chunk_index"],
                            "text": chunk["chunk_text"],
                            "start": chunk["char_start"],
                            "end": chunk["char_end"],
                            "embedding": str(chunk["embedding"]),
                            "tokens": chunk["token_count"],
                            "has_entities": True  # Will be updated by fact extraction
                        }
                    )

                session.commit()
                logger.info(f"✓ Stored {len(chunks_with_embeddings)} chunks for document {document_id}")
                return len(chunks_with_embeddings)

            except Exception as e:
                session.rollback()
                logger.error(f"Failed to store chunks: {e}")
                raise

    # =========================================================================
    # Similarity Search
    # =========================================================================

    def semantic_search(
        self,
        query: str,
        top_k: int = 10,
        similarity_threshold: float = None,
        document_id: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """
        Semantic search across all document chunks

        Args:
            query: Search query text
            top_k: Number of results to return
            similarity_threshold: Minimum similarity score (0-1)
            document_id: Optional filter by specific document

        Returns:
            List of matching chunks with similarity scores
        """
        threshold = similarity_threshold or settings.vector_similarity_threshold

        # Generate query embedding
        query_embedding = self.generate_embedding(query)

        with self.Session() as session:
            # Build query
            sql_query = """
                SELECT
                    dc.id,
                    dc.document_id,
                    dc.chunk_index,
                    dc.chunk_text,
                    dc.section_name,
                    dc.char_start,
                    dc.char_end,
                    1 - (dc.embedding <=> :query_embedding::vector) as similarity_score,
                    d.title as document_title,
                    d.document_type,
                    d.patient_id
                FROM document_chunks dc
                JOIN documents d ON dc.document_id = d.id
                WHERE dc.embedding IS NOT NULL
            """

            params = {"query_embedding": str(query_embedding)}

            # Add document filter if specified
            if document_id:
                sql_query += " AND dc.document_id = :doc_id"
                params["doc_id"] = document_id

            # Add similarity threshold
            sql_query += " AND (1 - (dc.embedding <=> :query_embedding::vector)) >= :threshold"
            params["threshold"] = threshold

            # Order and limit
            sql_query += " ORDER BY dc.embedding <=> :query_embedding::vector LIMIT :limit"
            params["limit"] = top_k

            # Execute query
            result = session.execute(sql_text(sql_query), params)

            results = []
            for row in result:
                results.append({
                    "chunk_id": row.id,
                    "document_id": row.document_id,
                    "patient_id": row.patient_id,
                    "chunk_text": row.chunk_text,
                    "section_name": row.section_name,
                    "document_title": row.document_title,
                    "document_type": row.document_type,
                    "similarity_score": float(row.similarity_score),
                    "char_start": row.char_start,
                    "char_end": row.char_end
                })

            logger.info(f"Semantic search found {len(results)} results for query: '{query[:50]}...'")
            return results

    def find_similar_documents(
        self,
        document_id: int,
        top_k: int = 10,
        exclude_same_patient: bool = False
    ) -> List[Dict[str, Any]]:
        """
        Find documents similar to given document

        Args:
            document_id: Source document ID
            top_k: Number of similar documents to return
            exclude_same_patient: Whether to exclude documents from same patient

        Returns:
            List of similar documents with scores
        """
        with self.Session() as session:
            # Get all chunks for source document
            chunks = session.execute(
                sql_text("SELECT embedding FROM document_chunks WHERE document_id = :doc_id AND embedding IS NOT NULL"),
                {"doc_id": document_id}
            ).fetchall()

            if not chunks:
                logger.warning(f"No embeddings found for document {document_id}")
                return []

            # Average embeddings to get document vector
            embeddings = [np.array(eval(row.embedding)) for row in chunks]
            doc_embedding = np.mean(embeddings, axis=0).tolist()

            # Search for similar chunks
            sql_query = """
                SELECT DISTINCT
                    dc.document_id,
                    d.title,
                    d.document_type,
                    d.patient_id,
                    AVG(1 - (dc.embedding <=> :doc_embedding::vector)) as avg_similarity
                FROM document_chunks dc
                JOIN documents d ON dc.document_id = d.id
                WHERE dc.document_id != :source_doc_id
                  AND dc.embedding IS NOT NULL
            """

            params = {
                "doc_embedding": str(doc_embedding),
                "source_doc_id": document_id
            }

            if exclude_same_patient:
                sql_query += """
                  AND d.patient_id NOT IN (
                      SELECT patient_id FROM documents WHERE id = :source_doc_id
                  )
                """

            sql_query += """
                GROUP BY dc.document_id, d.title, d.document_type, d.patient_id
                HAVING AVG(1 - (dc.embedding <=> :doc_embedding::vector)) >= :threshold
                ORDER BY avg_similarity DESC
                LIMIT :limit
            """

            params["threshold"] = settings.vector_similarity_threshold
            params["limit"] = top_k

            result = session.execute(sql_text(sql_query), params)

            results = []
            for row in result:
                results.append({
                    "document_id": row.document_id,
                    "patient_id": row.patient_id,
                    "title": row.title,
                    "document_type": row.document_type,
                    "similarity_score": float(row.avg_similarity)
                })

            logger.info(f"Found {len(results)} similar documents to document {document_id}")
            return results

    def find_similar_patients(
        self,
        patient_id: int,
        top_k: int = 10
    ) -> List[Dict[str, Any]]:
        """
        Find patients with similar clinical profiles based on document embeddings

        Args:
            patient_id: Source patient ID
            top_k: Number of similar patients to return

        Returns:
            List of similar patients with similarity scores
        """
        with self.Session() as session:
            # Get all document chunks for patient
            chunks = session.execute(
                sql_text("""
                    SELECT dc.embedding
                    FROM document_chunks dc
                    JOIN documents d ON dc.document_id = d.id
                    WHERE d.patient_id = :patient_id
                      AND dc.embedding IS NOT NULL
                """),
                {"patient_id": patient_id}
            ).fetchall()

            if not chunks:
                logger.warning(f"No embeddings found for patient {patient_id}")
                return []

            # Create patient profile vector (average of all chunks)
            embeddings = [np.array(eval(row.embedding)) for row in chunks]
            patient_profile = np.mean(embeddings, axis=0).tolist()

            # Find similar patients
            sql_query = """
                SELECT
                    d.patient_id,
                    p.mrn,
                    p.age,
                    p.sex,
                    p.primary_diagnosis,
                    AVG(1 - (dc.embedding <=> :profile::vector)) as similarity_score,
                    COUNT(DISTINCT d.id) as document_count
                FROM document_chunks dc
                JOIN documents d ON dc.document_id = d.id
                JOIN patients p ON d.patient_id = p.id
                WHERE d.patient_id != :source_patient_id
                  AND dc.embedding IS NOT NULL
                GROUP BY d.patient_id, p.mrn, p.age, p.sex, p.primary_diagnosis
                HAVING AVG(1 - (dc.embedding <=> :profile::vector)) >= :threshold
                ORDER BY similarity_score DESC
                LIMIT :limit
            """

            result = session.execute(
                sql_text(sql_query),
                {
                    "profile": str(patient_profile),
                    "source_patient_id": patient_id,
                    "threshold": settings.vector_similarity_threshold,
                    "limit": top_k
                }
            )

            results = []
            for row in result:
                results.append({
                    "patient_id": row.patient_id,
                    "mrn": row.mrn,
                    "age": row.age,
                    "sex": row.sex,
                    "primary_diagnosis": row.primary_diagnosis,
                    "similarity_score": float(row.similarity_score),
                    "document_count": row.document_count
                })

            logger.info(f"Found {len(results)} similar patients to patient {patient_id}")
            return results

    def search_by_clinical_features(
        self,
        features: List[str],
        top_k: int = 20
    ) -> List[Dict[str, Any]]:
        """
        Search for patients/documents by clinical features

        Args:
            features: List of clinical features (e.g., ["glioblastoma", "frontal lobe", "motor deficit"])
            top_k: Number of results

        Returns:
            Matching documents/patients
        """
        # Combine features into query
        query_text = " ".join(features)

        # Use semantic search
        return self.semantic_search(query_text, top_k=top_k)

    # =========================================================================
    # Advanced Search Methods
    # =========================================================================

    def hybrid_search(
        self,
        query: str,
        keywords: Optional[List[str]] = None,
        top_k: int = 10
    ) -> List[Dict[str, Any]]:
        """
        Hybrid search: Combines vector similarity with keyword matching

        Args:
            query: Semantic query
            keywords: Optional exact keyword matches
            top_k: Number of results

        Returns:
            Hybrid ranked results
        """
        # Get semantic results
        semantic_results = self.semantic_search(query, top_k=top_k * 2)

        # If keywords provided, boost scores for keyword matches
        if keywords:
            for result in semantic_results:
                keyword_matches = sum(
                    1 for kw in keywords
                    if kw.lower() in result["chunk_text"].lower()
                )
                # Boost score by 10% per keyword match
                result["similarity_score"] *= (1 + 0.1 * keyword_matches)
                result["keyword_matches"] = keyword_matches

            # Re-sort by boosted scores
            semantic_results.sort(key=lambda x: x["similarity_score"], reverse=True)

        return semantic_results[:top_k]

    def find_evidence_for_fact(
        self,
        fact_text: str,
        patient_id: Optional[int] = None,
        top_k: int = 5
    ) -> List[Dict[str, Any]]:
        """
        Find supporting or contradicting evidence for a clinical fact

        Args:
            fact_text: The fact to find evidence for
            patient_id: Optional patient ID to search within
            top_k: Number of evidence chunks to return

        Returns:
            List of relevant document chunks
        """
        embedding = self.generate_embedding(fact_text)

        with self.Session() as session:
            sql_query = """
                SELECT
                    dc.chunk_text,
                    dc.document_id,
                    d.document_type,
                    d.patient_id,
                    1 - (dc.embedding <=> :embedding::vector) as similarity
                FROM document_chunks dc
                JOIN documents d ON dc.document_id = d.id
                WHERE dc.embedding IS NOT NULL
            """

            params = {"embedding": str(embedding)}

            if patient_id:
                sql_query += " AND d.patient_id = :patient_id"
                params["patient_id"] = patient_id

            sql_query += """
                ORDER BY dc.embedding <=> :embedding::vector
                LIMIT :limit
            """
            params["limit"] = top_k

            result = session.execute(sql_text(sql_query), params)

            return [
                {
                    "chunk_text": row.chunk_text,
                    "document_id": row.document_id,
                    "patient_id": row.patient_id,
                    "document_type": row.document_type,
                    "similarity_score": float(row.similarity)
                }
                for row in result
            ]

    # =========================================================================
    # Utility Methods
    # =========================================================================

    def get_embedding_stats(self) -> Dict[str, Any]:
        """Get statistics about stored embeddings"""
        with self.Session() as session:
            result = session.execute(sql_text("""
                SELECT
                    COUNT(*) as total_chunks,
                    COUNT(DISTINCT document_id) as documents_with_embeddings,
                    COUNT(embedding) as chunks_with_embeddings,
                    AVG(token_count) as avg_tokens_per_chunk
                FROM document_chunks
            """)).fetchone()

            return {
                "total_chunks": result.total_chunks,
                "documents_indexed": result.documents_with_embeddings,
                "chunks_embedded": result.chunks_with_embeddings,
                "avg_tokens": int(result.avg_tokens_per_chunk) if result.avg_tokens_per_chunk else 0,
                "embedding_dimensions": self.embedding_dim,
                "model": self.model_name
            }

    def reindex_document(self, document_id: int, text: str) -> int:
        """Re-generate embeddings for a document"""
        logger.info(f"Re-indexing document {document_id}")
        chunks = self.chunk_and_embed_document(text)
        return self.store_document_chunks(document_id, chunks)


# =============================================================================
# Global Service Instance
# =============================================================================

# Lazy initialization - will be created when first accessed
_vector_search_service: Optional[VectorSearchService] = None


def get_vector_search_service() -> VectorSearchService:
    """Get or create vector search service instance"""
    global _vector_search_service
    if _vector_search_service is None:
        _vector_search_service = VectorSearchService()
    return _vector_search_service


# =============================================================================
# Public API Functions
# =============================================================================

def index_document(document_id: int, text: str) -> Dict[str, int]:
    """
    Index a document for vector search

    Args:
        document_id: Document ID
        text: Document text

    Returns:
        Indexing statistics
    """
    service = get_vector_search_service()
    chunks = service.chunk_and_embed_document(text)
    chunks_stored = service.store_document_chunks(document_id, chunks)

    return {
        "document_id": document_id,
        "chunks_created": len(chunks),
        "chunks_stored": chunks_stored
    }


def search_documents(
    query: str,
    top_k: int = 10,
    patient_id: Optional[int] = None
) -> List[Dict[str, Any]]:
    """
    Semantic search across documents

    Args:
        query: Search query
        top_k: Number of results
        patient_id: Optional patient filter

    Returns:
        Search results
    """
    service = get_vector_search_service()
    return service.semantic_search(query, top_k=top_k)


def find_similar_patients_by_embeddings(patient_id: int, top_k: int = 10) -> List[Dict]:
    """Find patients with similar clinical profiles"""
    service = get_vector_search_service()
    return service.find_similar_patients(patient_id, top_k=top_k)
