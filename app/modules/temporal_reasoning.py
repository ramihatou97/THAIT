"""
NeuroscribeAI Temporal Reasoning Engine
POD resolution, timeline construction, conflict detection for 98%+ accuracy
"""

import re
import logging
from typing import List, Dict, Optional, Tuple, Set
from datetime import datetime, timedelta
from dateutil import parser as date_parser
from collections import defaultdict

from app.schemas import AtomicClinicalFact, TemporalContext
from app.config import settings

logger = logging.getLogger(__name__)


# =============================================================================
# Temporal Expression Patterns
# =============================================================================

class TemporalPatterns:
    """Patterns for temporal expression extraction"""

    # Post-operative day
    POD_PATTERN = re.compile(
        r'\b(?:POD|post-?op(?:erative)?\s+day)\s*#?\s*(\d+)\b',
        re.IGNORECASE
    )

    # Hospital day
    HD_PATTERN = re.compile(
        r'\b(?:HD|hospital\s+day)\s*#?\s*(\d+)\b',
        re.IGNORECASE
    )

    # Relative temporal expressions
    RELATIVE_TIME = re.compile(
        r'\b(today|yesterday|tomorrow|tonight|this morning|this afternoon|this evening)\b',
        re.IGNORECASE
    )

    # Time expressions with number of days
    DAYS_AGO = re.compile(
        r'\b(\d+)\s+days?\s+ago\b',
        re.IGNORECASE
    )

    DAYS_LATER = re.compile(
        r'\b(\d+)\s+days?\s+later\b',
        re.IGNORECASE
    )

    # Duration expressions
    DURATION = re.compile(
        r'\b(?:for|during|over)\s+(\d+)\s+(hours?|days?|weeks?|months?)\b',
        re.IGNORECASE
    )

    # Specific times
    TIME_OF_DAY = re.compile(
        r'\b(\d{1,2}):(\d{2})\s*(am|pm|AM|PM)?\b'
    )

    # Date patterns
    DATE_NUMERIC = re.compile(
        r'\b(\d{1,2})/(\d{1,2})/(\d{2,4})\b'
    )

    DATE_WRITTEN = re.compile(
        r'\b(January|February|March|April|May|June|July|August|September|October|November|December)\s+(\d{1,2}),?\s+(\d{4})\b',
        re.IGNORECASE
    )

    # Sequence indicators
    SEQUENCE_BEFORE = re.compile(
        r'\b(before|prior to|preceding)\b',
        re.IGNORECASE
    )

    SEQUENCE_AFTER = re.compile(
        r'\b(after|following|subsequent to)\b',
        re.IGNORECASE
    )


# =============================================================================
# Temporal Event Class
# =============================================================================

class TemporalEvent:
    """Represents a temporal event in the patient timeline"""

    def __init__(
        self,
        event_id: str,
        event_type: str,
        event_name: str,
        timestamp: Optional[datetime] = None,
        pod: Optional[int] = None,
        hospital_day: Optional[int] = None,
        relative_time: Optional[str] = None,
        fact_ids: Optional[List[int]] = None,
        confidence: float = 1.0
    ):
        self.event_id = event_id
        self.event_type = event_type
        self.event_name = event_name
        self.timestamp = timestamp
        self.pod = pod
        self.hospital_day = hospital_day
        self.relative_time = relative_time
        self.fact_ids = fact_ids or []
        self.confidence = confidence
        self.resolved_timestamp: Optional[datetime] = None

    def __repr__(self) -> str:
        return (
            f"TemporalEvent(id={self.event_id}, name={self.event_name}, "
            f"timestamp={self.timestamp}, pod={self.pod}, hd={self.hospital_day})"
        )

    def has_absolute_time(self) -> bool:
        """Check if event has absolute timestamp"""
        return self.timestamp is not None or self.resolved_timestamp is not None

    def has_relative_time(self) -> bool:
        """Check if event has relative time markers"""
        return any([self.pod is not None, self.hospital_day is not None, self.relative_time])


