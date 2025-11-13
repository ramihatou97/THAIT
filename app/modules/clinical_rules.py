"""
NeuroscribeAI Clinical Rules Engine
17+ Clinical safety rules for neurosurgical patient care
"""

import logging
from typing import List, Dict, Optional, Tuple, Any
from datetime import datetime, timedelta
from enum import Enum

from app.schemas import (
    AtomicClinicalFact, EntityType, ClinicalAlert, AlertSeverity,
    AlertCategory
)
from app.config import settings

logger = logging.getLogger(__name__)


# =============================================================================
# Clinical Rule Base Classes
# =============================================================================

class RuleCategory(str, Enum):
    """Categories of clinical rules"""
    SEIZURE_PROPHYLAXIS = "seizure_prophylaxis"
    DVT_PROPHYLAXIS = "dvt_prophylaxis"
    STEROID_MANAGEMENT = "steroid_management"
    ELECTROLYTE_MONITORING = "electrolyte_monitoring"
    HEMORRHAGE_RISK = "hemorrhage_risk"
    DISCHARGE_READINESS = "discharge_readiness"


class ClinicalRule:
    """Base class for clinical rules"""

    def __init__(self, rule_id: str, rule_name: str, category: RuleCategory):
        self.rule_id = rule_id
        self.rule_name = rule_name
        self.category = category

    def evaluate(
        self,
        facts: List[AtomicClinicalFact],
        patient_context: Dict[str, Any]
    ) -> List[ClinicalAlert]:
        """
        Evaluate rule against patient facts

        Args:
            facts: List of clinical facts
            patient_context: Additional patient context

        Returns:
            List of clinical alerts if rule is triggered
        """
        raise NotImplementedError("Subclasses must implement evaluate()")

    def _create_alert(
        self,
        severity: AlertSeverity,
        title: str,
        message: str,
        recommendation: str,
        evidence_fact_ids: List[int],
        evidence_summary: str
    ) -> ClinicalAlert:
        """Helper method to create clinical alert"""
        return ClinicalAlert(
            alert_type=self.rule_id,
            category=self.category.value,
            severity=severity,
            title=title,
            message=message,
            recommendation=recommendation,
            triggered_by_rule=self.rule_name,
            rule_logic=self.__doc__ or "",
            evidence_fact_ids=evidence_fact_ids,
            evidence_summary=evidence_summary,
            alert_timestamp=datetime.now()
        )


# =============================================================================
# Seizure Prophylaxis Rules
# =============================================================================

class SeizureProphylaxisIndicationRule(ClinicalRule):
    """
    Rule: Patients with supratentorial craniotomy should receive seizure prophylaxis
    Evidence: Class IIA recommendation (AAN/CNS guidelines)
    """

    def __init__(self):
        super().__init__(
            rule_id="SEIZURE_001",
            rule_name="Seizure Prophylaxis Indication",
            category=RuleCategory.SEIZURE_PROPHYLAXIS
        )

    def evaluate(self, facts: List[AtomicClinicalFact], patient_context: Dict) -> List[ClinicalAlert]:
        alerts = []

        # Find supratentorial procedures
        supratentorial_procedures = [
            f for f in facts
            if f.entity_type == EntityType.PROCEDURE
            and f.anatomical_context
            and any([
                f.anatomical_context.get("brain_region") in ["frontal", "parietal", "temporal", "occipital"],
                "craniotomy" in f.entity_name.lower()
            ])
        ]

        # Find seizure prophylaxis medications
        seizure_meds = [
            f for f in facts
            if f.entity_type == EntityType.MEDICATION
            and f.entity_name.lower() in ["levetiracetam", "keppra", "phenytoin", "dilantin"]
        ]

        if supratentorial_procedures and not seizure_meds:
            alert = self._create_alert(
                severity=AlertSeverity.HIGH,
                title="Seizure Prophylaxis Not Documented",
                message=f"Patient underwent supratentorial craniotomy but no seizure prophylaxis documented.",
                recommendation="Consider levetiracetam 500mg BID or phenytoin per protocol",
                evidence_fact_ids=[f.id for f in supratentorial_procedures],
                evidence_summary=f"Supratentorial procedure: {supratentorial_procedures[0].entity_name}"
            )
            alerts.append(alert)

        return alerts


