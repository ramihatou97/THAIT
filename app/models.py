"""
NeuroscribeAI Database Models
SQLAlchemy 2.0 ORM models with pgvector support
"""

from datetime import datetime
from typing import List, Optional
from sqlalchemy import (
    Boolean, DateTime, Float, ForeignKey, Integer, String, Text,
    Enum, Index, CheckConstraint, UniqueConstraint, JSON
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from sqlalchemy.sql import func
from pgvector.sqlalchemy import Vector


class Base(DeclarativeBase):
    """Base class for all models"""
    pass


class TimestampMixin:
    """Mixin for created_at and updated_at timestamps"""
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False
    )


# =============================================================================
# Patient Models
# =============================================================================

class Patient(Base, TimestampMixin):
    """Patient demographic and core information"""
    __tablename__ = "patients"

    # Primary key
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    # Demographics
    mrn: Mapped[str] = mapped_column(String(50), unique=True, nullable=False, index=True)
    first_name: Mapped[Optional[str]] = mapped_column(String(100))
    last_name: Mapped[Optional[str]] = mapped_column(String(100))
    date_of_birth: Mapped[Optional[datetime]] = mapped_column(DateTime)
    age: Mapped[Optional[int]] = mapped_column(Integer)
    sex: Mapped[Optional[str]] = mapped_column(String(20))

    # Contact information
    phone: Mapped[Optional[str]] = mapped_column(String(20))
    email: Mapped[Optional[str]] = mapped_column(String(100))
    address: Mapped[Optional[str]] = mapped_column(Text)

    # Clinical summary
    primary_diagnosis: Mapped[Optional[str]] = mapped_column(Text)
    attending_physician: Mapped[Optional[str]] = mapped_column(String(200))

    # Metadata
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    last_visit_date: Mapped[Optional[datetime]] = mapped_column(DateTime)

    # Relationships
    documents: Mapped[List["Document"]] = relationship(
        "Document",
        back_populates="patient",
        cascade="all, delete-orphan",
        lazy="selectin"
    )
    clinical_facts: Mapped[List["AtomicClinicalFact"]] = relationship(
        "AtomicClinicalFact",
        back_populates="patient",
        cascade="all, delete-orphan",
        lazy="select"
    )
    clinical_alerts: Mapped[List["ClinicalAlert"]] = relationship(
        "ClinicalAlert",
        back_populates="patient",
        cascade="all, delete-orphan",
        lazy="select"
    )

    # Constraints
    __table_args__ = (
        CheckConstraint("age >= 0 AND age <= 150", name="valid_age"),
        Index("idx_patient_name", "last_name", "first_name"),
        Index("idx_patient_active", "is_active"),
    )

    def __repr__(self) -> str:
        return f"<Patient(id={self.id}, mrn={self.mrn}, name={self.last_name}, {self.first_name})>"


# =============================================================================
# Document Models
# =============================================================================

