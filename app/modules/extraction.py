"""
NeuroscribeAI Extraction Engine
Hybrid NER + LLM + Rule-based extraction for 95%+ recall
"""

import re
import logging
from typing import List, Dict, Optional, Tuple, Any
from datetime import datetime
import spacy
from spacy.tokens import Doc, Span
import scispacy
from transformers import AutoTokenizer, AutoModelForTokenClassification, pipeline

from app.schemas import (
    AtomicClinicalFact, EntityType, Laterality, BrainRegion,
    AnatomicalContext, MedicationDetail, MedicationRoute, MedicationFrequency,
    MotorStrength, MotorExam, GlasgowComaScale, NeuroExamDetail,
    ImagingFinding, ProcedureDetail, LabValue, TemporalContext
)
from app.config import settings

logger = logging.getLogger(__name__)


# =============================================================================
# NER Models Loading
# =============================================================================

class NERModels:
    """Container for NER models"""

    def __init__(self):
        self.spacy_model: Optional[spacy.Language] = None
        self.scispacy_model: Optional[spacy.Language] = None
        self.biobert_ner: Optional[Any] = None
        self.loaded = False
        self.load_errors: List[str] = []

    def load_models(self):
        """Load all NER models with graceful fallback"""
        if self.loaded:
            return

        logger.info("="*60)
        logger.info("Loading NER Models")
        logger.info("="*60)

        models_loaded = 0
        total_models = 2 + (1 if settings.extraction_use_llm else 0)

        try:
            # Load spaCy general model
            logger.info("Loading spaCy en_core_web_sm model...")
            try:
                self.spacy_model = spacy.load("en_core_web_sm")
                logger.info("✓ spaCy en_core_web_sm loaded successfully")
                models_loaded += 1
            except OSError as e:
                error_msg = (
                    "Failed to load spaCy model 'en_core_web_sm'. "
                    "Please run: python -m spacy download en_core_web_sm"
                )
                logger.error(f"✗ {error_msg}")
                self.load_errors.append(error_msg)

            # Load scispaCy medical model
            logger.info("Loading scispaCy en_ner_bc5cdr_md model...")
            try:
                self.scispacy_model = spacy.load("en_ner_bc5cdr_md")
                logger.info("✓ scispaCy en_ner_bc5cdr_md loaded successfully")
                models_loaded += 1
            except OSError as e:
                error_msg = (
                    "Failed to load scispaCy model 'en_ner_bc5cdr_md'. "
                    "Please run: pip install https://s3-us-west-2.amazonaws.com/"
                    "ai2-s2-scispacy/releases/v0.5.3/en_ner_bc5cdr_md-0.5.3.tar.gz"
                )
                logger.error(f"✗ {error_msg}")
                self.load_errors.append(error_msg)

            # Load BioBERT NER (optional, only if LLM extraction enabled)
            if settings.extraction_use_llm:
                logger.info("Loading BioBERT NER model (this may take a while on first run)...")
                try:
                    self.biobert_ner = pipeline(
                        "ner",
                        model="dmis-lab/biobert-base-cased-v1.2",
                        aggregation_strategy="simple"
                    )
                    logger.info("✓ BioBERT NER loaded successfully")
                    models_loaded += 1
                except Exception as e:
                    error_msg = f"Failed to load BioBERT model: {str(e)}"
                    logger.warning(f"⚠ {error_msg}")
                    logger.warning("  Continuing without BioBERT. LLM extraction will be limited.")
                    self.load_errors.append(error_msg)

            # Check if we have at least one model loaded
            if models_loaded == 0:
                error_msg = (
                    "No NER models could be loaded. Please run './scripts/download_models.sh' "
                    "or see scripts/README.md for manual installation instructions."
                )
                logger.error(f"✗ {error_msg}")
                raise RuntimeError(error_msg)

            self.loaded = True
            logger.info("="*60)
            logger.info(f"✓ Model loading complete: {models_loaded}/{total_models} models loaded")
            if self.load_errors:
                logger.warning(f"  {len(self.load_errors)} models failed to load")
                logger.warning("  System will use available models with reduced functionality")
            logger.info("="*60)

        except Exception as e:
            if not self.loaded:
                logger.error(f"✗ Critical error loading NER models: {e}")
                logger.error("  See logs above for details")
                raise

    def get_status(self) -> Dict[str, Any]:
        """Get status of loaded models"""
        return {
            "loaded": self.loaded,
            "models": {
                "spacy_general": self.spacy_model is not None,
                "scispacy_medical": self.scispacy_model is not None,
                "biobert_ner": self.biobert_ner is not None
            },
            "errors": self.load_errors
        }


