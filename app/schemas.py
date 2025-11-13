"""
NeuroscribeAI - Comprehensive Clinical Data Schemas
Neurosurgical-grade Pydantic models for structured data extraction
"""

from pydantic import BaseModel, Field, field_validator, computed_field
from typing import Optional, List, Dict, Any, Literal
from datetime import datetime, date
from enum import Enum


# ============================================================================
# Enumerations - Neurosurgical Domain
# ============================================================================

class Laterality(str, Enum):
    """Anatomical laterality"""
    LEFT = "left"
    RIGHT = "right"
    BILATERAL = "bilateral"
    MIDLINE = "midline"
    UNKNOWN = "unknown"


class BrainRegion(str, Enum):
    """Major brain regions"""
    FRONTAL = "frontal"
    PARIETAL = "parietal"
    TEMPORAL = "temporal"
    OCCIPITAL = "occipital"
    CEREBELLUM = "cerebellum"
    BRAINSTEM = "brainstem"
    BASAL_GANGLIA = "basal_ganglia"
    THALAMUS = "thalamus"
    CORPUS_CALLOSUM = "corpus_callosum"
    VENTRICLES = "ventricles"
    PITUITARY = "pituitary"
    PINEAL = "pineal"
    SPINAL_CORD = "spinal_cord"


class SpinalLevel(str, Enum):
    """Spinal cord levels"""
    C1 = "C1"
    C2 = "C2"
    C3 = "C3"
    C4 = "C4"
    C5 = "C5"
    C6 = "C6"
    C7 = "C7"
    T1 = "T1"
    T2 = "T2"
    T3 = "T3"
    T4 = "T4"
    T5 = "T5"
    T6 = "T6"
    T7 = "T7"
    T8 = "T8"
    T9 = "T9"
    T10 = "T10"
    T11 = "T11"
    T12 = "T12"
    L1 = "L1"
    L2 = "L2"
    L3 = "L3"
    L4 = "L4"
    L5 = "L5"
    S1 = "S1"
    S2 = "S2"
    S3 = "S3"
    S4 = "S4"
    S5 = "S5"


class MotorStrength(str, Enum):
    """Motor strength grading (0/5 to 5/5)"""
    ZERO = "0/5"
    ONE = "1/5"
    TWO = "2/5"
    THREE = "3/5"
    FOUR_MINUS = "4-/5"
    FOUR = "4/5"
    FOUR_PLUS = "4+/5"
    FIVE_MINUS = "5-/5"
    FIVE = "5/5"


class MedicationRoute(str, Enum):
    """Medication administration routes"""
    PO = "PO"
    IV = "IV"
    IM = "IM"
    SUBCUTANEOUS = "SubQ"
    TOPICAL = "Topical"
    RECTAL = "PR"
    SUBLINGUAL = "SL"
    TRANSDERMAL = "TD"
    INHALATION = "INH"
    INTRATHECAL = "IT"


class MedicationFrequency(str, Enum):
    """Medication frequency"""
    ONCE = "Once"
    DAILY = "Daily"
    BID = "BID"
    TID = "TID"
    QID = "QID"
    Q4H = "Q4H"
    Q6H = "Q6H"
    Q8H = "Q8H"
    Q12H = "Q12H"
    QHS = "QHS"
    QAM = "QAM"
    QPM = "QPM"
    WEEKLY = "Weekly"
    PRN = "PRN"


class EntityType(str, Enum):
    """Clinical entity types"""
    DIAGNOSIS = "DIAGNOSIS"
    PROCEDURE = "PROCEDURE"
    MEDICATION = "MEDICATION"
    LAB_VALUE = "LAB_VALUE"
    IMAGING = "IMAGING"
    IMAGING_FINDING = "IMAGING_FINDING"
    PHYSICAL_EXAM = "PHYSICAL_EXAM"
    NEURO_EXAM_FINDING = "NEURO_EXAM_FINDING"
    VITAL_SIGN = "VITAL_SIGN"
    SYMPTOM = "SYMPTOM"
    COMPLICATION = "COMPLICATION"
    ALLERGY = "ALLERGY"
    FAMILY_HISTORY = "FAMILY_HISTORY"
    ADMINISTRATIVE = "ADMINISTRATIVE"