# =============================================================================
# Temporal Conflict Detection
# =============================================================================

class TemporalConflict:
    """Represents a temporal conflict between events"""

    def __init__(
        self,
        conflict_type: str,
        event1: TemporalEvent,
        event2: TemporalEvent,
        description: str,
        severity: str = "warning"
    ):
        self.conflict_type = conflict_type
        self.event1 = event1
        self.event2 = event2
        self.description = description
        self.severity = severity

    def __repr__(self) -> str:
        return f"TemporalConflict({self.conflict_type}: {self.description})"


class ConflictDetector:
    """Detects temporal conflicts and impossible sequences"""

    @staticmethod
    def detect_conflicts(events: List[TemporalEvent]) -> List[TemporalConflict]:
        """
        Detect all temporal conflicts in event list

        Args:
            events: List of temporal events

        Returns:
            List of detected conflicts
        """
        conflicts = []

        # Sort events by resolved timestamp
        resolved_events = [e for e in events if e.resolved_timestamp]
        resolved_events.sort(key=lambda e: e.resolved_timestamp)

        # Check for impossible POD sequences
        conflicts.extend(ConflictDetector._check_pod_conflicts(events))

        # Check for temporal ordering violations
        conflicts.extend(ConflictDetector._check_ordering_conflicts(resolved_events))

        # Check for impossible durations
        conflicts.extend(ConflictDetector._check_duration_conflicts(resolved_events))

        # Check for maximum POD violations
        conflicts.extend(ConflictDetector._check_max_pod(events))

        return conflicts

    @staticmethod
    def _check_pod_conflicts(events: List[TemporalEvent]) -> List[TemporalConflict]:
        """Check for POD-related conflicts"""
        conflicts = []

        pod_events = [e for e in events if e.pod is not None]

        # Check for same POD with conflicting timestamps
        pod_groups = defaultdict(list)
        for event in pod_events:
            if event.resolved_timestamp:
                pod_groups[event.pod].append(event)

        for pod, pod_event_list in pod_groups.items():
            if len(pod_event_list) > 1:
                # Check if timestamps differ by more than 1 day
                timestamps = [e.resolved_timestamp for e in pod_event_list]
                min_time = min(timestamps)
                max_time = max(timestamps)

                if (max_time - min_time) > timedelta(days=1):
                    conflict = TemporalConflict(
                        conflict_type="pod_timestamp_mismatch",
                        event1=pod_event_list[0],
                        event2=pod_event_list[1],
                        description=f"POD {pod} has events with timestamps differing by {(max_time - min_time).days} days",
                        severity="critical"
                    )
                    conflicts.append(conflict)

        return conflicts

    @staticmethod
    def _check_ordering_conflicts(events: List[TemporalEvent]) -> List[TemporalConflict]:
        """Check for temporal ordering violations"""
        conflicts = []

        # Check for surgery before admission
        admission_events = [e for e in events if e.event_type == "admission"]
        surgery_events = [e for e in events if e.event_type == "procedure"]

        for admission in admission_events:
            for surgery in surgery_events:
                if admission.resolved_timestamp and surgery.resolved_timestamp:
                    if surgery.resolved_timestamp < admission.resolved_timestamp:
                        conflict = TemporalConflict(
                            conflict_type="impossible_sequence",
                            event1=surgery,
                            event2=admission,
                            description="Surgery timestamp before admission timestamp",
                            severity="critical"
                        )
                        conflicts.append(conflict)

        # Check for discharge before admission
        discharge_events = [e for e in events if e.event_type == "discharge"]

        for admission in admission_events:
            for discharge in discharge_events:
                if admission.resolved_timestamp and discharge.resolved_timestamp:
                    if discharge.resolved_timestamp < admission.resolved_timestamp:
                        conflict = TemporalConflict(
                            conflict_type="impossible_sequence",
                            event1=discharge,
                            event2=admission,
                            description="Discharge timestamp before admission timestamp",
                            severity="critical"
                        )
                        conflicts.append(conflict)

        return conflicts

    @staticmethod
    def _check_duration_conflicts(events: List[TemporalEvent]) -> List[TemporalConflict]:
        """Check for impossible durations between events"""
        conflicts = []

        # Check surgery duration (should be < 24 hours typically)
        surgery_events = [e for e in events if "surgery" in e.event_name.lower()]

        for i in range(len(surgery_events) - 1):
            if surgery_events[i].resolved_timestamp and surgery_events[i+1].resolved_timestamp:
                duration = surgery_events[i+1].resolved_timestamp - surgery_events[i].resolved_timestamp
                if timedelta(minutes=1) < duration < timedelta(minutes=30):
                    # Two surgeries within 30 minutes is unusual
                    conflict = TemporalConflict(
                        conflict_type="unlikely_duration",
                        event1=surgery_events[i],
                        event2=surgery_events[i+1],
                        description=f"Two surgeries within {duration.total_seconds()/60:.0f} minutes",
                        severity="warning"
                    )
                    conflicts.append(conflict)

        return conflicts

    @staticmethod
    def _check_max_pod(events: List[TemporalEvent]) -> List[TemporalConflict]:
        """Check for POD values exceeding maximum plausible value"""
        conflicts = []

        max_pod = settings.temporal_max_pod

        for event in events:
            if event.pod and event.pod > max_pod:
                conflict = TemporalConflict(
                    conflict_type="excessive_pod",
                    event1=event,
                    event2=event,
                    description=f"POD {event.pod} exceeds maximum plausible value of {max_pod}",
                    severity="warning"
                )
                conflicts.append(conflict)

        return conflicts


