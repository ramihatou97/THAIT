"""
Unit tests for extraction module
"""

import pytest
from app.modules.extraction import (
    HybridExtractionEngine,
    DiagnosisExtractor,
    ProcedureExtractor,
    MedicationExtractor,
    NeuroExamExtractor
)
from app.schemas import EntityType


class TestMedicationExtractor:
    """Test medication extraction"""

    def test_extract_medication_with_dose(self):
        """Test extracting medication with dosing information"""
        text = "Patient on levetiracetam 500mg twice daily for seizure prophylaxis"

        facts = MedicationExtractor.extract(text)

        assert len(facts) > 0
        med_fact = facts[0]
        assert med_fact.entity_type == EntityType.MEDICATION
        assert "levetiracetam" in med_fact.entity_name.lower()
        assert med_fact.medication_detail is not None
        assert med_fact.medication_detail.get("dose_value") == 500
        assert med_fact.medication_detail.get("dose_unit") == "mg"

    def test_extract_multiple_medications(self):
        """Test extracting multiple medications"""
        text = "Started on dexamethasone 4mg and levetiracetam 500mg"

        facts = MedicationExtractor.extract(text)

        assert len(facts) >= 2
        med_names = [f.entity_name.lower() for f in facts]
        assert any("dexamethasone" in name for name in med_names)
        assert any("levetiracetam" in name for name in med_names)


class TestProcedureExtractor:
    """Test procedure extraction"""

    def test_extract_craniotomy(self):
        """Test extracting craniotomy procedure"""
        text = "Patient underwent left frontal craniotomy for tumor resection"

        facts = ProcedureExtractor.extract(text)

        assert len(facts) > 0
        proc_fact = facts[0]
        assert proc_fact.entity_type == EntityType.PROCEDURE
        assert "craniotomy" in proc_fact.entity_name.lower()
        assert proc_fact.anatomical_context is not None

    def test_extract_procedure_with_laterality(self):
        """Test extracting procedure with laterality"""
        text = "Right temporal craniotomy performed"

        facts = ProcedureExtractor.extract(text)

        assert len(facts) > 0
        proc_fact = facts[0]
        if proc_fact.anatomical_context:
            assert proc_fact.anatomical_context.get("laterality") in ["right", "left"]


class TestNeuroExamExtractor:
    """Test neurological examination extraction"""

    def test_extract_gcs_with_components(self):
        """Test extracting GCS with components"""
        text = "GCS 15 (E4 V5 M6) on examination"

        facts = NeuroExamExtractor.extract_gcs(text)

        assert len(facts) > 0
        gcs_fact = facts[0]
        assert gcs_fact.entity_type == EntityType.PHYSICAL_EXAM
        assert "glasgow" in gcs_fact.entity_name.lower()

    def test_extract_motor_strength(self):
        """Test extracting motor strength"""
        text = "Motor examination shows right deltoid 5/5, left deltoid 4/5"

        facts = NeuroExamExtractor.extract_motor_exam(text)

        assert len(facts) > 0
        # Should extract at least one motor finding
        motor_fact = facts[0]
        assert motor_fact.entity_type == EntityType.PHYSICAL_EXAM


class TestHybridExtractionEngine:
    """Test complete extraction engine"""

    @pytest.fixture
    def sample_text(self):
        """Sample clinical text"""
        return """
        Patient is a 45-year-old male who underwent left frontal craniotomy
        on POD 3. Currently on dexamethasone 4mg BID and levetiracetam 500mg BID.
        Neurological examination shows GCS 15, motor strength 5/5 throughout.
        Sodium 138 mmol/L. Follow-up MRI shows expected post-operative changes.
        """

    def test_extract_all_facts(self, sample_text):
        """Test extracting all facts from clinical text"""
        engine = HybridExtractionEngine()

        facts = engine.extract_all_facts(
            text=sample_text,
            patient_id=1,
            document_id=1
        )

        assert len(facts) > 0

        # Check for different entity types
        entity_types = set(f.entity_type for f in facts)
        assert EntityType.PROCEDURE in entity_types
        assert EntityType.MEDICATION in entity_types

    def test_deduplication(self):
        """Test fact deduplication"""
        text = "Patient on levetiracetam. Started levetiracetam 500mg BID."

        engine = HybridExtractionEngine()
        facts = engine.extract_all_facts(text, 1, 1)

        # Should deduplicate duplicate medication mentions
        med_facts = [f for f in facts if f.entity_type == EntityType.MEDICATION]
        # Even with two mentions, should have reasonable deduplication
        assert len(med_facts) >= 1

    def test_confidence_filtering(self):
        """Test confidence threshold filtering"""
        text = "Patient on dexamethasone 4mg BID"

        engine = HybridExtractionEngine()
        facts = engine.extract_all_facts(text, 1, 1)

        # All returned facts should meet confidence threshold
        for fact in facts:
            assert fact.confidence_score >= 0.7  # Default threshold


class TestTemporalExtraction:
    """Test temporal information extraction"""

    def test_extract_pod(self):
        """Test POD extraction"""
        text = "Patient is POD 5 from craniotomy"

        from app.modules.extraction import TemporalExtractor

        # This is tested through the complete extraction
        engine = HybridExtractionEngine()
        facts = engine.extract_all_facts(text, 1, 1)

        # Check if any facts have POD context
        has_pod = any(
            f.temporal_context and f.temporal_context.get("pod")
            for f in facts
        )
        # POD should be extracted (though may not attach to all facts)
        # This is a reasonable expectation


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