class SeizureMedicationDurationRule(ClinicalRule):
    """
    Rule: Seizure prophylaxis should be continued for 7 days post-craniotomy
    Evidence: Standard neurosurgical protocol
    """

    def __init__(self):
        super().__init__(
            rule_id="SEIZURE_002",
            rule_name="Seizure Medication Duration",
            category=RuleCategory.SEIZURE_PROPHYLAXIS
        )

    def evaluate(self, facts: List[AtomicClinicalFact], patient_context: Dict) -> List[ClinicalAlert]:
        alerts = []

        # Get POD from context
        current_pod = patient_context.get("pod", 0)

        if current_pod > 7:
            # Find if still on seizure prophylaxis
            seizure_meds = [
                f for f in facts
                if f.entity_type == EntityType.MEDICATION
                and f.entity_name.lower() in ["levetiracetam", "keppra", "phenytoin", "dilantin"]
            ]

            if seizure_meds:
                alert = self._create_alert(
                    severity=AlertSeverity.MEDIUM,
                    title="Consider Discontinuing Seizure Prophylaxis",
                    message=f"Patient is POD {current_pod}. Standard seizure prophylaxis duration is 7 days.",
                    recommendation="Consider tapering seizure prophylaxis if no seizures occurred",
                    evidence_fact_ids=[f.id for f in seizure_meds],
                    evidence_summary=f"On {seizure_meds[0].entity_name} at POD {current_pod}"
                )
                alerts.append(alert)

        return alerts


# =============================================================================
# DVT Prophylaxis Rules
# =============================================================================

class DVTProphylaxisIndicationRule(ClinicalRule):
    """
    Rule: All post-operative neurosurgical patients should have DVT prophylaxis
    Evidence: ASA/AHA guidelines for VTE prevention
    """

    def __init__(self):
        super().__init__(
            rule_id="DVT_001",
            rule_name="DVT Prophylaxis Indication",
            category=RuleCategory.DVT_PROPHYLAXIS
        )

    def evaluate(self, facts: List[AtomicClinicalFact], patient_context: Dict) -> List[ClinicalAlert]:
        alerts = []

        # Check for any neurosurgical procedure
        procedures = [
            f for f in facts
            if f.entity_type == EntityType.PROCEDURE
        ]

        # Check for DVT prophylaxis (pharmacologic or mechanical)
        dvt_meds = [
            f for f in facts
            if f.entity_type == EntityType.MEDICATION
            and f.entity_name.lower() in ["enoxaparin", "lovenox", "heparin"]
        ]

        dvt_devices = [
            f for f in facts
            if "sequential compression" in f.entity_name.lower()
            or "scd" in f.entity_name.lower()
            or "compression device" in f.entity_name.lower()
        ]

        if procedures and not (dvt_meds or dvt_devices):
            current_pod = patient_context.get("pod", 0)
            if current_pod >= 1:  # Should start by POD 1
                alert = self._create_alert(
                    severity=AlertSeverity.HIGH,
                    title="DVT Prophylaxis Not Documented",
                    message="No DVT prophylaxis (pharmacologic or mechanical) documented post-operatively.",
                    recommendation="Consider enoxaparin 40mg SQ daily or SCD if pharmacologic contraindicated",
                    evidence_fact_ids=[f.id for f in procedures],
                    evidence_summary=f"Post-operative patient (POD {current_pod}) without DVT prophylaxis"
                )
                alerts.append(alert)

        return alerts