# =============================================================================
# Timeline Construction
# =============================================================================

class PatientTimeline:
    """Constructs and manages patient clinical timeline"""

    def __init__(self, patient_id: int):
        self.patient_id = patient_id
        self.events: List[TemporalEvent] = []
        self.anchor_date: Optional[datetime] = None  # Surgery/admission date
        self.conflicts: List[TemporalConflict] = []

    def add_event(self, event: TemporalEvent):
        """Add event to timeline"""
        self.events.append(event)

    def set_anchor_date(self, anchor_date: datetime):
        """Set anchor date for relative time resolution"""
        self.anchor_date = anchor_date
        logger.info(f"Set anchor date for patient {self.patient_id}: {anchor_date}")

    def resolve_temporal_references(self):
        """Resolve all relative temporal references to absolute timestamps"""
        if not self.anchor_date:
            logger.warning("No anchor date set, attempting to infer...")
            self._infer_anchor_date()

        if not self.anchor_date:
            logger.error("Could not resolve anchor date, timeline resolution incomplete")
            return

        # Resolve POD references
        for event in self.events:
            if event.pod is not None and not event.resolved_timestamp:
                event.resolved_timestamp = self.anchor_date + timedelta(days=event.pod)
                logger.debug(f"Resolved POD {event.pod} to {event.resolved_timestamp}")

        # Resolve hospital day references
        admission_date = self._find_admission_date()
        if admission_date:
            for event in self.events:
                if event.hospital_day is not None and not event.resolved_timestamp:
                    event.resolved_timestamp = admission_date + timedelta(days=event.hospital_day - 1)
                    logger.debug(f"Resolved HD {event.hospital_day} to {event.resolved_timestamp}")

        # Copy explicit timestamps to resolved_timestamp
        for event in self.events:
            if event.timestamp and not event.resolved_timestamp:
                event.resolved_timestamp = event.timestamp

        # Sort events chronologically
        self.events.sort(key=lambda e: e.resolved_timestamp if e.resolved_timestamp else datetime.max)

    def _infer_anchor_date(self):
        """Infer anchor date (surgery date) from explicit dates and POD references"""
        # Find events with explicit dates
        dated_events = [e for e in self.events if e.timestamp]

        # Find events with POD
        pod_events = [e for e in self.events if e.pod is not None]

        if not dated_events or not pod_events:
            return

        # Try to infer surgery date by subtracting POD from known dates
        inferred_dates = []
        for dated_event in dated_events:
            for pod_event in pod_events:
                if dated_event.event_id == pod_event.event_id:
                    surgery_date = dated_event.timestamp - timedelta(days=pod_event.pod)
                    inferred_dates.append(surgery_date)

        if inferred_dates:
            # Use most common inferred date
            self.anchor_date = max(set(inferred_dates), key=inferred_dates.count)
            logger.info(f"Inferred anchor date: {self.anchor_date}")

    def _find_admission_date(self) -> Optional[datetime]:
        """Find admission date from events"""
        admission_events = [e for e in self.events if e.event_type == "admission"]
        if admission_events and admission_events[0].resolved_timestamp:
            return admission_events[0].resolved_timestamp
        return self.anchor_date

    def detect_conflicts(self):
        """Detect temporal conflicts in timeline"""
        self.conflicts = ConflictDetector.detect_conflicts(self.events)

        if self.conflicts:
            logger.warning(f"Detected {len(self.conflicts)} temporal conflicts")
            for conflict in self.conflicts:
                logger.warning(f"  - {conflict.description}")

    def get_events_by_type(self, event_type: str) -> List[TemporalEvent]:
        """Get all events of specific type"""
        return [e for e in self.events if e.event_type == event_type]

    def get_events_in_range(
        self,
        start_date: datetime,
        end_date: datetime
    ) -> List[TemporalEvent]:
        """Get events within date range"""
        return [
            e for e in self.events
            if e.resolved_timestamp and start_date <= e.resolved_timestamp <= end_date
        ]

    def get_timeline_summary(self) -> Dict:
        """Get summary of timeline"""
        resolved_events = [e for e in self.events if e.resolved_timestamp]

        return {
            "patient_id": self.patient_id,
            "total_events": len(self.events),
            "resolved_events": len(resolved_events),
            "anchor_date": self.anchor_date.isoformat() if self.anchor_date else None,
            "conflicts": len(self.conflicts),
            "critical_conflicts": len([c for c in self.conflicts if c.severity == "critical"]),
            "event_types": self._count_event_types(),
            "date_range": self._get_date_range()
        }

    def _count_event_types(self) -> Dict[str, int]:
        """Count events by type"""
        counts = defaultdict(int)
        for event in self.events:
            counts[event.event_type] += 1
        return dict(counts)

    def _get_date_range(self) -> Optional[Dict[str, str]]:
        """Get date range of timeline"""
        resolved_events = [e for e in self.events if e.resolved_timestamp]
        if not resolved_events:
            return None

        timestamps = [e.resolved_timestamp for e in resolved_events]
        return {
            "start": min(timestamps).isoformat(),
            "end": max(timestamps).isoformat()
        }