class AlertSeverity(str, Enum):
    """Clinical alert severity levels"""
    CRITICAL = "CRITICAL"
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"
    INFO = "INFO"


class AlertCategory(str, Enum):
    """Clinical alert categories"""
    PROPHYLAXIS = "PROPHYLAXIS"
    MEDICATION_MANAGEMENT = "MEDICATION_MANAGEMENT"
    DEVICE_MANAGEMENT = "DEVICE_MANAGEMENT"
    MONITORING = "MONITORING"
    COMPLICATIONS = "COMPLICATIONS"
    DISCHARGE_PLANNING = "DISCHARGE_PLANNING"


# ============================================================================
# Anatomical Context Models
# ============================================================================

class AnatomicalContext(BaseModel):
    """Detailed anatomical location information"""
    laterality: Optional[Laterality] = None
    brain_region: Optional[BrainRegion] = None
    specific_structure: Optional[str] = Field(None, description="Specific anatomical structure")
    spinal_levels: Optional[List[SpinalLevel]] = Field(default_factory=list)
    coordinates_3d: Optional[Dict[str, float]] = Field(None, description="X, Y, Z coordinates if available")
    proximity_to: Optional[List[str]] = Field(default_factory=list, description="Adjacent structures")
    crosses_midline: Optional[bool] = None
    size_mm: Optional[float] = Field(None, ge=0, description="Size in millimeters")
    volume_cc: Optional[float] = Field(None, ge=0, description="Volume in cubic centimeters")

    class Config:
        json_schema_extra = {
            "example": {
                "laterality": "left",
                "brain_region": "frontal",
                "specific_structure": "precentral gyrus",
                "size_mm": 45.0,
                "crosses_midline": False
            }
        }


# ============================================================================
# Neurological Examination Models
# ============================================================================

class GlasgowComaScale(BaseModel):
    """Glasgow Coma Scale scoring"""
    eye_opening: Literal[1, 2, 3, 4] = Field(..., description="1-4 scale")
    verbal_response: Literal[1, 2, 3, 4, 5] = Field(..., description="1-5 scale")
    motor_response: Literal[1, 2, 3, 4, 5, 6] = Field(..., description="1-6 scale")

    @computed_field
    @property
    def total_score(self) -> int:
        """Calculate total GCS score"""
        return self.eye_opening + self.verbal_response + self.motor_response

    @field_validator('eye_opening', 'verbal_response', 'motor_response')
    @classmethod
    def validate_scores(cls, v, info):
        """Validate GCS component scores"""
        field_name = info.field_name
        if field_name == 'eye_opening' and not 1 <= v <= 4:
            raise ValueError("Eye opening must be 1-4")
        elif field_name == 'verbal_response' and not 1 <= v <= 5:
            raise ValueError("Verbal response must be 1-5")
        elif field_name == 'motor_response' and not 1 <= v <= 6:
            raise ValueError("Motor response must be 1-6")
        return v


class MotorExam(BaseModel):
    """Detailed motor examination"""
    # Upper extremities
    right_deltoid: Optional[MotorStrength] = None
    right_biceps: Optional[MotorStrength] = None
    right_triceps: Optional[MotorStrength] = None
    right_wrist_extension: Optional[MotorStrength] = None
    right_wrist_flexion: Optional[MotorStrength] = None
    right_grip: Optional[MotorStrength] = None
    right_finger_abduction: Optional[MotorStrength] = None

    left_deltoid: Optional[MotorStrength] = None
    left_biceps: Optional[MotorStrength] = None
    left_triceps: Optional[MotorStrength] = None
    left_wrist_extension: Optional[MotorStrength] = None
    left_wrist_flexion: Optional[MotorStrength] = None
    left_grip: Optional[MotorStrength] = None
    left_finger_abduction: Optional[MotorStrength] = None

    # Lower extremities
    right_iliopsoas: Optional[MotorStrength] = None
    right_quadriceps: Optional[MotorStrength] = None
    right_hamstrings: Optional[MotorStrength] = None
    right_dorsiflexion: Optional[MotorStrength] = None
    right_plantarflexion: Optional[MotorStrength] = None

    left_iliopsoas: Optional[MotorStrength] = None
    left_quadriceps: Optional[MotorStrength] = None
    left_hamstrings: Optional[MotorStrength] = None
    left_dorsiflexion: Optional[MotorStrength] = None
    left_plantarflexion: Optional[MotorStrength] = None

    # Summary
    symmetric: Optional[bool] = None
    focal_weakness_location: Optional[str] = None