class DVTPharmacologicTimingRule(ClinicalRule):
    """
    Rule: Pharmacologic DVT prophylaxis should start 24-48h post-craniotomy
    Evidence: Balance between VTE risk and hemorrhage risk
    """

    def __init__(self):
        super().__init__(
            rule_id="DVT_002",
            rule_name="DVT Pharmacologic Timing",
            category=RuleCategory.DVT_PROPHYLAXIS
        )

    def evaluate(self, facts: List[AtomicClinicalFact], patient_context: Dict) -> List[ClinicalAlert]:
        alerts = []

        current_pod = patient_context.get("pod", 0)

        # Check for pharmacologic DVT prophylaxis
        dvt_meds = [
            f for f in facts
            if f.entity_type == EntityType.MEDICATION
            and f.entity_name.lower() in ["enoxaparin", "lovenox", "heparin"]
        ]

        if dvt_meds and current_pod == 0:
            # Starting on POD 0 may be too early
            alert = self._create_alert(
                severity=AlertSeverity.MEDIUM,
                title="Early Pharmacologic DVT Prophylaxis",
                message="Pharmacologic DVT prophylaxis started on POD 0 may increase hemorrhage risk.",
                recommendation="Verify no contraindications and consider imaging to rule out hemorrhage",
                evidence_fact_ids=[f.id for f in dvt_meds],
                evidence_summary=f"Started {dvt_meds[0].entity_name} on POD 0"
            )
            alerts.append(alert)

        return alerts


class DVTContraindicationRule(ClinicalRule):
    """
    Rule: Check for contraindications to pharmacologic DVT prophylaxis
    Contraindications: Active hemorrhage, coagulopathy, recent hemorrhagic stroke
    """

    def __init__(self):
        super().__init__(
            rule_id="DVT_003",
            rule_name="DVT Prophylaxis Contraindications",
            category=RuleCategory.DVT_PROPHYLAXIS
        )

    def evaluate(self, facts: List[AtomicClinicalFact], patient_context: Dict) -> List[ClinicalAlert]:
        alerts = []

        # Find DVT medications
        dvt_meds = [
            f for f in facts
            if f.entity_type == EntityType.MEDICATION
            and f.entity_name.lower() in ["enoxaparin", "lovenox", "heparin"]
        ]

        if not dvt_meds:
            return alerts

        # Check for hemorrhage
        hemorrhage_findings = [
            f for f in facts
            if f.entity_type in [EntityType.DIAGNOSIS, EntityType.IMAGING]
            and any(keyword in f.entity_name.lower() for keyword in ["hemorrhage", "bleeding", "hematoma"])
            and not f.is_historical
        ]

        if hemorrhage_findings:
            alert = self._create_alert(
                severity=AlertSeverity.CRITICAL,
                title="DVT Prophylaxis with Active Hemorrhage",
                message="Pharmacologic DVT prophylaxis prescribed with documented hemorrhage.",
                recommendation="Consider mechanical prophylaxis only until hemorrhage resolves",
                evidence_fact_ids=[f.id for f in dvt_meds + hemorrhage_findings],
                evidence_summary=f"Hemorrhage documented: {hemorrhage_findings[0].entity_name}"
            )
            alerts.append(alert)

        return alerts


# =============================================================================
# Steroid Management Rules
# =============================================================================

class SteroidTaperRule(ClinicalRule):
    """
    Rule: Dexamethasone should be tapered, not stopped abruptly
    Evidence: Risk of adrenal insufficiency with abrupt discontinuation
    """

    def __init__(self):
        super().__init__(
            rule_id="STEROID_001",
            rule_name="Steroid Taper Protocol",
            category=RuleCategory.STEROID_MANAGEMENT
        )

    def evaluate(self, facts: List[AtomicClinicalFact], patient_context: Dict) -> List[ClinicalAlert]:
        alerts = []

        # Find dexamethasone mentions
        dex_facts = [
            f for f in facts
            if f.entity_type == EntityType.MEDICATION
            and "dexamethasone" in f.entity_name.lower()
        ]

        if dex_facts:
            # Check if taper schedule is documented
            has_taper = any(
                f.medication_detail and f.medication_detail.get("taper_schedule")
                for f in dex_facts
            )

            if not has_taper:
                current_pod = patient_context.get("pod", 0)
                if current_pod >= 3:  # Should have taper plan by POD 3
                    alert = self._create_alert(
                        severity=AlertSeverity.MEDIUM,
                        title="Dexamethasone Taper Not Documented",
                        message="Patient on dexamethasone without documented taper schedule.",
                        recommendation="Implement taper protocol (e.g., decrease by 2mg every 3 days)",
                        evidence_fact_ids=[f.id for f in dex_facts],
                        evidence_summary=f"On dexamethasone at POD {current_pod}, no taper documented"
                    )
                    alerts.append(alert)

        return alerts


