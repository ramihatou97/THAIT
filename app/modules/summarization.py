"""
NeuroscribeAI Summarization Engine
RAG-based clinical summary generation with LLM integration
"""

import logging
from typing import List, Dict, Optional, Any
from datetime import datetime
import json
from tenacity import retry, stop_after_attempt, wait_exponential

from app.schemas import (
    AtomicClinicalFact, EntityType, SummaryRequest, SummaryResponse,
    SummarySection, ClinicalAlert
)
from app.config import settings

# Conditional imports for LLM providers
try:
    import openai
    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False

try:
    import anthropic
    ANTHROPIC_AVAILABLE = True
except ImportError:
    ANTHROPIC_AVAILABLE = False

logger = logging.getLogger(__name__)


# =============================================================================
# Summary Templates
# =============================================================================

class SummaryTemplates:
    """Templates for different summary sections"""

    DISCHARGE_SUMMARY = """
# DISCHARGE SUMMARY

**Patient Information:**
{patient_info}

## HOSPITAL COURSE

**Admission Date:** {admission_date}
**Discharge Date:** {discharge_date}
**Length of Stay:** {length_of_stay} days

### Primary Diagnosis
{primary_diagnosis}

### Procedures Performed
{procedures}

### Hospital Course by System

#### Neurological
{neuro_course}

#### Medications
{medications}

#### Laboratory/Imaging
{labs_imaging}

### Discharge Condition
{discharge_condition}

### Discharge Medications
{discharge_medications}

### Follow-Up
{followup}

### Discharge Instructions
{discharge_instructions}
"""

    OPERATIVE_NOTE = """
# OPERATIVE NOTE

**Date of Surgery:** {surgery_date}
**Surgeon:** {surgeon}
**Procedure:** {procedure_name}

## PREOPERATIVE DIAGNOSIS
{preop_diagnosis}

## POSTOPERATIVE DIAGNOSIS
{postop_diagnosis}

## PROCEDURE PERFORMED
{procedure_performed}

## INDICATION
{indication}

## FINDINGS
{findings}

## TECHNIQUE
{technique}

## ESTIMATED BLOOD LOSS
{ebl}

## COMPLICATIONS
{complications}

## DISPOSITION
{disposition}
"""


# =============================================================================
# Fact Organizer
# =============================================================================

class FactOrganizer:
    """Organizes clinical facts into structured sections"""

    @staticmethod
    def organize_by_type(facts: List[AtomicClinicalFact]) -> Dict[EntityType, List[AtomicClinicalFact]]:
        """Organize facts by entity type"""
        organized = {}
        for entity_type in EntityType:
            organized[entity_type] = [f for f in facts if f.entity_type == entity_type]
        return organized

    @staticmethod
    def organize_by_timeline(facts: List[AtomicClinicalFact]) -> List[AtomicClinicalFact]:
        """Organize facts chronologically"""
        # Filter facts with timestamps
        dated_facts = [f for f in facts if f.resolved_timestamp or f.timestamp]

        # Sort by resolved_timestamp or timestamp
        dated_facts.sort(key=lambda f: f.resolved_timestamp or f.timestamp or datetime.min)

        return dated_facts

    @staticmethod
    def group_by_body_system(facts: List[AtomicClinicalFact]) -> Dict[str, List[AtomicClinicalFact]]:
        """Group facts by body system"""
        systems = {
            "neurological": [],
            "cardiovascular": [],
            "respiratory": [],
            "gastrointestinal": [],
            "genitourinary": [],
            "hematologic": [],
            "infectious": [],
            "other": []
        }

        for fact in facts:
            # Classify based on entity type and content
            if fact.entity_type == EntityType.PHYSICAL_EXAM:
                if fact.neuro_exam_detail:
                    systems["neurological"].append(fact)
                else:
                    systems["other"].append(fact)
            elif fact.entity_type == EntityType.DIAGNOSIS:
                if any(keyword in fact.entity_name.lower() for keyword in [
                    "brain", "neuro", "cranial", "spinal", "seizure", "stroke"
                ]):
                    systems["neurological"].append(fact)
                elif any(keyword in fact.entity_name.lower() for keyword in [
                    "heart", "cardiac", "vascular"
                ]):
                    systems["cardiovascular"].append(fact)
                else:
                    systems["other"].append(fact)
            elif fact.entity_type == EntityType.LAB_VALUE:
                systems["hematologic"].append(fact)
            else:
                systems["other"].append(fact)

        return systems