class CranialNerveExam(BaseModel):
    """Cranial nerve examination findings"""
    cn_ii_pupils: Optional[str] = Field(None, description="Pupil size and reactivity")
    cn_ii_visual_fields: Optional[str] = None
    cn_iii_iv_vi_eom: Optional[str] = Field(None, description="Extraocular movements")
    cn_v_facial_sensation: Optional[str] = None
    cn_vii_face: Optional[str] = Field(None, description="Facial symmetry and strength")
    cn_viii_hearing: Optional[str] = None
    cn_ix_x_palate: Optional[str] = None
    cn_xi_scm_trapezius: Optional[str] = Field(None, description="SCM and trapezius strength")
    cn_xii_tongue: Optional[str] = None


class SensoryExam(BaseModel):
    """Sensory examination"""
    light_touch: Optional[str] = None
    pinprick: Optional[str] = None
    proprioception: Optional[str] = None
    vibration: Optional[str] = None
    temperature: Optional[str] = None
    sensory_level: Optional[SpinalLevel] = None
    symmetric: Optional[bool] = None


class ReflexExam(BaseModel):
    """Deep tendon reflex examination"""
    biceps_right: Optional[str] = None
    biceps_left: Optional[str] = None
    triceps_right: Optional[str] = None
    triceps_left: Optional[str] = None
    brachioradialis_right: Optional[str] = None
    brachioradialis_left: Optional[str] = None
    patellar_right: Optional[str] = None
    patellar_left: Optional[str] = None
    achilles_right: Optional[str] = None
    achilles_left: Optional[str] = None
    babinski_right: Optional[str] = Field(None, description="Upgoing/downgoing/equivocal")
    babinski_left: Optional[str] = None
    clonus_present: Optional[bool] = None


class NeuroExamDetail(BaseModel):
    """Complete neurological examination"""
    mental_status: Optional[str] = None
    gcs: Optional[GlasgowComaScale] = None
    gcs_verbal_intubated: Optional[bool] = Field(False, description="True if patient intubated")
    motor_exam: Optional[MotorExam] = None
    cranial_nerves: Optional[CranialNerveExam] = None
    sensory_exam: Optional[SensoryExam] = None
    reflex_exam: Optional[ReflexExam] = None
    coordination: Optional[str] = None
    gait: Optional[str] = None
    special_tests: Optional[Dict[str, str]] = Field(default_factory=dict)


# ============================================================================
# Clinical Detail Models
# ============================================================================

class MedicationDetail(BaseModel):
    """Comprehensive medication information"""
    generic_name: str
    brand_name: Optional[str] = None
    rxnorm_cui: Optional[str] = Field(None, description="RxNorm concept ID")
    dose_value: Optional[float] = Field(None, ge=0)
    dose_unit: Optional[str] = None
    route: Optional[MedicationRoute] = None
    frequency: Optional[MedicationFrequency] = None
    prn_indication: Optional[str] = Field(None, description="PRN reason")
    as_needed: bool = False
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    duration_days: Optional[int] = Field(None, ge=0)
    indication: Optional[str] = None
    taper_schedule: Optional[str] = None
    special_instructions: Optional[str] = None