# Global NER models instance
ner_models = NERModels()


# =============================================================================
# Regular Expression Patterns
# =============================================================================

class ClinicalPatterns:
    """Regular expression patterns for clinical entity extraction"""

    # Laterality patterns
    LATERALITY = re.compile(
        r'\b(left|right|bilateral|midline|contralateral|ipsilateral)\b',
        re.IGNORECASE
    )

    # Brain regions
    BRAIN_REGION = re.compile(
        r'\b(frontal|parietal|temporal|occipital|cerebellum|brainstem|thalamus|'
        r'basal ganglia|corpus callosum|ventricle|hippocampus|amygdala|insula)\b',
        re.IGNORECASE
    )

    # Spinal levels
    SPINAL_LEVEL = re.compile(
        r'\b([CT])\s*(\d{1,2})(?:\s*-\s*([CT])\s*(\d{1,2}))?\b'
    )

    # Motor strength (e.g., "5/5", "4-/5", "3+/5")
    MOTOR_STRENGTH = re.compile(
        r'\b(\d)([+-]?)/5\b'
    )

    # Glasgow Coma Scale
    GCS_PATTERN = re.compile(
        r'\bGCS\s*(?:of\s*)?(\d{1,2})(?:\s*\(E\s*(\d)\s*V\s*(\d)\s*M\s*(\d)\))?',
        re.IGNORECASE
    )

    # Medication dosing
    MEDICATION_DOSE = re.compile(
        r'(\d+(?:\.\d+)?)\s*(mg|g|mcg|μg|units?|mL|L|%)\b',
        re.IGNORECASE
    )

    # Medication frequency
    MEDICATION_FREQ = re.compile(
        r'\b(qd|bid|tid|qid|q\d+h|daily|twice daily|three times daily|'
        r'every \d+ hours?|prn|as needed)\b',
        re.IGNORECASE
    )

    # Lab values
    LAB_VALUE = re.compile(
        r'\b([A-Z][A-Za-z0-9\s-]+?):\s*(\d+(?:\.\d+)?)\s*([A-Za-z/]+)?',
        re.MULTILINE
    )

    # Size measurements (e.g., "2.5 x 3.1 x 1.8 cm")
    SIZE_MEASUREMENT = re.compile(
        r'(\d+(?:\.\d+)?)\s*x\s*(\d+(?:\.\d+)?)\s*(?:x\s*(\d+(?:\.\d+)?))?\s*(mm|cm)',
        re.IGNORECASE
    )

    # Temporal expressions
    POST_OP_DAY = re.compile(
        r'\b(?:POD|post-?op(?:erative)?\s+day)\s*#?\s*(\d+)\b',
        re.IGNORECASE
    )

    HOSPITAL_DAY = re.compile(
        r'\b(?:HD|hospital\s+day)\s*#?\s*(\d+)\b',
        re.IGNORECASE
    )

    # Date patterns
    DATE_PATTERN = re.compile(
        r'\b(\d{1,2})/(\d{1,2})/(\d{2,4})\b|'
        r'\b(January|February|March|April|May|June|July|August|September|October|November|December)\s+(\d{1,2}),?\s+(\d{4})\b',
        re.IGNORECASE
    )


# =============================================================================
# Entity Extractors
# =============================================================================

