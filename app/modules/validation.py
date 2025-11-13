"""
NeuroscribeAI Validation Framework
6-stage QA pipeline for clinical data validation
"""

import logging
from typing import List, Dict, Optional, Set, Tuple
from datetime import datetime, timedelta
from collections import defaultdict

from app.schemas import (
    AtomicClinicalFact, EntityType, ValidationReport, ValidationIssue,
    ValidationSeverity, PatientTimeline
)
from app.modules.temporal_reasoning import build_patient_timeline, TemporalConflict
from app.config import settings

logger = logging.getLogger(__name__)


# =============================================================================
# Stage 1: Completeness Validation
# =============================================================================

class CompletenessValidator:
    """
    Stage 1: Validate completeness of extracted data
    Checks for required fields and expected entities
    """

    # Required entity types for neurosurgical discharge summary
    REQUIRED_ENTITIES = [
        EntityType.DIAGNOSIS,
        EntityType.PROCEDURE,
        EntityType.MEDICATION
    ]

    # Expected entity types (not required but expected)
    EXPECTED_ENTITIES = [
        EntityType.PHYSICAL_EXAM,
        EntityType.IMAGING,
        EntityType.LAB_VALUE
    ]

    @staticmethod
    def validate(facts: List[AtomicClinicalFact]) -> Tuple[float, List[ValidationIssue]]:
        """
        Validate completeness of facts

        Args:
            facts: List of clinical facts

        Returns:
            Tuple of (completeness_score, list of issues)
        """
        issues = []
        total_checks = 0
        passed_checks = 0

        # Check for required entity types
        entity_types_present = set(f.entity_type for f in facts)

        for required_type in CompletenessValidator.REQUIRED_ENTITIES:
            total_checks += 1
            if required_type in entity_types_present:
                passed_checks += 1
            else:
                issue = ValidationIssue(
                    severity=ValidationSeverity.CRITICAL,
                    category="completeness",
                    field=required_type,
                    message=f"Required entity type {required_type} not found",
                    recommendation=f"Verify extraction captured {required_type} from source document"
                )
                issues.append(issue)

        # Check for expected entity types
        for expected_type in CompletenessValidator.EXPECTED_ENTITIES:
            total_checks += 1
            if expected_type in entity_types_present:
                passed_checks += 1
            else:
                issue = ValidationIssue(
                    severity=ValidationSeverity.WARNING,
                    category="completeness",
                    field=expected_type,
                    message=f"Expected entity type {expected_type} not found",
                    recommendation=f"Review document for {expected_type} information"
                )
                issues.append(issue)

        # Check for critical missing details
        for fact in facts:
            if fact.entity_type == EntityType.DIAGNOSIS:
                # Diagnosis should have anatomical context
                if not fact.anatomical_context:
                    issue = ValidationIssue(
                        severity=ValidationSeverity.WARNING,
                        category="completeness",
                        field="anatomical_context",
                        message=f"Diagnosis '{fact.entity_name}' missing anatomical context",
                        fact_id=fact.id if hasattr(fact, 'id') else None
                    )
                    issues.append(issue)

            elif fact.entity_type == EntityType.MEDICATION:
                # Medications should have dosing information
                if not fact.medication_detail or not fact.medication_detail.get("dose_value"):
                    issue = ValidationIssue(
                        severity=ValidationSeverity.WARNING,
                        category="completeness",
                        field="medication_detail",
                        message=f"Medication '{fact.entity_name}' missing dosing information",
                        fact_id=fact.id if hasattr(fact, 'id') else None
                    )
                    issues.append(issue)

            elif fact.entity_type == EntityType.PROCEDURE:
                # Procedures should have date/time
                if not fact.timestamp and not fact.resolved_timestamp:
                    issue = ValidationIssue(
                        severity=ValidationSeverity.WARNING,
                        category="completeness",
                        field="timestamp",
                        message=f"Procedure '{fact.entity_name}' missing temporal information",
                        fact_id=fact.id if hasattr(fact, 'id') else None
                    )
                    issues.append(issue)

        # Calculate completeness score
        completeness_score = (passed_checks / total_checks * 100) if total_checks > 0 else 0

        logger.info(f"Completeness validation: {completeness_score:.1f}% ({passed_checks}/{total_checks} checks passed)")

        return completeness_score, issues