# =============================================================================
# Temporal Reasoning Engine
# =============================================================================

class TemporalReasoningEngine:
    """
    Main temporal reasoning engine for clinical timeline construction
    Target: 98%+ temporal accuracy
    """

    def __init__(self):
        """Initialize temporal reasoning engine"""
        pass

    def build_timeline(
        self,
        facts: List[AtomicClinicalFact],
        patient_id: int,
        anchor_date: Optional[datetime] = None
    ) -> PatientTimeline:
        """
        Build patient timeline from clinical facts

        Args:
            facts: List of clinical facts
            patient_id: Patient ID
            anchor_date: Optional anchor date (surgery/admission)

        Returns:
            Constructed patient timeline
        """
        logger.info(f"Building timeline for patient {patient_id} with {len(facts)} facts")

        timeline = PatientTimeline(patient_id)

        if anchor_date:
            timeline.set_anchor_date(anchor_date)

        # Convert facts to temporal events
        for i, fact in enumerate(facts):
            event = self._fact_to_event(fact, event_id=f"event_{i}")
            timeline.add_event(event)

        # Resolve temporal references
        timeline.resolve_temporal_references()

        # Detect conflicts
        timeline.detect_conflicts()

        logger.info(f"Timeline construction complete: {timeline.get_timeline_summary()}")

        return timeline

    def _fact_to_event(self, fact: AtomicClinicalFact, event_id: str) -> TemporalEvent:
        """Convert clinical fact to temporal event"""

        # Extract temporal information from fact
        timestamp = None
        pod = None
        hospital_day = None
        relative_time = None

        if fact.temporal_context:
            timestamp = fact.temporal_context.get("timestamp")
            pod = fact.temporal_context.get("pod")
            hospital_day = fact.temporal_context.get("hospital_day")
            relative_time = fact.temporal_context.get("relative_time")

        # Use fact's resolved_timestamp if available
        if fact.resolved_timestamp:
            timestamp = fact.resolved_timestamp

        return TemporalEvent(
            event_id=event_id,
            event_type=fact.entity_type,
            event_name=fact.entity_name,
            timestamp=timestamp,
            pod=pod,
            hospital_day=hospital_day,
            relative_time=relative_time,
            fact_ids=[fact.id] if hasattr(fact, 'id') else [],
            confidence=fact.confidence_score
        )

    def calculate_temporal_distance(
        self,
        event1: TemporalEvent,
        event2: TemporalEvent
    ) -> Optional[timedelta]:
        """
        Calculate temporal distance between two events

        Args:
            event1: First event
            event2: Second event

        Returns:
            Time delta between events, or None if cannot be calculated
        """
        if event1.resolved_timestamp and event2.resolved_timestamp:
            return abs(event2.resolved_timestamp - event1.resolved_timestamp)

        # Try to calculate from POD if available
        if event1.pod is not None and event2.pod is not None:
            return timedelta(days=abs(event2.pod - event1.pod))

        # Try to calculate from hospital day
        if event1.hospital_day is not None and event2.hospital_day is not None:
            return timedelta(days=abs(event2.hospital_day - event1.hospital_day))

        return None

    def find_temporally_related_facts(
        self,
        target_fact: AtomicClinicalFact,
        all_facts: List[AtomicClinicalFact],
        max_distance_days: int = 7
    ) -> List[Tuple[AtomicClinicalFact, timedelta]]:
        """
        Find facts temporally related to target fact

        Args:
            target_fact: Target fact
            all_facts: All facts to search
            max_distance_days: Maximum temporal distance in days

        Returns:
            List of (fact, temporal_distance) tuples
        """
        if not target_fact.resolved_timestamp:
            return []

        related = []

        for fact in all_facts:
            if fact == target_fact:
                continue

            if fact.resolved_timestamp:
                distance = abs(fact.resolved_timestamp - target_fact.resolved_timestamp)
                if distance <= timedelta(days=max_distance_days):
                    related.append((fact, distance))

        # Sort by distance
        related.sort(key=lambda x: x[1])

        return related


# =============================================================================
# Public API
# =============================================================================

def build_patient_timeline(
    facts: List[AtomicClinicalFact],
    patient_id: int,
    anchor_date: Optional[datetime] = None
) -> PatientTimeline:
    """
    Build patient timeline from clinical facts

    Args:
        facts: List of clinical facts
        patient_id: Patient ID
        anchor_date: Optional anchor date

    Returns:
        Constructed patient timeline
    """
    engine = TemporalReasoningEngine()
    return engine.build_timeline(facts, patient_id, anchor_date)


def detect_temporal_conflicts(timeline: PatientTimeline) -> List[TemporalConflict]:
    """
    Detect temporal conflicts in timeline

    Args:
        timeline: Patient timeline

    Returns:
        List of detected conflicts
    """
    return ConflictDetector.detect_conflicts(timeline.events)