class DiagnosisExtractor:
    """Extract diagnoses and pathologies"""

    @staticmethod
    def extract(doc: Doc, text: str) -> List[AtomicClinicalFact]:
        """Extract diagnoses from text"""
        facts = []

        # Extract from scispaCy NER
        for ent in doc.ents:
            if ent.label_ in ["DISEASE", "SYMPTOM"]:
                # Get anatomical context
                anatomical_context = AnatomicalContextExtractor.extract_for_span(ent)

                fact = AtomicClinicalFact(
                    entity_type=EntityType.DIAGNOSIS,
                    entity_name=ent.text,
                    extracted_text=ent.text,
                    source_snippet=text[max(0, ent.start_char-50):min(len(text), ent.end_char+50)],
                    confidence_score=0.85,
                    extraction_method="scispacy_ner",
                    anatomical_context=anatomical_context.dict() if anatomical_context else None,
                    char_start=ent.start_char,
                    char_end=ent.end_char
                )
                facts.append(fact)

        return facts


class ProcedureExtractor:
    """Extract surgical procedures and interventions"""

    # Common neurosurgical procedures
    PROCEDURES = [
        "craniotomy", "craniectomy", "cranioplasty", "burr hole", "biopsy",
        "resection", "decompression", "laminectomy", "fusion", "discectomy",
        "ventriculostomy", "EVD placement", "shunt placement", "embolization",
        "clipping", "coiling", "stereotactic biopsy", "radiosurgery"
    ]

    @staticmethod
    def extract(text: str) -> List[AtomicClinicalFact]:
        """Extract procedures from text"""
        facts = []

        for procedure in ProcedureExtractor.PROCEDURES:
            pattern = re.compile(rf'\b{procedure}\b', re.IGNORECASE)
            for match in pattern.finditer(text):
                # Get context
                start = max(0, match.start() - 100)
                end = min(len(text), match.end() + 100)
                context = text[start:end]

                # Extract anatomical context
                laterality = None
                lat_match = ClinicalPatterns.LATERALITY.search(context)
                if lat_match:
                    laterality = Laterality(lat_match.group(1).lower())

                brain_region = None
                region_match = ClinicalPatterns.BRAIN_REGION.search(context)
                if region_match:
                    try:
                        brain_region = BrainRegion(region_match.group(1).lower())
                    except ValueError:
                        pass

                anatomical_context = None
                if laterality or brain_region:
                    anatomical_context = AnatomicalContext(
                        laterality=laterality,
                        brain_region=brain_region
                    )

                procedure_detail = ProcedureDetail(
                    procedure_name=match.group(0),
                    procedure_type="surgical",
                    approach=None,
                    duration_minutes=None
                )

                fact = AtomicClinicalFact(
                    entity_type=EntityType.PROCEDURE,
                    entity_name=match.group(0),
                    extracted_text=match.group(0),
                    source_snippet=context,
                    confidence_score=0.9,
                    extraction_method="rule_based",
                    anatomical_context=anatomical_context.dict() if anatomical_context else None,
                    procedure_detail=procedure_detail.dict(),
                    char_start=match.start(),
                    char_end=match.end()
                )
                facts.append(fact)

        return facts