# =============================================================================
# Stage 2: Accuracy Validation
# =============================================================================

class AccuracyValidator:
    """
    Stage 2: Validate accuracy of extracted data
    Cross-references facts with source text
    """

    @staticmethod
    def validate(
        facts: List[AtomicClinicalFact],
        source_text: str
    ) -> Tuple[float, List[ValidationIssue]]:
        """
        Validate accuracy of facts against source text

        Args:
            facts: List of clinical facts
            source_text: Original source document text

        Returns:
            Tuple of (accuracy_score, list of issues)
        """
        issues = []
        total_facts = len(facts)
        accurate_facts = 0

        for fact in facts:
            # Check if extracted text is in source
            if fact.extracted_text and fact.extracted_text.lower() in source_text.lower():
                accurate_facts += 1
            else:
                # Check source snippet
                if fact.source_snippet and fact.source_snippet.lower() in source_text.lower():
                    accurate_facts += 1
                else:
                    issue = ValidationIssue(
                        severity=ValidationSeverity.CRITICAL,
                        category="accuracy",
                        field="extracted_text",
                        message=f"Cannot verify '{fact.entity_name}' in source document",
                        fact_id=fact.id if hasattr(fact, 'id') else None,
                        recommendation="Review extraction - may be hallucinated"
                    )
                    issues.append(issue)

            # Check confidence score
            if fact.confidence_score < settings.extraction_min_confidence:
                issue = ValidationIssue(
                    severity=ValidationSeverity.WARNING,
                    category="accuracy",
                    field="confidence_score",
                    message=f"Low confidence score ({fact.confidence_score:.2f}) for '{fact.entity_name}'",
                    fact_id=fact.id if hasattr(fact, 'id') else None,
                    recommendation="Consider manual review"
                )
                issues.append(issue)

        # Calculate accuracy score
        accuracy_score = (accurate_facts / total_facts * 100) if total_facts > 0 else 0

        logger.info(f"Accuracy validation: {accuracy_score:.1f}% ({accurate_facts}/{total_facts} facts verified)")

        return accuracy_score, issues


# =============================================================================
# Stage 3: Temporal Validation
# =============================================================================

class TemporalValidator:
    """
    Stage 3: Validate temporal coherence
    Checks timeline consistency and detects conflicts
    """

    @staticmethod
    def validate(
        facts: List[AtomicClinicalFact],
        patient_id: int
    ) -> Tuple[float, List[ValidationIssue]]:
        """
        Validate temporal coherence of facts

        Args:
            facts: List of clinical facts
            patient_id: Patient ID

        Returns:
            Tuple of (temporal_coherence_score, list of issues)
        """
        issues = []

        # Build timeline
        timeline = build_patient_timeline(facts, patient_id)

        # Check for temporal conflicts
        conflicts = timeline.conflicts

        if conflicts:
            for conflict in conflicts:
                severity = ValidationSeverity.CRITICAL if conflict.severity == "critical" else ValidationSeverity.WARNING

                issue = ValidationIssue(
                    severity=severity,
                    category="temporal",
                    field="timeline",
                    message=conflict.description,
                    recommendation="Review temporal information and resolve conflict"
                )
                issues.append(issue)

        # Check temporal resolution rate
        total_events = len(timeline.events)
        resolved_events = len([e for e in timeline.events if e.resolved_timestamp])
        resolution_rate = (resolved_events / total_events) if total_events > 0 else 0

        if resolution_rate < 0.8:
            issue = ValidationIssue(
                severity=ValidationSeverity.WARNING,
                category="temporal",
                field="temporal_resolution",
                message=f"Low temporal resolution rate: {resolution_rate*100:.1f}%",
                recommendation="Add more explicit dates/times to improve timeline accuracy"
            )
            issues.append(issue)

        # Calculate temporal coherence score
        # Score based on: resolution rate (50%) + inverse of conflicts (50%)
        conflict_penalty = min(len(conflicts) * 10, 50)  # Max 50 point penalty
        temporal_score = (resolution_rate * 50) + (50 - conflict_penalty)

        logger.info(f"Temporal validation: {temporal_score:.1f}% ({len(conflicts)} conflicts, {resolution_rate*100:.1f}% resolved)")

        return temporal_score, issues