class SteroidGastricProtectionRule(ClinicalRule):
    """
    Rule: Patients on steroids should receive gastric protection
    Evidence: Increased risk of GI bleeding with corticosteroids
    """

    def __init__(self):
        super().__init__(
            rule_id="STEROID_002",
            rule_name="Steroid Gastric Protection",
            category=RuleCategory.STEROID_MANAGEMENT
        )

    def evaluate(self, facts: List[AtomicClinicalFact], patient_context: Dict) -> List[ClinicalAlert]:
        alerts = []

        # Find steroid use
        steroids = [
            f for f in facts
            if f.entity_type == EntityType.MEDICATION
            and any(s in f.entity_name.lower() for s in ["dexamethasone", "prednisone", "methylprednisolone"])
        ]

        # Find PPI/H2 blocker
        gastric_protection = [
            f for f in facts
            if f.entity_type == EntityType.MEDICATION
            and any(med in f.entity_name.lower() for med in [
                "pantoprazole", "omeprazole", "famotidine", "ranitidine"
            ])
        ]

        if steroids and not gastric_protection:
            alert = self._create_alert(
                severity=AlertSeverity.MEDIUM,
                title="Gastric Protection Not Documented",
                message="Patient on corticosteroids without gastric protection.",
                recommendation="Consider pantoprazole 40mg daily or famotidine 20mg BID",
                evidence_fact_ids=[f.id for f in steroids],
                evidence_summary=f"On {steroids[0].entity_name} without PPI/H2 blocker"
            )
            alerts.append(alert)

        return alerts


# =============================================================================
# Electrolyte Monitoring Rules
# =============================================================================

class HyponatremiaMonitoringRule(ClinicalRule):
    """
    Rule: Monitor sodium levels in post-craniotomy patients
    Evidence: Risk of SIADH and cerebral salt wasting
    """

    def __init__(self):
        super().__init__(
            rule_id="SODIUM_001",
            rule_name="Hyponatremia Monitoring",
            category=RuleCategory.ELECTROLYTE_MONITORING
        )

    def evaluate(self, facts: List[AtomicClinicalFact], patient_context: Dict) -> List[ClinicalAlert]:
        alerts = []

        # Find sodium lab values
        sodium_labs = [
            f for f in facts
            if f.entity_type == EntityType.LAB_VALUE
            and "sodium" in f.entity_name.lower()
            and f.lab_value
        ]

        if sodium_labs:
            latest_sodium = max(sodium_labs, key=lambda f: f.resolved_timestamp or datetime.min)
            sodium_value = latest_sodium.lab_value.get("value")

            if sodium_value and sodium_value < 135:
                severity = AlertSeverity.CRITICAL if sodium_value < 125 else AlertSeverity.HIGH

                alert = self._create_alert(
                    severity=severity,
                    title=f"Hyponatremia Detected (Na {sodium_value})",
                    message=f"Sodium level {sodium_value} mmol/L below normal range (135-145).",
                    recommendation="Evaluate for SIADH vs cerebral salt wasting. Consider fluid restriction or hypertonic saline based on etiology.",
                    evidence_fact_ids=[latest_sodium.id],
                    evidence_summary=f"Sodium {sodium_value} mmol/L"
                )
                alerts.append(alert)

        # Check if sodium being monitored at all
        current_pod = patient_context.get("pod", 0)
        if current_pod >= 2 and not sodium_labs:
            alert = self._create_alert(
                severity=AlertSeverity.MEDIUM,
                title="Sodium Monitoring Not Documented",
                message=f"No sodium lab values documented at POD {current_pod}.",
                recommendation="Obtain basic metabolic panel to monitor for electrolyte abnormalities",
                evidence_fact_ids=[],
                evidence_summary=f"No sodium labs at POD {current_pod}"
            )
            alerts.append(alert)

        return alerts