class MedicationExtractor:
    """Extract medications with dosing information"""

    # Common neurosurgical medications
    MEDICATIONS = {
        "dexamethasone": ("dexamethasone", "Decadron"),
        "levetiracetam": ("levetiracetam", "Keppra"),
        "phenytoin": ("phenytoin", "Dilantin"),
        "mannitol": ("mannitol", None),
        "hypertonic saline": ("hypertonic saline", None),
        "fentanyl": ("fentanyl", "Sublimaze"),
        "morphine": ("morphine", None),
        "oxycodone": ("oxycodone", "OxyContin"),
        "acetaminophen": ("acetaminophen", "Tylenol"),
        "enoxaparin": ("enoxaparin", "Lovenox"),
        "heparin": ("heparin", None),
        "warfarin": ("warfarin", "Coumadin"),
        "aspirin": ("aspirin", None),
        "clopidogrel": ("clopidogrel", "Plavix"),
    }

    @staticmethod
    def extract(text: str) -> List[AtomicClinicalFact]:
        """Extract medications from text"""
        facts = []

        for generic_name, (generic, brand) in MedicationExtractor.MEDICATIONS.items():
            # Search for medication mentions
            pattern = re.compile(rf'\b{generic_name}\b', re.IGNORECASE)
            for match in pattern.finditer(text):
                # Get context for dosing information
                start = max(0, match.start() - 50)
                end = min(len(text), match.end() + 100)
                context = text[start:end]

                # Extract dose
                dose_value = None
                dose_unit = None
                dose_match = ClinicalPatterns.MEDICATION_DOSE.search(context)
                if dose_match:
                    dose_value = float(dose_match.group(1))
                    dose_unit = dose_match.group(2).lower()

                # Extract frequency
                frequency = None
                freq_match = ClinicalPatterns.MEDICATION_FREQ.search(context)
                if freq_match:
                    freq_text = freq_match.group(1).lower()
                    if freq_text in ["qd", "daily"]:
                        frequency = MedicationFrequency.DAILY
                    elif freq_text in ["bid", "twice daily"]:
                        frequency = MedicationFrequency.BID
                    elif freq_text in ["tid", "three times daily"]:
                        frequency = MedicationFrequency.TID
                    elif freq_text in ["qid"]:
                        frequency = MedicationFrequency.QID
                    elif freq_text in ["prn", "as needed"]:
                        frequency = MedicationFrequency.PRN

                medication_detail = MedicationDetail(
                    generic_name=generic,
                    brand_name=brand,
                    dose_value=dose_value,
                    dose_unit=dose_unit,
                    frequency=frequency,
                    as_needed=(frequency == MedicationFrequency.PRN)
                )

                fact = AtomicClinicalFact(
                    entity_type=EntityType.MEDICATION,
                    entity_name=generic,
                    extracted_text=match.group(0),
                    source_snippet=context,
                    confidence_score=0.95,
                    extraction_method="rule_based",
                    medication_detail=medication_detail.dict(),
                    char_start=match.start(),
                    char_end=match.end()
                )
                facts.append(fact)

        return facts


class LabExtractor:
    """Extract laboratory values"""

    @staticmethod
    def extract(text: str) -> List[AtomicClinicalFact]:
        """Extract lab values from text"""
        facts = []

        for match in ClinicalPatterns.LAB_VALUE.finditer(text):
            lab_name = match.group(1).strip()
            value = float(match.group(2))
            unit = match.group(3) if match.group(3) else None

            # Get context
            start = max(0, match.start() - 50)
            end = min(len(text), match.end() + 50)
            context = text[start:end]

            lab_value = LabValue(
                test_name=lab_name,
                value=value,
                unit=unit,
                timestamp=None
            )

            fact = AtomicClinicalFact(
                entity_type=EntityType.LAB_VALUE,
                entity_name=lab_name,
                extracted_text=match.group(0),
                source_snippet=context,
                confidence_score=0.9,
                extraction_method="rule_based",
                lab_value=lab_value.dict(),
                char_start=match.start(),
                char_end=match.end()
            )
            facts.append(fact)

        return facts