# =============================================================================
# Stage 4: Contradiction Detection
# =============================================================================

class ContradictionDetector:
    """
    Stage 4: Detect contradictions between facts
    """

    @staticmethod
    def validate(facts: List[AtomicClinicalFact]) -> Tuple[float, List[ValidationIssue]]:
        """
        Detect contradictions in facts

        Args:
            facts: List of clinical facts

        Returns:
            Tuple of (contradiction_score, list of issues)
        """
        issues = []
        contradictions_found = 0

        # Group facts by entity type
        facts_by_type = defaultdict(list)
        for fact in facts:
            facts_by_type[fact.entity_type].append(fact)

        # Check for contradictory diagnoses
        diagnoses = facts_by_type[EntityType.DIAGNOSIS]
        if len(diagnoses) > 1:
            # Check for contradictory laterality
            laterality_groups = defaultdict(list)
            for diag in diagnoses:
                if diag.anatomical_context and diag.anatomical_context.get("laterality"):
                    key = diag.entity_name.lower()
                    laterality = diag.anatomical_context.get("laterality")
                    laterality_groups[key].append((diag, laterality))

            for diag_name, diag_list in laterality_groups.items():
                if len(diag_list) > 1:
                    lateralities = set(lat for _, lat in diag_list)
                    if len(lateralities) > 1 and "bilateral" not in lateralities:
                        contradictions_found += 1
                        issue = ValidationIssue(
                            severity=ValidationSeverity.CRITICAL,
                            category="contradiction",
                            field="laterality",
                            message=f"Contradictory laterality for {diag_name}: {lateralities}",
                            recommendation="Verify correct laterality from source document"
                        )
                        issues.append(issue)

        # Check for contradictory lab values
        lab_values = facts_by_type[EntityType.LAB_VALUE]
        if lab_values:
            # Group by test name and check for physiologically impossible changes
            lab_groups = defaultdict(list)
            for lab in lab_values:
                if lab.lab_value and lab.resolved_timestamp:
                    test_name = lab.entity_name.lower()
                    value = lab.lab_value.get("value")
                    if value:
                        lab_groups[test_name].append((lab, value, lab.resolved_timestamp))

            for test_name, lab_list in lab_groups.items():
                if len(lab_list) > 1:
                    # Sort by timestamp
                    lab_list.sort(key=lambda x: x[2])

                    # Check for impossible changes
                    for i in range(len(lab_list) - 1):
                        _, val1, time1 = lab_list[i]
                        _, val2, time2 = lab_list[i + 1]

                        # Check sodium (should not change by >30 in short time)
                        if "sodium" in test_name:
                            change = abs(val2 - val1)
                            time_diff_hours = (time2 - time1).total_seconds() / 3600

                            if time_diff_hours < 24 and change > 30:
                                contradictions_found += 1
                                issue = ValidationIssue(
                                    severity=ValidationSeverity.CRITICAL,
                                    category="contradiction",
                                    field="lab_values",
                                    message=f"Implausible sodium change: {val1} → {val2} in {time_diff_hours:.1f}h",
                                    recommendation="Verify lab values from source"
                                )
                                issues.append(issue)

        # Check for medication contradictions (e.g., anticoagulant + active hemorrhage)
        medications = facts_by_type[EntityType.MEDICATION]
        diagnoses = facts_by_type[EntityType.DIAGNOSIS]

        anticoagulants = [m for m in medications if any(
            drug in m.entity_name.lower() for drug in ["warfarin", "heparin", "enoxaparin"]
        )]

        hemorrhage = [d for d in diagnoses if "hemorrhage" in d.entity_name.lower() and not d.is_historical]

        if anticoagulants and hemorrhage:
            contradictions_found += 1
            issue = ValidationIssue(
                severity=ValidationSeverity.CRITICAL,
                category="contradiction",
                field="medications",
                message="Anticoagulant prescribed with active hemorrhage",
                recommendation="Verify clinical decision or correct extraction"
            )
            issues.append(issue)

        # Calculate contradiction score (inverse of contradictions found)
        max_contradictions = 10  # Normalize to max of 10
        contradiction_penalty = min(contradictions_found / max_contradictions, 1.0) * 100
        contradiction_score = 100 - contradiction_penalty

        logger.info(f"Contradiction detection: {contradiction_score:.1f}% ({contradictions_found} contradictions found)")

        return contradiction_score, issues