class Document(Base, TimestampMixin):
    """Clinical documents (discharge summaries, operative notes, etc.)"""
    __tablename__ = "documents"

    # Primary key
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    # Foreign keys
    patient_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("patients.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )

    # Document metadata
    document_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        index=True
    )  # "discharge_summary", "operative_note", "progress_note", etc.

    document_date: Mapped[datetime] = mapped_column(DateTime, nullable=False, index=True)
    author: Mapped[Optional[str]] = mapped_column(String(200))
    department: Mapped[Optional[str]] = mapped_column(String(100))

    # Content
    raw_text: Mapped[str] = mapped_column(Text, nullable=False)
    structured_data: Mapped[Optional[dict]] = mapped_column(JSON)

    # File information
    original_filename: Mapped[Optional[str]] = mapped_column(String(255))
    file_path: Mapped[Optional[str]] = mapped_column(String(500))
    file_size_bytes: Mapped[Optional[int]] = mapped_column(Integer)
    file_hash: Mapped[Optional[str]] = mapped_column(String(64))  # SHA-256

    # Processing status
    processing_status: Mapped[str] = mapped_column(
        String(20),
        default="pending",
        nullable=False,
        index=True
    )  # "pending", "processing", "completed", "failed"

    processing_started_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    processing_completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    processing_error: Mapped[Optional[str]] = mapped_column(Text)

    # Extraction statistics
    facts_extracted: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    avg_confidence: Mapped[Optional[float]] = mapped_column(Float)

    # Version control
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    is_latest: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    # Relationships
    patient: Mapped["Patient"] = relationship("Patient", back_populates="documents")
    chunks: Mapped[List["DocumentChunk"]] = relationship(
        "DocumentChunk",
        back_populates="document",
        cascade="all, delete-orphan",
        lazy="select"
    )
    clinical_facts: Mapped[List["AtomicClinicalFact"]] = relationship(
        "AtomicClinicalFact",
        back_populates="document",
        cascade="all, delete-orphan",
        lazy="select"
    )
    validation_results: Mapped[List["ValidationResult"]] = relationship(
        "ValidationResult",
        back_populates="document",
        cascade="all, delete-orphan",
        lazy="select"
    )

    # Constraints
    __table_args__ = (
        Index("idx_document_patient_date", "patient_id", "document_date"),
        Index("idx_document_status", "processing_status"),
        Index("idx_document_type_date", "document_type", "document_date"),
        CheckConstraint("version >= 1", name="positive_version"),
        CheckConstraint("facts_extracted >= 0", name="non_negative_facts"),
    )

    def __repr__(self) -> str:
        return f"<Document(id={self.id}, type={self.document_type}, patient_id={self.patient_id})>"


class DocumentChunk(Base, TimestampMixin):
    """Document chunks for vector search with embeddings"""
    __tablename__ = "document_chunks"

    # Primary key
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    # Foreign keys
    document_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("documents.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )

    # Chunk information
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False)
    chunk_text: Mapped[str] = mapped_column(Text, nullable=False)
    char_start: Mapped[int] = mapped_column(Integer, nullable=False)
    char_end: Mapped[int] = mapped_column(Integer, nullable=False)

    # Vector embedding (384 dimensions for all-MiniLM-L6-v2)
    embedding: Mapped[Optional[Vector]] = mapped_column(Vector(384))

    # Section classification
    section_name: Mapped[Optional[str]] = mapped_column(String(100))
    section_type: Mapped[Optional[str]] = mapped_column(String(50))

    # Metadata
    token_count: Mapped[Optional[int]] = mapped_column(Integer)
    contains_clinical_entities: Mapped[bool] = mapped_column(Boolean, default=False)

    # Relationships
    document: Mapped["Document"] = relationship("Document", back_populates="chunks")

    # Constraints
    __table_args__ = (
        Index("idx_chunk_document", "document_id", "chunk_index"),
        Index(
            "idx_chunk_embedding",
            "embedding",
            postgresql_using="ivfflat",
            postgresql_with={"lists": 100},
            postgresql_ops={"embedding": "vector_cosine_ops"}
        ),
        UniqueConstraint("document_id", "chunk_index", name="uq_document_chunk"),
        CheckConstraint("char_start >= 0", name="non_negative_char_start"),
        CheckConstraint("char_end > char_start", name="valid_char_range"),
    )

    def __repr__(self) -> str:
        return f"<DocumentChunk(id={self.id}, document_id={self.document_id}, index={self.chunk_index})>"


# =============================================================================
# Clinical Fact Models
# =============================================================================