class NeuroExamExtractor:
    """Extract neurological examination findings"""

    @staticmethod
    def extract_gcs(text: str) -> List[AtomicClinicalFact]:
        """Extract Glasgow Coma Scale scores"""
        facts = []

        for match in ClinicalPatterns.GCS_PATTERN.finditer(text):
            total = int(match.group(1))

            # Check if components are provided
            if match.group(2) and match.group(3) and match.group(4):
                eye = int(match.group(2))
                verbal = int(match.group(3))
                motor = int(match.group(4))

                gcs = GlasgowComaScale(
                    eye_opening=eye,
                    verbal_response=verbal,
                    motor_response=motor
                )
            else:
                # If only total provided, we can't create a complete GCS object
                gcs = None

            context = text[max(0, match.start()-50):min(len(text), match.end()+50)]

            neuro_exam_detail = NeuroExamDetail(
                gcs=gcs,
                mental_status=None,
                motor_exam=None
            ) if gcs else None

            fact = AtomicClinicalFact(
                entity_type=EntityType.PHYSICAL_EXAM,
                entity_name="Glasgow Coma Scale",
                extracted_text=match.group(0),
                source_snippet=context,
                confidence_score=0.95,
                extraction_method="rule_based",
                neuro_exam_detail=neuro_exam_detail.dict() if neuro_exam_detail else None,
                char_start=match.start(),
                char_end=match.end()
            )
            facts.append(fact)

        return facts

    @staticmethod
    def extract_motor_exam(text: str) -> List[AtomicClinicalFact]:
        """Extract motor examination findings"""
        facts = []

        # Common muscle groups
        muscles = {
            "deltoid": ["right_deltoid", "left_deltoid"],
            "biceps": ["right_biceps", "left_biceps"],
            "triceps": ["right_triceps", "left_triceps"],
            "wrist extensors": ["right_wrist_ext", "left_wrist_ext"],
            "grip": ["right_grip", "left_grip"],
            "iliopsoas": ["right_iliopsoas", "left_iliopsoas"],
            "quadriceps": ["right_quadriceps", "left_quadriceps"],
            "hamstrings": ["right_hamstrings", "left_hamstrings"],
            "tibialis anterior": ["right_tibialis_ant", "left_tibialis_ant"],
            "gastrocnemius": ["right_gastrocnemius", "left_gastrocnemius"]
        }

        for muscle_name, muscle_fields in muscles.items():
            pattern = re.compile(
                rf'\b(left|right|bilateral)?\s*{muscle_name}\s*[:\-]?\s*(\d[+-]?)/5',
                re.IGNORECASE
            )

            for match in pattern.finditer(text):
                laterality = match.group(1).lower() if match.group(1) else None
                strength_str = match.group(2)

                # Convert to MotorStrength enum
                try:
                    strength = MotorStrength(f"{strength_str}/5")
                except ValueError:
                    continue

                context = text[max(0, match.start()-50):min(len(text), match.end()+50)]

                motor_exam = MotorExam()
                if laterality == "right" and len(muscle_fields) > 0:
                    setattr(motor_exam, muscle_fields[0], strength)
                elif laterality == "left" and len(muscle_fields) > 1:
                    setattr(motor_exam, muscle_fields[1], strength)
                elif laterality == "bilateral":
                    if len(muscle_fields) > 0:
                        setattr(motor_exam, muscle_fields[0], strength)
                    if len(muscle_fields) > 1:
                        setattr(motor_exam, muscle_fields[1], strength)

                neuro_exam_detail = NeuroExamDetail(
                    motor_exam=motor_exam
                )

                fact = AtomicClinicalFact(
                    entity_type=EntityType.PHYSICAL_EXAM,
                    entity_name=f"{muscle_name} strength",
                    extracted_text=match.group(0),
                    source_snippet=context,
                    confidence_score=0.9,
                    extraction_method="rule_based",
                    neuro_exam_detail=neuro_exam_detail.dict(),
                    char_start=match.start(),
                    char_end=match.end()
                )
                facts.append(fact)

        return facts