# =============================================================================
# Stage 5: Missing Data Detection
# =============================================================================

class MissingDataDetector:
    """
    Stage 5: Detect missing expected data
    """

    # Expected data patterns for neurosurgical cases
    EXPECTED_DATA = {
        EntityType.DIAGNOSIS: ["pathology location", "laterality", "size"],
        EntityType.PROCEDURE: ["date", "approach", "extent of resection"],
        EntityType.MEDICATION: ["dose", "frequency", "route"],
        EntityType.PHYSICAL_EXAM: ["mental status", "motor strength", "cranial nerves"],
        EntityType.IMAGING: ["modality", "findings", "date"]
    }

    @staticmethod
    def validate(facts: List[AtomicClinicalFact]) -> Tuple[List[str], List[str], List[ValidationIssue]]:
        """
        Detect missing data

        Args:
            facts: List of clinical facts

        Returns:
            Tuple of (missing_required_fields, missing_expected_entities, issues)
        """
        issues = []
        missing_required = []
        missing_expected = []

        # Check each entity type for missing details
        facts_by_type = defaultdict(list)
        for fact in facts:
            facts_by_type[fact.entity_type].append(fact)

        for entity_type, expected_fields in MissingDataDetector.EXPECTED_DATA.items():
            if entity_type not in facts_by_type:
                missing_expected.append(entity_type)
                continue

            entity_facts = facts_by_type[entity_type]

            for fact in entity_facts:
                missing_for_fact = []

                if entity_type == EntityType.DIAGNOSIS:
                    if not fact.anatomical_context:
                        missing_for_fact.append("anatomical_context")
                    elif not fact.anatomical_context.get("laterality"):
                        missing_for_fact.append("laterality")

                elif entity_type == EntityType.MEDICATION:
                    if not fact.medication_detail:
                        missing_for_fact.append("medication_detail")
                    else:
                        if not fact.medication_detail.get("dose_value"):
                            missing_for_fact.append("dose")
                        if not fact.medication_detail.get("frequency"):
                            missing_for_fact.append("frequency")

                elif entity_type == EntityType.PROCEDURE:
                    if not fact.timestamp and not fact.resolved_timestamp:
                        missing_for_fact.append("timestamp")
                    if not fact.procedure_detail:
                        missing_for_fact.append("procedure_detail")

                if missing_for_fact:
                    issue = ValidationIssue(
                        severity=ValidationSeverity.WARNING,
                        category="missing_data",
                        field=", ".join(missing_for_fact),
                        message=f"{entity_type} '{fact.entity_name}' missing: {', '.join(missing_for_fact)}",
                        fact_id=fact.id if hasattr(fact, 'id') else None,
                        recommendation="Review source document for additional details"
                    )
                    issues.append(issue)

        logger.info(f"Missing data detection: {len(missing_required)} required, {len(missing_expected)} expected, {len(issues)} detail issues")

        return missing_required, missing_expected, issues