class ImagingFinding(BaseModel):
    """Imaging study findings with measurements"""
    modality: str = Field(..., description="CT, MRI, angiogram, etc.")
    date_performed: Optional[date] = None
    size_mm: Optional[float] = Field(None, ge=0)
    volume_cc: Optional[float] = Field(None, ge=0)
    midline_shift_mm: Optional[float] = Field(None, ge=0)
    hemorrhage: Optional[bool] = None
    edema: Optional[bool] = None
    mass_effect: Optional[bool] = None
    enhancement: Optional[str] = Field(None, description="None/minimal/moderate/avid")
    hydrocephalus: Optional[bool] = None
    description: Optional[str] = None


class ProcedureDetail(BaseModel):
    """Surgical procedure details"""
    procedure_name: str
    date_performed: Optional[date] = None
    laterality: Optional[Laterality] = None
    approach: Optional[str] = Field(None, description="Surgical approach")
    surgeon: Optional[str] = None
    assistant: Optional[str] = None
    anesthesia_type: Optional[str] = None
    duration_minutes: Optional[int] = Field(None, ge=0)
    ebl_ml: Optional[float] = Field(None, ge=0, description="Estimated blood loss")
    complications: Optional[List[str]] = Field(default_factory=list)
    findings: Optional[str] = None
    specimens: Optional[List[str]] = Field(default_factory=list)


class LabValue(BaseModel):
    """Laboratory value with reference range"""
    test_name: str
    value: float
    unit: Optional[str] = None  # Made optional since not all labs have units
    reference_range_low: Optional[float] = None
    reference_range_high: Optional[float] = None
    normal: Optional[bool] = None
    date_performed: Optional[date] = None
    critical: bool = False


class TemporalContext(BaseModel):
    """Rich temporal information"""
    expression: Optional[str] = Field(None, description="Original temporal expression")
    resolved_datetime: Optional[datetime] = None
    relative_to: Optional[str] = Field(None, description="Relative to event")
    pod: Optional[int] = Field(None, description="Post-operative day")
    hospital_day: Optional[int] = Field(None, description="Hospital day")
    confidence: float = Field(1.0, ge=0.0, le=1.0)


# ============================================================================
# Core Clinical Fact Model
# ============================================================================

class AtomicClinicalFact(BaseModel):
    """
    Core atomic clinical fact with enhanced detail schemas
    Represents a single, verifiable clinical assertion
    """
    # Core identification
    entity_type: EntityType
    entity_name: str = Field(..., description="Primary entity name")
    extracted_text: str = Field(..., description="Raw extracted text")
    source_snippet: str = Field(..., description="Source text context")

    # Confidence and timestamps
    confidence_score: float = Field(0.8, ge=0.0, le=1.0)
    extraction_method: str = Field("hybrid", description="ner/llm/hybrid/rule")
    timestamp: Optional[datetime] = Field(None, description="Document timestamp")
    resolved_timestamp: Optional[datetime] = Field(None, description="Resolved clinical timestamp")

    # Detailed schemas (optional based on entity type)
    anatomical_context: Optional[AnatomicalContext] = None
    medication_detail: Optional[MedicationDetail] = None
    imaging_detail: Optional[ImagingFinding] = None
    procedure_detail: Optional[ProcedureDetail] = None
    lab_value: Optional[LabValue] = None
    neuro_exam_detail: Optional[NeuroExamDetail] = None
    temporal_context: Optional[TemporalContext] = None

    # Metadata
    is_negated: bool = False
    is_historical: bool = False
    is_family_history: bool = False
    attributes: Dict[str, Any] = Field(default_factory=dict)

    # Character positions in source text
    char_start: Optional[int] = Field(None, description="Start position in source text")
    char_end: Optional[int] = Field(None, description="End position in source text")


# ============================================================================
# Clinical Alert Models
# ============================================================================

class ClinicalAlert(BaseModel):
    """Clinical safety alert"""
    category: AlertCategory
    severity: AlertSeverity
    message: str
    recommendation: str
    rule_name: str
    patient_id: int
    created_at: datetime = Field(default_factory=datetime.utcnow)
    resolved: bool = False
    acknowledged_by: Optional[str] = None


# ============================================================================
# Validation Models
# ============================================================================