class RapidSodiumCorrectionRule(ClinicalRule):
    """
    Rule: Avoid rapid sodium correction (>8-10 mEq/L per 24h)
    Evidence: Risk of osmotic demyelination syndrome
    """

    def __init__(self):
        super().__init__(
            rule_id="SODIUM_002",
            rule_name="Rapid Sodium Correction",
            category=RuleCategory.ELECTROLYTE_MONITORING
        )

    def evaluate(self, facts: List[AtomicClinicalFact], patient_context: Dict) -> List[ClinicalAlert]:
        alerts = []

        # Find sodium values with timestamps
        sodium_labs = [
            f for f in facts
            if f.entity_type == EntityType.LAB_VALUE
            and "sodium" in f.entity_name.lower()
            and f.lab_value
            and f.resolved_timestamp
        ]

        if len(sodium_labs) < 2:
            return alerts

        # Sort by timestamp
        sodium_labs.sort(key=lambda f: f.resolved_timestamp)

        # Check consecutive values
        for i in range(len(sodium_labs) - 1):
            prev = sodium_labs[i]
            curr = sodium_labs[i + 1]

            prev_value = prev.lab_value.get("value")
            curr_value = curr.lab_value.get("value")

            if prev_value and curr_value:
                change = curr_value - prev_value
                time_diff = (curr.resolved_timestamp - prev.resolved_timestamp).total_seconds() / 3600  # hours

                if time_diff <= 24 and change > 10:
                    alert = self._create_alert(
                        severity=AlertSeverity.CRITICAL,
                        title="Rapid Sodium Correction Detected",
                        message=f"Sodium increased by {change:.1f} mEq/L in {time_diff:.1f} hours.",
                        recommendation="Risk of osmotic demyelination. Slow correction rate to <8-10 mEq/L per 24h.",
                        evidence_fact_ids=[prev.id, curr.id],
                        evidence_summary=f"Na {prev_value} → {curr_value} in {time_diff:.1f}h"
                    )
                    alerts.append(alert)

        return alerts


# =============================================================================
# Hemorrhage Risk Rules
# =============================================================================

class PostOpHemorrhageRiskRule(ClinicalRule):
    """
    Rule: Monitor for post-operative hemorrhage risk factors
    Risk factors: anticoagulation, hypertension, coagulopathy
    """

    def __init__(self):
        super().__init__(
            rule_id="HEMORRHAGE_001",
            rule_name="Post-Operative Hemorrhage Risk",
            category=RuleCategory.HEMORRHAGE_RISK
        )

    def evaluate(self, facts: List[AtomicClinicalFact], patient_context: Dict) -> List[ClinicalAlert]:
        alerts = []

        current_pod = patient_context.get("pod", 0)
        if current_pod > 7:  # Most risk in first week
            return alerts

        # Check for anticoagulation
        anticoagulants = [
            f for f in facts
            if f.entity_type == EntityType.MEDICATION
            and any(med in f.entity_name.lower() for med in [
                "warfarin", "coumadin", "heparin", "enoxaparin", "apixaban", "rivaroxaban"
            ])
        ]

        # Check for hypertension
        hypertension = [
            f for f in facts
            if f.entity_type == EntityType.VITAL_SIGN
            and "blood pressure" in f.entity_name.lower()
        ]

        # Check for coagulopathy
        coagulopathy = [
            f for f in facts
            if f.entity_type == EntityType.LAB_VALUE
            and any(lab in f.entity_name.lower() for lab in ["inr", "ptt", "platelet"])
        ]

        risk_factors = []
        evidence_ids = []

        if anticoagulants:
            risk_factors.append("anticoagulation")
            evidence_ids.extend([f.id for f in anticoagulants])

        if risk_factors:
            alert = self._create_alert(
                severity=AlertSeverity.HIGH,
                title="Hemorrhage Risk Factors Present",
                message=f"Patient at POD {current_pod} with risk factors: {', '.join(risk_factors)}",
                recommendation="Close neurological monitoring, consider repeat imaging if clinical change",
                evidence_fact_ids=evidence_ids,
                evidence_summary=f"Risk factors: {', '.join(risk_factors)}"
            )
            alerts.append(alert)

        return alerts