# =============================================================================
# Stage 6: Cross-Validation
# =============================================================================

class CrossValidator:
    """
    Stage 6: Cross-validate facts with medical knowledge
    """

    # Valid value ranges for common labs
    LAB_RANGES = {
        "sodium": (135, 145),
        "potassium": (3.5, 5.0),
        "hemoglobin": (12.0, 17.0),
        "platelet": (150, 400),
        "inr": (0.8, 1.2),
        "glucose": (70, 140)
    }

    # Valid medication dose ranges (mg)
    MEDICATION_RANGES = {
        "dexamethasone": (0.5, 24),
        "levetiracetam": (250, 3000),
        "phenytoin": (100, 600),
        "enoxaparin": (20, 150)
    }

    @staticmethod
    def validate(facts: List[AtomicClinicalFact]) -> Tuple[float, List[ValidationIssue]]:
        """
        Cross-validate facts with medical knowledge

        Args:
            facts: List of clinical facts

        Returns:
            Tuple of (cross_validation_score, list of issues)
        """
        issues = []
        total_checks = 0
        passed_checks = 0

        # Validate lab values
        lab_facts = [f for f in facts if f.entity_type == EntityType.LAB_VALUE]
        for lab in lab_facts:
            if lab.lab_value:
                test_name = lab.entity_name.lower()
                value = lab.lab_value.get("value")

                if value is not None:
                    for lab_type, (min_val, max_val) in CrossValidator.LAB_RANGES.items():
                        if lab_type in test_name:
                            total_checks += 1
                            if min_val <= value <= max_val:
                                passed_checks += 1
                            else:
                                severity = ValidationSeverity.CRITICAL if (
                                    value < min_val * 0.7 or value > max_val * 1.5
                                ) else ValidationSeverity.WARNING

                                issue = ValidationIssue(
                                    severity=severity,
                                    category="cross_validation",
                                    field="lab_value",
                                    message=f"{lab.entity_name} value {value} outside normal range ({min_val}-{max_val})",
                                    fact_id=lab.id if hasattr(lab, 'id') else None,
                                    recommendation="Verify value from source, may require clinical intervention"
                                )
                                issues.append(issue)

        # Validate medication doses
        med_facts = [f for f in facts if f.entity_type == EntityType.MEDICATION]
        for med in med_facts:
            if med.medication_detail:
                med_name = med.entity_name.lower()
                dose = med.medication_detail.get("dose_value")
                unit = med.medication_detail.get("dose_unit", "").lower()

                if dose and unit == "mg":
                    for med_type, (min_dose, max_dose) in CrossValidator.MEDICATION_RANGES.items():
                        if med_type in med_name:
                            total_checks += 1
                            if min_dose <= dose <= max_dose:
                                passed_checks += 1
                            else:
                                severity = ValidationSeverity.CRITICAL if (
                                    dose < min_dose * 0.5 or dose > max_dose * 2
                                ) else ValidationSeverity.WARNING

                                issue = ValidationIssue(
                                    severity=severity,
                                    category="cross_validation",
                                    field="medication_dose",
                                    message=f"{med.entity_name} dose {dose}mg outside typical range ({min_dose}-{max_dose}mg)",
                                    fact_id=med.id if hasattr(med, 'id') else None,
                                    recommendation="Verify dose from source"
                                )
                                issues.append(issue)

        # Calculate cross-validation score
        cross_validation_score = (passed_checks / total_checks * 100) if total_checks > 0 else 100

        logger.info(f"Cross-validation: {cross_validation_score:.1f}% ({passed_checks}/{total_checks} checks passed)")

        return cross_validation_score, issues


# =============================================================================
# Validation Framework
# =============================================================================