class ValidationSeverity(str, Enum):
    """Validation issue severity levels"""
    CRITICAL = "CRITICAL"
    WARNING = "WARNING"
    INFO = "INFO"


class ValidationIssue(BaseModel):
    """Validation issue"""
    severity: Literal["CRITICAL", "WARNING", "INFO"]
    issue_type: str
    message: str
    field: Optional[str] = None
    suggestion: Optional[str] = None


class ValidationReport(BaseModel):
    """Comprehensive validation report"""
    patient_id: int
    validation_timestamp: datetime = Field(default_factory=datetime.utcnow)

    # Scores (0-100)
    completeness_score: float = Field(0.0, ge=0.0, le=100.0)
    accuracy_score: float = Field(0.0, ge=0.0, le=100.0)
    temporal_coherence_score: float = Field(0.0, ge=0.0, le=100.0)
    overall_quality_score: float = Field(0.0, ge=0.0, le=100.0)

    # Issues
    issues: List[ValidationIssue] = Field(default_factory=list)

    # Safety determination
    safe_for_clinical_use: bool = False
    requires_review: bool = True

    @computed_field
    @property
    def critical_issues_count(self) -> int:
        """Count critical issues"""
        return len([i for i in self.issues if i.severity == "CRITICAL"])


# ============================================================================
# Timeline Models
# ============================================================================

class PatientTimeline(BaseModel):
    """Patient clinical timeline"""
    patient_id: int
    events: List[Dict[str, Any]] = Field(default_factory=list)
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None


# ============================================================================
# Summary Generation Models
# ============================================================================

class SummarySection(BaseModel):
    """Section of a clinical summary"""
    title: str
    content: str
    section_type: Optional[str] = None
    facts_count: int = 0


class SummaryRequest(BaseModel):
    """Request for summary generation - contains all data for the summarization job"""
    patient_mrn: str
    patient_id: Optional[int] = None
    summary_type: Literal["discharge_summary", "progress_note", "procedure_note"] = "discharge_summary"
    format: Literal["markdown", "json", "structured"] = "markdown"
    include_timeline: bool = True
    include_references: bool = True
    include_alerts: bool = True
    max_length: Optional[int] = Field(None, ge=500, le=10000)

    # Embedded data for summarization
    facts: List["AtomicClinicalFact"] = Field(default_factory=list)
    alerts: Optional[List["ClinicalAlert"]] = Field(default_factory=list)
    patient_data: Optional[Dict[str, Any]] = Field(default_factory=dict)
    patient_context: Optional[Dict[str, Any]] = Field(default_factory=dict)


class SummaryResponse(BaseModel):
    """Generated summary with metadata"""
    patient_id: int
    summary_type: str
    summary_text: str
    sections: List[SummarySection] = Field(default_factory=list)
    facts_included: int
    generation_timestamp: datetime = Field(default_factory=datetime.utcnow)
    confidence_score: float = Field(0.0, ge=0.0, le=1.0)
    metadata: Dict[str, Any] = Field(default_factory=dict)

    # Legacy fields for compatibility
    generated_at: Optional[datetime] = None
    word_count: Optional[int] = None
    verified_claims_count: Optional[int] = None
    unverified_claims: List[str] = Field(default_factory=list)
    safety_warnings: List[str] = Field(default_factory=list)
    missing_critical_data: List[str] = Field(default_factory=list)

    @field_validator("generated_at", mode="before")
    @classmethod
    def set_generated_at(cls, v, info):
        return v or info.data.get("generation_timestamp") or datetime.utcnow()

    @field_validator("word_count", mode="before")
    @classmethod
    def calculate_word_count(cls, v, info):
        if v is not None:
            return v
        summary_text = info.data.get("summary_text", "")
        return len(summary_text.split()) if summary_text else 0


# ============================================================================
# Document Classification
# ============================================================================

class DocumentClassification(BaseModel):
    """Document type classification"""
    document_type: str
    confidence: float = Field(0.8, ge=0.0, le=1.0)
    detected_sections: List[str] = Field(default_factory=list)