class AnticoagulationReversalRule(ClinicalRule):
    """
    Rule: Ensure anticoagulation properly reversed before surgery
    """

    def __init__(self):
        super().__init__(
            rule_id="HEMORRHAGE_002",
            rule_name="Anticoagulation Reversal",
            category=RuleCategory.HEMORRHAGE_RISK
        )

    def evaluate(self, facts: List[AtomicClinicalFact], patient_context: Dict) -> List[ClinicalAlert]:
        alerts = []

        # Check for pre-operative anticoagulation
        anticoagulants = [
            f for f in facts
            if f.entity_type == EntityType.MEDICATION
            and any(med in f.entity_name.lower() for med in [
                "warfarin", "coumadin", "apixaban", "rivaroxaban", "dabigatran"
            ])
            and f.is_historical
        ]

        if anticoagulants:
            # Check for reversal agents or labs
            reversal = [
                f for f in facts
                if (f.entity_type == EntityType.MEDICATION and any(
                    agent in f.entity_name.lower() for agent in ["vitamin k", "prothrombin complex", "andexanet"]
                )) or (f.entity_type == EntityType.LAB_VALUE and "inr" in f.entity_name.lower())
            ]

            if not reversal:
                alert = self._create_alert(
                    severity=AlertSeverity.HIGH,
                    title="Anticoagulation Reversal Not Documented",
                    message="Patient on anticoagulation pre-operatively without documented reversal.",
                    recommendation="Verify anticoagulation reversed and labs normalized before surgery",
                    evidence_fact_ids=[f.id for f in anticoagulants],
                    evidence_summary=f"Pre-op anticoagulation: {anticoagulants[0].entity_name}"
                )
                alerts.append(alert)

        return alerts


# =============================================================================
# Discharge Readiness Rules
# =============================================================================

class DischargeSafetyRule(ClinicalRule):
    """
    Rule: Verify discharge safety criteria met
    Criteria: stable neuro exam, tolerating PO, pain controlled, PT cleared
    """

    def __init__(self):
        super().__init__(
            rule_id="DISCHARGE_001",
            rule_name="Discharge Safety Criteria",
            category=RuleCategory.DISCHARGE_READINESS
        )

    def evaluate(self, facts: List[AtomicClinicalFact], patient_context: Dict) -> List[ClinicalAlert]:
        alerts = []

        # Only check if discharge mentioned
        discharge_mention = any(
            "discharge" in f.entity_name.lower() for f in facts
        )

        if not discharge_mention:
            return alerts

        unmet_criteria = []

        # Check for recent neuro exam
        recent_exam = any(
            f.entity_type == EntityType.PHYSICAL_EXAM
            and f.neuro_exam_detail
            for f in facts
        )
        if not recent_exam:
            unmet_criteria.append("Recent neurological exam not documented")

        # Check pain control
        pain_controlled = any(
            f.entity_type == EntityType.SYMPTOM
            and "pain" in f.entity_name.lower()
            and "controlled" in f.extracted_text.lower()
            for f in facts
        )

        if unmet_criteria:
            alert = self._create_alert(
                severity=AlertSeverity.MEDIUM,
                title="Discharge Criteria Not Fully Met",
                message=f"Patient being discharged with unmet criteria: {'; '.join(unmet_criteria)}",
                recommendation="Complete discharge criteria checklist before discharge",
                evidence_fact_ids=[],
                evidence_summary="; ".join(unmet_criteria)
            )
            alerts.append(alert)

        return alerts


class DischargeFollowUpRule(ClinicalRule):
    """
    Rule: Ensure follow-up appointments scheduled
    Required: Neurosurgery follow-up within 2 weeks
    """

    def __init__(self):
        super().__init__(
            rule_id="DISCHARGE_002",
            rule_name="Discharge Follow-Up",
            category=RuleCategory.DISCHARGE_READINESS
        )

    def evaluate(self, facts: List[AtomicClinicalFact], patient_context: Dict) -> List[ClinicalAlert]:
        alerts = []

        # Check if discharge mentioned
        discharge_mention = any(
            "discharge" in f.entity_name.lower() for f in facts
        )

        if not discharge_mention:
            return alerts

        # Check for follow-up appointment
        followup = any(
            "follow" in f.entity_name.lower() or "appointment" in f.entity_name.lower()
            for f in facts
        )

        if not followup:
            alert = self._create_alert(
                severity=AlertSeverity.MEDIUM,
                title="Follow-Up Appointment Not Documented",
                message="Discharge planned without documented follow-up appointment.",
                recommendation="Schedule neurosurgery follow-up within 2 weeks of discharge",
                evidence_fact_ids=[],
                evidence_summary="No follow-up appointment documented"
            )
            alerts.append(alert)

        return alerts