# =============================================================================
# Section Generators
# =============================================================================

class SectionGenerator:
    """Generates individual summary sections"""

    @staticmethod
    def generate_patient_info(patient_data: Dict) -> str:
        """Generate patient information section"""
        lines = []

        if patient_data.get("mrn"):
            lines.append(f"MRN: {patient_data['mrn']}")

        if patient_data.get("name"):
            lines.append(f"Name: {patient_data['name']}")

        if patient_data.get("age"):
            lines.append(f"Age: {patient_data['age']} years")

        if patient_data.get("sex"):
            lines.append(f"Sex: {patient_data['sex']}")

        return "\n".join(lines) if lines else "Patient information not available"

    @staticmethod
    def generate_diagnosis_section(diagnosis_facts: List[AtomicClinicalFact]) -> str:
        """Generate diagnosis section"""
        if not diagnosis_facts:
            return "No diagnoses documented"

        lines = []
        for i, diag in enumerate(diagnosis_facts, 1):
            diag_text = f"{i}. {diag.entity_name}"

            # Add anatomical context
            if diag.anatomical_context:
                details = []
                if diag.anatomical_context.get("laterality"):
                    details.append(diag.anatomical_context["laterality"])
                if diag.anatomical_context.get("brain_region"):
                    details.append(diag.anatomical_context["brain_region"])
                if diag.anatomical_context.get("size_mm"):
                    details.append(f"{diag.anatomical_context['size_mm']:.1f}mm")

                if details:
                    diag_text += f" ({', '.join(details)})"

            lines.append(diag_text)

        return "\n".join(lines)

    @staticmethod
    def generate_procedure_section(procedure_facts: List[AtomicClinicalFact]) -> str:
        """Generate procedures section"""
        if not procedure_facts:
            return "No procedures documented"

        lines = []
        for i, proc in enumerate(procedure_facts, 1):
            proc_text = f"{i}. {proc.entity_name}"

            # Add date if available
            if proc.resolved_timestamp:
                proc_text += f" ({proc.resolved_timestamp.strftime('%m/%d/%Y')})"
            elif proc.timestamp:
                proc_text += f" ({proc.timestamp.strftime('%m/%d/%Y')})"

            # Add anatomical context
            if proc.anatomical_context:
                details = []
                if proc.anatomical_context.get("laterality"):
                    details.append(proc.anatomical_context["laterality"])
                if proc.anatomical_context.get("brain_region"):
                    details.append(proc.anatomical_context["brain_region"])

                if details:
                    proc_text += f" - {', '.join(details)}"

            lines.append(proc_text)

        return "\n".join(lines)

    @staticmethod
    def generate_medication_section(medication_facts: List[AtomicClinicalFact]) -> str:
        """Generate medications section"""
        if not medication_facts:
            return "No medications documented"

        lines = []
        for i, med in enumerate(medication_facts, 1):
            med_text = f"{i}. {med.entity_name}"

            # Add dosing information
            if med.medication_detail:
                details = []

                dose_value = med.medication_detail.get("dose_value")
                dose_unit = med.medication_detail.get("dose_unit")
                if dose_value and dose_unit:
                    details.append(f"{dose_value}{dose_unit}")

                frequency = med.medication_detail.get("frequency")
                if frequency:
                    details.append(frequency)

                route = med.medication_detail.get("route")
                if route:
                    details.append(route)

                if details:
                    med_text += f" {' '.join(details)}"

            lines.append(med_text)

        return "\n".join(lines)

    @staticmethod
    def generate_neuro_exam_section(exam_facts: List[AtomicClinicalFact]) -> str:
        """Generate neurological examination section"""
        if not exam_facts:
            return "Neurological examination not documented"

        lines = []

        # Find most recent exam
        recent_exam = max(
            [f for f in exam_facts if f.resolved_timestamp],
            key=lambda f: f.resolved_timestamp,
            default=exam_facts[0] if exam_facts else None
        )

        if recent_exam and recent_exam.neuro_exam_detail:
            neuro = recent_exam.neuro_exam_detail

            # Mental status
            if neuro.get("mental_status"):
                lines.append(f"**Mental Status:** {neuro['mental_status']}")

            # GCS
            if neuro.get("gcs"):
                gcs = neuro["gcs"]
                total = gcs.get("total_score",
                    (gcs.get("eye_opening", 0) +
                     gcs.get("verbal_response", 0) +
                     gcs.get("motor_response", 0)))
                lines.append(f"**GCS:** {total}")

            # Motor exam
            if neuro.get("motor_exam"):
                motor = neuro["motor_exam"]
                lines.append("**Motor Exam:**")

                # Check for symmetric strength
                if motor.get("symmetric"):
                    lines.append("- Strength symmetric throughout")
                else:
                    lines.append("- Upper extremities: 5/5 bilaterally (if not documented otherwise)")
                    lines.append("- Lower extremities: 5/5 bilaterally (if not documented otherwise)")

            # Cranial nerves
            if neuro.get("cranial_nerves"):
                lines.append("**Cranial Nerves:** Intact")

        return "\n".join(lines) if lines else "Neurological examination findings not detailed"

    @staticmethod
    def generate_labs_imaging_section(
        lab_facts: List[AtomicClinicalFact],
        imaging_facts: List[AtomicClinicalFact]
    ) -> str:
        """Generate labs and imaging section"""
        lines = []

        # Laboratory results
        if lab_facts:
            lines.append("**Laboratory Results:**")
            for lab in lab_facts:
                if lab.lab_value:
                    value = lab.lab_value.get("value")
                    unit = lab.lab_value.get("unit", "")
                    lines.append(f"- {lab.entity_name}: {value} {unit}")
            lines.append("")

        # Imaging results
        if imaging_facts:
            lines.append("**Imaging:**")
            for img in imaging_facts:
                img_text = f"- {img.entity_name}"
                if img.imaging_detail:
                    findings = img.imaging_detail.get("findings")
                    if findings:
                        img_text += f": {findings}"
                lines.append(img_text)

        return "\n".join(lines) if lines else "No laboratory or imaging results documented"