class AnatomicalContextExtractor:
    """Extract anatomical context for entities"""

    @staticmethod
    def extract_for_span(span: Span) -> Optional[AnatomicalContext]:
        """Extract anatomical context for a spaCy span"""
        # Get surrounding context
        doc = span.doc
        start_idx = max(0, span.start - 20)
        end_idx = min(len(doc), span.end + 20)
        context_text = doc[start_idx:end_idx].text

        # Extract laterality
        laterality = None
        lat_match = ClinicalPatterns.LATERALITY.search(context_text)
        if lat_match:
            lat_str = lat_match.group(1).lower()
            try:
                laterality = Laterality(lat_str)
            except ValueError:
                pass

        # Extract brain region
        brain_region = None
        region_match = ClinicalPatterns.BRAIN_REGION.search(context_text)
        if region_match:
            region_str = region_match.group(1).lower()
            try:
                brain_region = BrainRegion(region_str)
            except ValueError:
                pass

        # Extract size measurements
        size_mm = None
        volume_cc = None
        size_match = ClinicalPatterns.SIZE_MEASUREMENT.search(context_text)
        if size_match:
            dim1 = float(size_match.group(1))
            dim2 = float(size_match.group(2))
            dim3 = float(size_match.group(3)) if size_match.group(3) else None
            unit = size_match.group(4).lower()

            # Convert to mm
            if unit == "cm":
                dim1 *= 10
                dim2 *= 10
                if dim3:
                    dim3 *= 10

            # Calculate max diameter
            size_mm = max(dim1, dim2, dim3 if dim3 else 0)

            # Calculate volume if 3D
            if dim3:
                volume_cc = (dim1 * dim2 * dim3) / 1000  # mm³ to cc

        # Return context if any information found
        if any([laterality, brain_region, size_mm, volume_cc]):
            return AnatomicalContext(
                laterality=laterality,
                brain_region=brain_region,
                size_mm=size_mm,
                volume_cc=volume_cc
            )

        return None


class TemporalExtractor:
    """Extract temporal information"""

    @staticmethod
    def extract_temporal_context(text: str, match_start: int, match_end: int) -> Optional[TemporalContext]:
        """Extract temporal context for an entity"""
        # Get surrounding context
        start = max(0, match_start - 100)
        end = min(len(text), match_end + 100)
        context = text[start:end]

        # Extract POD
        pod = None
        pod_match = ClinicalPatterns.POST_OP_DAY.search(context)
        if pod_match:
            pod = int(pod_match.group(1))

        # Extract hospital day
        hospital_day = None
        hd_match = ClinicalPatterns.HOSPITAL_DAY.search(context)
        if hd_match:
            hospital_day = int(hd_match.group(1))

        # Extract dates
        timestamp = None
        date_match = ClinicalPatterns.DATE_PATTERN.search(context)
        if date_match:
            # Parse date (simplified - would need more robust parsing)
            pass

        if pod or hospital_day or timestamp:
            return TemporalContext(
                timestamp=timestamp,
                relative_time=None,
                pod=pod,
                hospital_day=hospital_day
            )

        return None


# =============================================================================
# Main Extraction Pipeline
# =============================================================================