class AtomicClinicalFact(Base, TimestampMixin):
    """Atomic clinical facts extracted from documents"""
    __tablename__ = "atomic_clinical_facts"

    # Primary key
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    # Foreign keys
    patient_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("patients.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    document_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("documents.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )

    # Core identification
    entity_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    entity_name: Mapped[str] = mapped_column(String(500), nullable=False, index=True)
    extracted_text: Mapped[str] = mapped_column(Text, nullable=False)
    source_snippet: Mapped[str] = mapped_column(Text, nullable=False)

    # Confidence and extraction method
    confidence_score: Mapped[float] = mapped_column(Float, nullable=False)
    extraction_method: Mapped[str] = mapped_column(String(50), nullable=False)

    # Timestamps
    timestamp: Mapped[Optional[datetime]] = mapped_column(DateTime, index=True)
    resolved_timestamp: Mapped[Optional[datetime]] = mapped_column(DateTime, index=True)
    temporal_modifier: Mapped[Optional[str]] = mapped_column(String(50))

    # Negation and history
    is_negated: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_historical: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_hypothetical: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    # Detailed schemas (stored as JSON)
    anatomical_context: Mapped[Optional[dict]] = mapped_column(JSON)
    medication_detail: Mapped[Optional[dict]] = mapped_column(JSON)
    imaging_detail: Mapped[Optional[dict]] = mapped_column(JSON)
    procedure_detail: Mapped[Optional[dict]] = mapped_column(JSON)
    lab_value: Mapped[Optional[dict]] = mapped_column(JSON)
    neuro_exam_detail: Mapped[Optional[dict]] = mapped_column(JSON)
    temporal_context: Mapped[Optional[dict]] = mapped_column(JSON)

    # Standardized codes
    icd10_codes: Mapped[Optional[List[str]]] = mapped_column(JSON)
    snomed_codes: Mapped[Optional[List[str]]] = mapped_column(JSON)
    rxnorm_codes: Mapped[Optional[List[str]]] = mapped_column(JSON)
    loinc_codes: Mapped[Optional[List[str]]] = mapped_column(JSON)

    # Source location
    char_start: Mapped[Optional[int]] = mapped_column(Integer)
    char_end: Mapped[Optional[int]] = mapped_column(Integer)
    line_number: Mapped[Optional[int]] = mapped_column(Integer)

    # Verification
    verified: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    verified_by: Mapped[Optional[str]] = mapped_column(String(200))
    verified_at: Mapped[Optional[datetime]] = mapped_column(DateTime)

    # NLI verification
    nli_verified: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    nli_score: Mapped[Optional[float]] = mapped_column(Float)
    nli_label: Mapped[Optional[str]] = mapped_column(String(20))

    # Graph database sync
    neo4j_node_id: Mapped[Optional[str]] = mapped_column(String(100))
    synced_to_neo4j: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    # Relationships
    patient: Mapped["Patient"] = relationship("Patient", back_populates="clinical_facts")
    document: Mapped["Document"] = relationship("Document", back_populates="clinical_facts")

    # Constraints
    __table_args__ = (
        Index("idx_fact_patient_type", "patient_id", "entity_type"),
        Index("idx_fact_entity_name", "entity_name"),
        Index("idx_fact_timestamp", "resolved_timestamp"),
        Index("idx_fact_confidence", "confidence_score"),
        Index("idx_fact_verified", "verified"),
        CheckConstraint("confidence_score >= 0.0 AND confidence_score <= 1.0", name="valid_confidence"),
        CheckConstraint("nli_score IS NULL OR (nli_score >= 0.0 AND nli_score <= 1.0)", name="valid_nli_score"),
    )

    def __repr__(self) -> str:
        return f"<AtomicClinicalFact(id={self.id}, type={self.entity_type}, name={self.entity_name})>"