# =============================================================================
# LLM Integration
# =============================================================================

class LLMSummarizer:
    """LLM-based summarization for narrative generation"""

    def __init__(self):
        self.provider = settings.llm_provider
        self.openai_client = None
        self.anthropic_client = None

        if OPENAI_AVAILABLE and settings.openai_api_key:
            try:
                self.openai_client = openai.OpenAI(api_key=settings.openai_api_key)
                logger.info("OpenAI client initialized for summarization")
            except Exception as e:
                logger.error(f"Failed to initialize OpenAI client: {e}")

        if ANTHROPIC_AVAILABLE and settings.anthropic_api_key:
            try:
                self.anthropic_client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
                logger.info("Anthropic client initialized for summarization")
            except Exception as e:
                logger.error(f"Failed to initialize Anthropic client: {e}")

        if not self.openai_client and not self.anthropic_client:
            logger.warning("No LLM API clients initialized - narrative generation disabled")

    def _get_summary_prompt(
        self,
        facts: List[AtomicClinicalFact],
        summary_type: str,
        patient_context: Dict
    ) -> str:
        """Generate prompt for narrative summary"""
        # Organize facts by type
        facts_by_type = {}
        for fact in facts:
            if fact.entity_type not in facts_by_type:
                facts_by_type[fact.entity_type] = []
            facts_by_type[fact.entity_type] = [f.entity_name for f in facts if f.entity_type == fact.entity_type]

        pod = patient_context.get('pod', 'N/A')

        return f"""You are a senior neurosurgical attending physician writing a {summary_type.replace('_', ' ')}.

Generate a concise, professional narrative "Hospital Course" section based ONLY on these extracted clinical facts:

Diagnoses: {', '.join(facts_by_type.get(EntityType.DIAGNOSIS, []))}
Procedures: {', '.join(facts_by_type.get(EntityType.PROCEDURE, []))}
Medications: {', '.join(facts_by_type.get(EntityType.MEDICATION, []))}
Physical Exam: {', '.join([f.entity_name for f in facts if f.entity_type == EntityType.PHYSICAL_EXAM])}
Labs: {', '.join([f.entity_name for f in facts if f.entity_type == EntityType.LAB_VALUE])}

Post-operative Day: {pod}

Chronological Facts:
{json.dumps([{'day': f.temporal_context.get('pod') if f.temporal_context else None, 'type': f.entity_type.value, 'entity': f.entity_name} for f in sorted(facts, key=lambda x: (x.temporal_context.get('pod') if x.temporal_context and x.temporal_context.get('pod') else 999), reverse=False)], indent=2)}

Write a 2-3 paragraph narrative hospital course that:
1. Flows chronologically by POD
2. Integrates facts naturally
3. Is professional and concise
4. Uses only information from the facts above
5. Follows neurosurgical documentation standards

Hospital Course:"""

    @retry(
        stop=stop_after_attempt(settings.llm_max_retries),
        wait=wait_exponential(multiplier=1, min=2, max=10)
    )
    def _call_openai(self, prompt: str) -> str:
        """Call OpenAI API with retry logic"""
        if not self.openai_client:
            return "OpenAI client not configured."

        try:
            response = self.openai_client.chat.completions.create(
                model=settings.openai_model,
                messages=[
                    {"role": "system", "content": "You are a senior neurosurgical attending physician writing clinical summaries."},
                    {"role": "user", "content": prompt}
                ],
                temperature=settings.openai_temperature,
                max_tokens=settings.openai_max_tokens,
                timeout=settings.llm_timeout
            )
            return response.choices[0].message.content or ""

        except Exception as e:
            logger.error(f"OpenAI API call failed: {e}")
            raise

    @retry(
        stop=stop_after_attempt(settings.llm_max_retries),
        wait=wait_exponential(multiplier=1, min=2, max=10)
    )
    def _call_anthropic(self, prompt: str) -> str:
        """Call Anthropic API with retry logic"""
        if not self.anthropic_client:
            return "Anthropic client not configured."

        try:
            response = self.anthropic_client.messages.create(
                model=settings.anthropic_model,
                system="You are a senior neurosurgical attending physician writing clinical summaries.",
                messages=[{"role": "user", "content": prompt}],
                temperature=settings.anthropic_temperature,
                max_tokens=settings.anthropic_max_tokens,
                timeout=settings.llm_timeout
            )
            return response.content[0].text or ""

        except Exception as e:
            logger.error(f"Anthropic API call failed: {e}")
            raise

    def generate_narrative_summary(
        self,
        facts: List[AtomicClinicalFact],
        summary_type: str,
        patient_context: Dict
    ) -> str:
        """Generate narrative summary using LLM"""
        if not settings.extraction_use_llm or (not self.openai_client and not self.anthropic_client):
            logger.warning("LLM summarization disabled - no API keys configured")
            return "(LLM narrative generation is disabled. Configure API keys in .env to enable.)"

        logger.info(f"Generating LLM narrative for {summary_type}...")
        prompt = self._get_summary_prompt(facts, summary_type, patient_context)

        try:
            # Try primary provider
            if self.provider == "openai" and self.openai_client:
                return self._call_openai(prompt)
            elif self.provider == "anthropic" and self.anthropic_client:
                return self._call_anthropic(prompt)
            # Try fallback
            elif settings.llm_fallback_provider == "openai" and self.openai_client:
                logger.warning(f"Primary provider unavailable, using fallback OpenAI")
                return self._call_openai(prompt)
            elif settings.llm_fallback_provider == "anthropic" and self.anthropic_client:
                logger.warning(f"Primary provider unavailable, using fallback Anthropic")
                return self._call_anthropic(prompt)
            else:
                return "(No valid LLM provider configured.)"

        except Exception as e:
            logger.error(f"LLM summarization failed after retries: {e}")
            return f"(Error generating summary: {str(e)})"

    def enhance_section(self, section_text: str, context: str) -> str:
        """Enhance section with LLM (placeholder for future use)"""
        return section_text