class HybridExtractionEngine:
    """
    Hybrid extraction engine combining NER, LLM, and rule-based methods
    Target: 95%+ extraction recall
    """

    def __init__(self):
        """Initialize the extraction engine"""
        self.ner_models = ner_models
        if not self.ner_models.loaded:
            self.ner_models.load_models()

    def extract_all_facts(self, text: str, patient_id: int, document_id: int) -> List[AtomicClinicalFact]:
        """
        Extract all clinical facts from text using hybrid approach

        Args:
            text: Clinical text to extract from
            patient_id: Patient ID
            document_id: Document ID

        Returns:
            List of extracted atomic clinical facts
        """
        logger.info(f"Starting extraction for document {document_id}")
        all_facts = []

        try:
            # Process text with spaCy models
            if settings.extraction_use_ner and self.ner_models.scispacy_model:
                doc = self.ner_models.scispacy_model(text)
            else:
                doc = None

            # 1. Extract diagnoses (NER-based)
            if doc:
                diagnosis_facts = DiagnosisExtractor.extract(doc, text)
                all_facts.extend(diagnosis_facts)
                logger.info(f"Extracted {len(diagnosis_facts)} diagnoses")

            # 2. Extract procedures (rule-based)
            procedure_facts = ProcedureExtractor.extract(text)
            all_facts.extend(procedure_facts)
            logger.info(f"Extracted {len(procedure_facts)} procedures")

            # 3. Extract medications (rule-based)
            medication_facts = MedicationExtractor.extract(text)
            all_facts.extend(medication_facts)
            logger.info(f"Extracted {len(medication_facts)} medications")

            # 4. Extract lab values (rule-based)
            lab_facts = LabExtractor.extract(text)
            all_facts.extend(lab_facts)
            logger.info(f"Extracted {len(lab_facts)} lab values")

            # 5. Extract GCS (rule-based)
            gcs_facts = NeuroExamExtractor.extract_gcs(text)
            all_facts.extend(gcs_facts)
            logger.info(f"Extracted {len(gcs_facts)} GCS scores")

            # 6. Extract motor exam (rule-based)
            motor_facts = NeuroExamExtractor.extract_motor_exam(text)
            all_facts.extend(motor_facts)
            logger.info(f"Extracted {len(motor_facts)} motor exam findings")

            # 7. Add temporal context to all facts
            for fact in all_facts:
                temporal_context = TemporalExtractor.extract_temporal_context(
                    text, fact.char_start or 0, fact.char_end or 0
                )
                if temporal_context:
                    fact.temporal_context = temporal_context.dict()

            # 8. Deduplicate facts
            deduplicated_facts = self._deduplicate_facts(all_facts)
            logger.info(f"After deduplication: {len(deduplicated_facts)} facts")

            # 9. Filter by confidence threshold
            high_confidence_facts = [
                f for f in deduplicated_facts
                if f.confidence_score >= settings.extraction_min_confidence
            ]
            logger.info(f"After confidence filtering: {len(high_confidence_facts)} facts")

            return high_confidence_facts

        except Exception as e:
            logger.error(f"Error in extraction pipeline: {e}", exc_info=True)
            return []

    def _deduplicate_facts(self, facts: List[AtomicClinicalFact]) -> List[AtomicClinicalFact]:
        """
        Deduplicate extracted facts based on entity name and position

        Args:
            facts: List of facts to deduplicate

        Returns:
            Deduplicated list of facts
        """
        if not facts:
            return []

        # Group by entity type and name
        fact_groups: Dict[Tuple[str, str], List[AtomicClinicalFact]] = {}

        for fact in facts:
            key = (fact.entity_type, fact.entity_name.lower())
            if key not in fact_groups:
                fact_groups[key] = []
            fact_groups[key].append(fact)

        # For each group, keep the highest confidence fact
        # or merge if they're from different positions
        deduplicated = []

        for key, group in fact_groups.items():
            if len(group) == 1:
                deduplicated.append(group[0])
            else:
                # Check if facts are from different positions (> 50 chars apart)
                positions = [(f.char_start or 0, f.char_end or 0) for f in group]
                unique_positions = []

                for i, (start, end) in enumerate(positions):
                    is_unique = True
                    for unique_start, unique_end in unique_positions:
                        if abs(start - unique_start) < 50:
                            is_unique = False
                            break
                    if is_unique:
                        unique_positions.append((start, end))
                        deduplicated.append(group[i])

                # If all from same position, keep highest confidence
                if not unique_positions:
                    best_fact = max(group, key=lambda f: f.confidence_score)
                    deduplicated.append(best_fact)

        return deduplicated

    def extract_with_llm(self, text: str, entity_types: List[EntityType]) -> List[AtomicClinicalFact]:
        """
        Use LLM for extraction when rule-based methods fail
        This would integrate with OpenAI/Anthropic API

        Args:
            text: Text to extract from
            entity_types: Types of entities to extract

        Returns:
            List of extracted facts
        """
        # TODO: Implement LLM-based extraction
        # This would use structured output from GPT-4 or Claude
        logger.info("LLM-based extraction not yet implemented")
        return []


# =============================================================================
# Public API
# =============================================================================

def extract_clinical_facts(
    text: str,
    patient_id: int,
    document_id: int
) -> List[AtomicClinicalFact]:
    """
    Main entry point for clinical fact extraction

    Args:
        text: Clinical text to extract from
        patient_id: Patient ID
        document_id: Document ID

    Returns:
        List of extracted atomic clinical facts
    """
    engine = HybridExtractionEngine()
    return engine.extract_all_facts(text, patient_id, document_id)