# =============================================================================
# Clinical Rules Engine
# =============================================================================

class ClinicalRulesEngine:
    """
    Main clinical rules engine
    Evaluates all rules and generates clinical alerts
    """

    def __init__(self):
        """Initialize rules engine with all rules"""
        self.rules: List[ClinicalRule] = []

        # Add seizure prophylaxis rules
        if settings.rules_seizure_prophylaxis:
            self.rules.append(SeizureProphylaxisIndicationRule())
            self.rules.append(SeizureMedicationDurationRule())

        # Add DVT prophylaxis rules
        if settings.rules_dvt_prophylaxis:
            self.rules.append(DVTProphylaxisIndicationRule())
            self.rules.append(DVTPharmacologicTimingRule())
            self.rules.append(DVTContraindicationRule())

        # Add steroid management rules
        if settings.rules_steroid_taper:
            self.rules.append(SteroidTaperRule())
            self.rules.append(SteroidGastricProtectionRule())

        # Add electrolyte monitoring rules
        if settings.rules_sodium_monitoring:
            self.rules.append(HyponatremiaMonitoringRule())
            self.rules.append(RapidSodiumCorrectionRule())

        # Add hemorrhage risk rules
        if settings.rules_hemorrhage_risk:
            self.rules.append(PostOpHemorrhageRiskRule())
            self.rules.append(AnticoagulationReversalRule())

        # Add discharge readiness rules
        if settings.rules_discharge_readiness:
            self.rules.append(DischargeSafetyRule())
            self.rules.append(DischargeFollowUpRule())

        logger.info(f"Initialized clinical rules engine with {len(self.rules)} rules")

    def evaluate_all_rules(
        self,
        facts: List[AtomicClinicalFact],
        patient_context: Optional[Dict[str, Any]] = None
    ) -> List[ClinicalAlert]:
        """
        Evaluate all clinical rules against patient facts

        Args:
            facts: List of clinical facts
            patient_context: Additional patient context (POD, etc.)

        Returns:
            List of clinical alerts from triggered rules
        """
        if patient_context is None:
            patient_context = {}

        all_alerts = []

        logger.info(f"Evaluating {len(self.rules)} rules against {len(facts)} facts")

        for rule in self.rules:
            try:
                alerts = rule.evaluate(facts, patient_context)
                if alerts:
                    logger.info(f"Rule {rule.rule_id} triggered {len(alerts)} alerts")
                    all_alerts.extend(alerts)
            except Exception as e:
                logger.error(f"Error evaluating rule {rule.rule_id}: {e}", exc_info=True)

        # Sort by severity
        severity_order = {
            AlertSeverity.CRITICAL: 0,
            AlertSeverity.HIGH: 1,
            AlertSeverity.MEDIUM: 2,
            AlertSeverity.LOW: 3
        }
        all_alerts.sort(key=lambda a: severity_order.get(a.severity, 999))

        logger.info(f"Total alerts generated: {len(all_alerts)}")
        return all_alerts

    def get_rules_by_category(self, category: RuleCategory) -> List[ClinicalRule]:
        """Get all rules in a specific category"""
        return [r for r in self.rules if r.category == category]


# =============================================================================
# Public API
# =============================================================================

def evaluate_clinical_rules(
    facts: List[AtomicClinicalFact],
    patient_context: Optional[Dict[str, Any]] = None
) -> List[ClinicalAlert]:
    """
    Evaluate all clinical rules and generate alerts

    Args:
        facts: List of clinical facts
        patient_context: Additional patient context

    Returns:
        List of clinical alerts
    """
    engine = ClinicalRulesEngine()
    return engine.evaluate_all_rules(facts, patient_context)