# =============================================================================
# Main Summarization Engine
# =============================================================================

class SummarizationEngine:
    """
    Main summarization engine
    Generates structured clinical summaries from extracted facts
    """

    def __init__(self):
        """Initialize summarization engine"""
        self.fact_organizer = FactOrganizer()
        self.section_generator = SectionGenerator()
        self.llm_summarizer = LLMSummarizer()

    def generate_summary(
        self,
        request: SummaryRequest,
        facts: List[AtomicClinicalFact],
        alerts: Optional[List[ClinicalAlert]] = None,
        patient_data: Optional[Dict] = None
    ) -> SummaryResponse:
        """
        Generate clinical summary from facts

        Args:
            request: Summary request with preferences
            facts: List of clinical facts
            alerts: Optional clinical alerts
            patient_data: Optional patient demographic data

        Returns:
            Structured summary response
        """
        logger.info(f"Generating {request.summary_type} summary with {len(facts)} facts")

        # Organize facts
        facts_by_type = self.fact_organizer.organize_by_type(facts)
        facts_by_timeline = self.fact_organizer.organize_by_timeline(facts)
        facts_by_system = self.fact_organizer.group_by_body_system(facts)

        # Generate sections
        sections = []

        # Patient Information
        if patient_data:
            patient_info_text = self.section_generator.generate_patient_info(patient_data)
            sections.append(SummarySection(
                title="Patient Information",
                content=patient_info_text,
                section_type="demographics"
            ))

        # Primary Diagnosis
        diagnosis_text = self.section_generator.generate_diagnosis_section(
            facts_by_type[EntityType.DIAGNOSIS]
        )
        sections.append(SummarySection(
            title="Primary Diagnosis",
            content=diagnosis_text,
            section_type="diagnosis"
        ))

        # Procedures
        procedure_text = self.section_generator.generate_procedure_section(
            facts_by_type[EntityType.PROCEDURE]
        )
        sections.append(SummarySection(
            title="Procedures Performed",
            content=procedure_text,
            section_type="procedures"
        ))

        # Neurological Examination
        neuro_exam_text = self.section_generator.generate_neuro_exam_section(
            facts_by_type[EntityType.PHYSICAL_EXAM]
        )
        sections.append(SummarySection(
            title="Neurological Examination",
            content=neuro_exam_text,
            section_type="physical_exam"
        ))

        # Medications
        medication_text = self.section_generator.generate_medication_section(
            facts_by_type[EntityType.MEDICATION]
        )
        sections.append(SummarySection(
            title="Medications",
            content=medication_text,
            section_type="medications"
        ))

        # Labs and Imaging
        labs_imaging_text = self.section_generator.generate_labs_imaging_section(
            facts_by_type[EntityType.LAB_VALUE],
            facts_by_type[EntityType.IMAGING]
        )
        sections.append(SummarySection(
            title="Laboratory and Imaging Results",
            content=labs_imaging_text,
            section_type="labs_imaging"
        ))

        # Generate LLM narrative (if enabled and discharge summary)
        if settings.extraction_use_llm and request.summary_type == "discharge_summary":
            logger.info("Generating narrative hospital course via LLM...")
            patient_context = request.patient_context or patient_data or {}
            narrative_course = self.llm_summarizer.generate_narrative_summary(
                facts_by_timeline,  # Give chronologically ordered facts
                request.summary_type,
                patient_context
            )
            sections.append(SummarySection(
                title="Hospital Course Narrative",
                content=narrative_course,
                section_type="narrative",
                facts_count=len(facts_by_timeline)
            ))

        # Clinical Alerts (if any)
        if alerts:
            alert_lines = []
            for alert in alerts:
                alert_lines.append(f"**[{alert.severity.upper()}]** {alert.title}")
                alert_lines.append(f"  {alert.message}")
                if alert.recommendation:
                    alert_lines.append(f"  *Recommendation:* {alert.recommendation}")
                alert_lines.append("")

            if alert_lines:
                sections.append(SummarySection(
                    title="Clinical Alerts",
                    content="\n".join(alert_lines),
                    section_type="alerts"
                ))

        # Generate full summary text based on format
        if request.format == "markdown":
            summary_text = self._format_as_markdown(sections, request.summary_type)
        elif request.format == "json":
            summary_text = self._format_as_json(sections)
        else:  # structured
            summary_text = self._format_as_structured(sections)

        # Create response
        response = SummaryResponse(
            patient_id=request.patient_id,
            summary_type=request.summary_type,
            summary_text=summary_text,
            sections=sections,
            facts_included=len(facts),
            generation_timestamp=datetime.now(),
            confidence_score=self._calculate_confidence(facts),
            metadata={
                "facts_by_type": {
                    entity_type.value: len(fact_list)
                    for entity_type, fact_list in facts_by_type.items()
                    if fact_list
                },
                "alerts_count": len(alerts) if alerts else 0,
                "generation_method": "structured_extraction"
            }
        )

        logger.info(f"Summary generation complete: {len(sections)} sections, {len(facts)} facts")

        return response

    def _format_as_markdown(self, sections: List[SummarySection], summary_type: str) -> str:
        """Format sections as markdown"""
        lines = [f"# {summary_type.upper().replace('_', ' ')}"]
        lines.append("")
        lines.append(f"*Generated: {datetime.now().strftime('%B %d, %Y at %I:%M %p')}*")
        lines.append("")
        lines.append("---")
        lines.append("")

        for section in sections:
            lines.append(f"## {section.title}")
            lines.append("")
            lines.append(section.content)
            lines.append("")

        return "\n".join(lines)

    def _format_as_json(self, sections: List[SummarySection]) -> str:
        """Format sections as JSON"""
        data = {
            "sections": [
                {
                    "title": section.title,
                    "content": section.content,
                    "type": section.section_type
                }
                for section in sections
            ]
        }
        return json.dumps(data, indent=2)

    def _format_as_structured(self, sections: List[SummarySection]) -> str:
        """Format sections as structured text"""
        lines = []
        for section in sections:
            lines.append(f"=== {section.title} ===")
            lines.append(section.content)
            lines.append("")
        return "\n".join(lines)

    def _calculate_confidence(self, facts: List[AtomicClinicalFact]) -> float:
        """Calculate overall confidence score for summary"""
        if not facts:
            return 0.0

        # Average confidence of all facts
        total_confidence = sum(f.confidence_score for f in facts)
        avg_confidence = total_confidence / len(facts)

        # Penalty for low number of facts
        fact_count_score = min(len(facts) / 20, 1.0)  # Normalized to 20 facts

        # Combined score
        return (avg_confidence * 0.7 + fact_count_score * 0.3)


# =============================================================================
# Public API
# =============================================================================

def generate_clinical_summary(
    request: SummaryRequest,
    facts: List[AtomicClinicalFact],
    alerts: Optional[List[ClinicalAlert]] = None,
    patient_data: Optional[Dict] = None
) -> SummaryResponse:
    """
    Generate clinical summary from extracted facts

    Args:
        request: Summary request
        facts: List of clinical facts
        alerts: Optional clinical alerts
        patient_data: Optional patient data

    Returns:
        Summary response
    """
    engine = SummarizationEngine()
    return engine.generate_summary(request, facts, alerts, patient_data)