class ValidationFramework:
    """
    Main validation framework coordinating all 6 stages
    Target: 95%+ validation accuracy
    """

    def __init__(self):
        """Initialize validation framework"""
        self.completeness_validator = CompletenessValidator()
        self.accuracy_validator = AccuracyValidator()
        self.temporal_validator = TemporalValidator()
        self.contradiction_detector = ContradictionDetector()
        self.missing_data_detector = MissingDataDetector()
        self.cross_validator = CrossValidator()

    def validate_all(
        self,
        facts: List[AtomicClinicalFact],
        source_text: str,
        patient_id: int
    ) -> ValidationReport:
        """
        Run all validation stages

        Args:
            facts: List of clinical facts to validate
            source_text: Original source document text
            patient_id: Patient ID

        Returns:
            Comprehensive validation report
        """
        logger.info(f"Starting 6-stage validation for patient {patient_id} with {len(facts)} facts")

        all_issues = []

        # Stage 1: Completeness
        logger.info("Stage 1: Completeness validation")
        completeness_score, completeness_issues = self.completeness_validator.validate(facts)
        all_issues.extend(completeness_issues)

        # Stage 2: Accuracy
        logger.info("Stage 2: Accuracy validation")
        accuracy_score, accuracy_issues = self.accuracy_validator.validate(facts, source_text)
        all_issues.extend(accuracy_issues)

        # Stage 3: Temporal
        logger.info("Stage 3: Temporal validation")
        temporal_score, temporal_issues = self.temporal_validator.validate(facts, patient_id)
        all_issues.extend(temporal_issues)

        # Stage 4: Contradictions
        logger.info("Stage 4: Contradiction detection")
        contradiction_score, contradiction_issues = self.contradiction_detector.validate(facts)
        all_issues.extend(contradiction_issues)

        # Stage 5: Missing data
        logger.info("Stage 5: Missing data detection")
        missing_required, missing_expected, missing_issues = self.missing_data_detector.validate(facts)
        all_issues.extend(missing_issues)

        # Stage 6: Cross-validation
        logger.info("Stage 6: Cross-validation")
        cross_validation_score, cross_validation_issues = self.cross_validator.validate(facts)
        all_issues.extend(cross_validation_issues)

        # Calculate overall quality score (weighted average)
        overall_score = (
            completeness_score * 0.20 +
            accuracy_score * 0.25 +
            temporal_score * 0.20 +
            contradiction_score * 0.15 +
            cross_validation_score * 0.20
        )

        # Determine safety flags
        critical_issues = [i for i in all_issues if i.severity == ValidationSeverity.CRITICAL]
        safe_for_clinical_use = (
            overall_score >= settings.validation_score_threshold and
            len(critical_issues) == 0
        )
        requires_review = (
            overall_score < settings.validation_score_threshold or
            len(critical_issues) > 0
        )

        # Create validation report
        report = ValidationReport(
            patient_id=patient_id,
            validation_timestamp=datetime.now(),
            completeness_score=completeness_score,
            accuracy_score=accuracy_score,
            temporal_coherence_score=temporal_score,
            contradiction_score=contradiction_score,
            overall_quality_score=overall_score,
            issues=all_issues,
            safe_for_clinical_use=safe_for_clinical_use,
            requires_review=requires_review,
            missing_required_fields=missing_required,
            missing_expected_entities=missing_expected
        )

        logger.info(
            f"Validation complete: Overall score {overall_score:.1f}%, "
            f"{len(all_issues)} issues ({len(critical_issues)} critical), "
            f"Safe for use: {safe_for_clinical_use}"
        )

        return report


# =============================================================================
# Public API
# =============================================================================

def validate_clinical_data(
    facts: List[AtomicClinicalFact],
    source_text: str,
    patient_id: int
) -> ValidationReport:
    """
    Validate clinical data through 6-stage QA pipeline

    Args:
        facts: List of clinical facts
        source_text: Original source document
        patient_id: Patient ID

    Returns:
        Comprehensive validation report
    """
    framework = ValidationFramework()
    return framework.validate_all(facts, source_text, patient_id)