class InferredFact(Base, TimestampMixin):
    """Facts inferred through clinical reasoning and rules"""
    __tablename__ = "inferred_facts"

    # Primary key
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    # Foreign key
    patient_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("patients.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )

    # Inference details
    fact_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    fact_description: Mapped[str] = mapped_column(Text, nullable=False)
    inference_rule: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    rule_category: Mapped[str] = mapped_column(String(50), nullable=False)

    # Confidence
    confidence_score: Mapped[float] = mapped_column(Float, nullable=False)

    # Supporting evidence (references to clinical facts)
    supporting_fact_ids: Mapped[List[int]] = mapped_column(JSON, nullable=False)
    evidence_summary: Mapped[str] = mapped_column(Text, nullable=False)

    # Clinical significance
    severity: Mapped[str] = mapped_column(String(20), nullable=False)
    requires_action: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    action_items: Mapped[Optional[List[str]]] = mapped_column(JSON)

    # Status
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    resolved_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    resolved_by: Mapped[Optional[str]] = mapped_column(String(200))

    # Relationships
    patient: Mapped["Patient"] = relationship("Patient")

    # Constraints
    __table_args__ = (
        Index("idx_inferred_patient_type", "patient_id", "fact_type"),
        Index("idx_inferred_rule", "inference_rule"),
        Index("idx_inferred_active", "is_active"),
        CheckConstraint("confidence_score >= 0.0 AND confidence_score <= 1.0", name="valid_confidence"),
    )

    def __repr__(self) -> str:
        return f"<InferredFact(id={self.id}, type={self.fact_type}, rule={self.inference_rule})>"


# =============================================================================
# Clinical Alert Models
# =============================================================================

class ClinicalAlert(Base, TimestampMixin):
    """Clinical safety alerts and warnings"""
    __tablename__ = "clinical_alerts"

    # Primary key
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    # Foreign key
    patient_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("patients.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )

    # Alert details
    alert_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    category: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    severity: Mapped[str] = mapped_column(String(20), nullable=False, index=True)

    title: Mapped[str] = mapped_column(String(200), nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    recommendation: Mapped[Optional[str]] = mapped_column(Text)

    # Clinical rule that generated this alert
    triggered_by_rule: Mapped[str] = mapped_column(String(100), nullable=False)
    rule_logic: Mapped[str] = mapped_column(Text, nullable=False)

    # Supporting evidence
    evidence_fact_ids: Mapped[List[int]] = mapped_column(JSON, nullable=False)
    evidence_summary: Mapped[str] = mapped_column(Text, nullable=False)

    # Status
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False, index=True)
    acknowledged: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    acknowledged_by: Mapped[Optional[str]] = mapped_column(String(200))
    acknowledged_at: Mapped[Optional[datetime]] = mapped_column(DateTime)

    resolved: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    resolved_by: Mapped[Optional[str]] = mapped_column(String(200))
    resolved_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    resolution_notes: Mapped[Optional[str]] = mapped_column(Text)

    # Timestamps
    alert_timestamp: Mapped[datetime] = mapped_column(DateTime, nullable=False, index=True)
    expires_at: Mapped[Optional[datetime]] = mapped_column(DateTime)

    # Relationships
    patient: Mapped["Patient"] = relationship("Patient", back_populates="clinical_alerts")

    # Constraints
    __table_args__ = (
        Index("idx_alert_patient_severity", "patient_id", "severity", "is_active"),
        Index("idx_alert_category_active", "category", "is_active"),
        Index("idx_alert_timestamp", "alert_timestamp"),
    )

    def __repr__(self) -> str:
        return f"<ClinicalAlert(id={self.id}, type={self.alert_type}, severity={self.severity})>"


# =============================================================================
# Validation Models
# =============================================================================

class ValidationResult(Base, TimestampMixin):
    """Validation results for extracted clinical data"""
    __tablename__ = "validation_results"

    # Primary key
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    # Foreign keys
    patient_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("patients.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    document_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("documents.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )

    # Validation timestamp
    validation_timestamp: Mapped[datetime] = mapped_column(DateTime, nullable=False, index=True)
    validation_version: Mapped[str] = mapped_column(String(20), nullable=False)

    # Scores (0-100)
    completeness_score: Mapped[float] = mapped_column(Float, nullable=False)
    accuracy_score: Mapped[float] = mapped_column(Float, nullable=False)
    temporal_coherence_score: Mapped[float] = mapped_column(Float, nullable=False)
    contradiction_score: Mapped[float] = mapped_column(Float, nullable=False)
    overall_quality_score: Mapped[float] = mapped_column(Float, nullable=False)

    # Status flags
    safe_for_clinical_use: Mapped[bool] = mapped_column(Boolean, nullable=False, index=True)
    requires_review: Mapped[bool] = mapped_column(Boolean, nullable=False, index=True)

    # Issues found
    issues: Mapped[List[dict]] = mapped_column(JSON, nullable=False)
    critical_issues_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    warnings_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    info_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    # Missing data
    missing_required_fields: Mapped[List[str]] = mapped_column(JSON, default=list)
    missing_expected_entities: Mapped[List[str]] = mapped_column(JSON, default=list)

    # Contradictions detected
    contradictions_found: Mapped[List[dict]] = mapped_column(JSON, default=list)

    # Temporal issues
    temporal_conflicts: Mapped[List[dict]] = mapped_column(JSON, default=list)
    impossible_sequences: Mapped[List[dict]] = mapped_column(JSON, default=list)

    # Human review
    reviewed: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    reviewed_by: Mapped[Optional[str]] = mapped_column(String(200))
    reviewed_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    review_notes: Mapped[Optional[str]] = mapped_column(Text)

    # Relationships
    patient: Mapped["Patient"] = relationship("Patient")
    document: Mapped["Document"] = relationship("Document", back_populates="validation_results")

    # Constraints
    __table_args__ = (
        Index("idx_validation_patient", "patient_id", "validation_timestamp"),
        Index("idx_validation_document", "document_id"),
        Index("idx_validation_safe", "safe_for_clinical_use"),
        Index("idx_validation_review", "requires_review", "reviewed"),
        CheckConstraint("completeness_score >= 0.0 AND completeness_score <= 100.0", name="valid_completeness"),
        CheckConstraint("accuracy_score >= 0.0 AND accuracy_score <= 100.0", name="valid_accuracy"),
        CheckConstraint("temporal_coherence_score >= 0.0 AND temporal_coherence_score <= 100.0", name="valid_temporal"),
        CheckConstraint("overall_quality_score >= 0.0 AND overall_quality_score <= 100.0", name="valid_overall"),
    )

    def __repr__(self) -> str:
        return f"<ValidationResult(id={self.id}, patient_id={self.patient_id}, score={self.overall_quality_score:.1f})>"


# =============================================================================
# Temporal Models
# =============================================================================

class TemporalEvent(Base, TimestampMixin):
    """Temporal events in patient timeline"""
    __tablename__ = "temporal_events"

    # Primary key
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    # Foreign key
    patient_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("patients.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )

    # Event details
    event_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    event_name: Mapped[str] = mapped_column(String(500), nullable=False)
    event_description: Mapped[str] = mapped_column(Text, nullable=False)

    # Timestamps
    event_timestamp: Mapped[datetime] = mapped_column(DateTime, nullable=False, index=True)
    event_date_only: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    # Temporal context
    pod: Mapped[Optional[int]] = mapped_column(Integer)  # Post-operative day
    hospital_day: Mapped[Optional[int]] = mapped_column(Integer)
    relative_time: Mapped[Optional[str]] = mapped_column(String(100))

    # Related facts
    related_fact_ids: Mapped[List[int]] = mapped_column(JSON, default=list)

    # Confidence
    confidence_score: Mapped[float] = mapped_column(Float, nullable=False)

    # Source
    source_document_id: Mapped[Optional[int]] = mapped_column(
        Integer,
        ForeignKey("documents.id", ondelete="SET NULL")
    )

    # Relationships
    patient: Mapped["Patient"] = relationship("Patient")

    # Constraints
    __table_args__ = (
        Index("idx_temporal_patient_time", "patient_id", "event_timestamp"),
        Index("idx_temporal_type", "event_type"),
        Index("idx_temporal_pod", "pod"),
        CheckConstraint("confidence_score >= 0.0 AND confidence_score <= 1.0", name="valid_confidence"),
    )

    def __repr__(self) -> str:
        return f"<TemporalEvent(id={self.id}, type={self.event_type}, timestamp={self.event_timestamp})>"


# =============================================================================
# Summary Generation Models
# =============================================================================

class GeneratedSummary(Base, TimestampMixin):
    """Generated clinical summaries"""
    __tablename__ = "generated_summaries"

    # Primary key
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    # Foreign key
    patient_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("patients.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )

    # Summary type
    summary_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    format: Mapped[str] = mapped_column(String(20), nullable=False)

    # Content
    summary_text: Mapped[str] = mapped_column(Text, nullable=False)
    structured_summary: Mapped[dict] = mapped_column(JSON, nullable=False)

    # Generation metadata
    generation_method: Mapped[str] = mapped_column(String(50), nullable=False)
    llm_model: Mapped[Optional[str]] = mapped_column(String(100))
    llm_provider: Mapped[Optional[str]] = mapped_column(String(50))
    tokens_used: Mapped[Optional[int]] = mapped_column(Integer)
    generation_time_ms: Mapped[Optional[int]] = mapped_column(Integer)

    # Source data
    source_document_ids: Mapped[List[int]] = mapped_column(JSON, nullable=False)
    source_fact_ids: Mapped[List[int]] = mapped_column(JSON, nullable=False)
    facts_included: Mapped[int] = mapped_column(Integer, nullable=False)

    # Quality metrics
    completeness_score: Mapped[Optional[float]] = mapped_column(Float)
    factual_accuracy_score: Mapped[Optional[float]] = mapped_column(Float)

    # Status
    is_current: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False, index=True)
    superseded_by_id: Mapped[Optional[int]] = mapped_column(
        Integer,
        ForeignKey("generated_summaries.id", ondelete="SET NULL")
    )

    # Review
    reviewed: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    reviewed_by: Mapped[Optional[str]] = mapped_column(String(200))
    reviewed_at: Mapped[Optional[datetime]] = mapped_column(DateTime)

    # Relationships
    patient: Mapped["Patient"] = relationship("Patient")

    # Constraints
    __table_args__ = (
        Index("idx_summary_patient_type", "patient_id", "summary_type", "is_current"),
        Index("idx_summary_timestamp", "created_at"),
    )

    def __repr__(self) -> str:
        return f"<GeneratedSummary(id={self.id}, patient_id={self.patient_id}, type={self.summary_type})>"


# =============================================================================
# Audit Log Model
# =============================================================================

class AuditLog(Base):
    """Audit log for all system actions"""
    __tablename__ = "audit_logs"

    # Primary key
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    # Timestamp
    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
        index=True
    )

    # User/system information
    user_id: Mapped[Optional[str]] = mapped_column(String(100), index=True)
    username: Mapped[Optional[str]] = mapped_column(String(200))

    # Action details
    action: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    resource_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    resource_id: Mapped[Optional[int]] = mapped_column(Integer)

    # Request details
    ip_address: Mapped[Optional[str]] = mapped_column(String(45))
    user_agent: Mapped[Optional[str]] = mapped_column(String(500))
    request_method: Mapped[Optional[str]] = mapped_column(String(10))
    request_path: Mapped[Optional[str]] = mapped_column(String(500))

    # Changes
    changes: Mapped[Optional[dict]] = mapped_column(JSON)
    old_values: Mapped[Optional[dict]] = mapped_column(JSON)
    new_values: Mapped[Optional[dict]] = mapped_column(JSON)

    # Result
    status: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    error_message: Mapped[Optional[str]] = mapped_column(Text)

    # Constraints
    __table_args__ = (
        Index("idx_audit_timestamp", "timestamp"),
        Index("idx_audit_user_action", "user_id", "action"),
        Index("idx_audit_resource", "resource_type", "resource_id"),
    )

    def __repr__(self) -> str:
        return f"<AuditLog(id={self.id}, action={self.action}, resource={self.resource_type})>"
