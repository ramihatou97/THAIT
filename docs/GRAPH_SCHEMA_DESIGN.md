# NeuroscribeAI - Knowledge Graph Schema Design

**Version**: 1.0
**Date**: 2025-11-13
**Purpose**: Define Neo4j graph schema for clinical knowledge representation

---

## Overview

The knowledge graph transforms relational clinical data into a network of interconnected entities, enabling:
- **Relationship Discovery**: Find causal links between diagnoses, procedures, and outcomes
- **Pattern Detection**: Identify common treatment pathways
- **Temporal Reasoning**: Track disease progression and intervention timelines
- **Cohort Analysis**: Find patients with similar clinical profiles
- **Evidence-Based Insights**: Query treatment efficacy across patient population

---

## Graph Schema

### Node Types

#### 1. Patient Node
```cypher
(:Patient {
  id: Integer,              // PostgreSQL ID
  mrn: String (UNIQUE),     // Medical Record Number
  age: Integer,
  sex: String,
  primary_diagnosis: String,
  created_at: DateTime,
  updated_at: DateTime
})
```

**Indexes**: `CREATE INDEX ON :Patient(mrn)`

---

#### 2. Diagnosis Node
```cypher
(:Diagnosis {
  id: Integer,              // Fact ID from PostgreSQL
  name: String (INDEXED),   // Canonical diagnosis name
  extracted_text: String,
  laterality: String,       // left, right, bilateral
  brain_region: String,     // frontal, temporal, parietal, etc.
  size_mm: Float,           // Tumor size if applicable
  volume_cc: Float,
  who_grade: String,        // For tumors: I, II, III, IV
  confidence: Float,
  extraction_method: String,
  timestamp: DateTime
})
```

**Indexes**:
- `CREATE INDEX ON :Diagnosis(name)`
- `CREATE FULLTEXT INDEX diagnosis_text FOR (d:Diagnosis) ON EACH [d.name, d.extracted_text]`

---

#### 3. Procedure Node
```cypher
(:Procedure {
  id: Integer,
  name: String (INDEXED),
  procedure_type: String,   // surgical, diagnostic, therapeutic
  approach: String,
  laterality: String,
  brain_region: String,
  duration_minutes: Integer,
  confidence: Float,
  timestamp: DateTime,
  pod: Integer              // Post-operative day context
})
```

---

#### 4. Medication Node
```cypher
(:Medication {
  id: Integer,
  generic_name: String (INDEXED),
  brand_name: String,
  dose_value: Float,
  dose_unit: String,
  frequency: String,        // BID, TID, Q4H, etc.
  route: String,            // PO, IV, SubQ, etc.
  is_prn: Boolean,
  start_date: DateTime,
  end_date: DateTime,
  taper_schedule: String
})
```

**Indexes**: `CREATE INDEX ON :Medication(generic_name)`

---

#### 5. LabValue Node
```cypher
(:LabValue {
  id: Integer,
  test_name: String (INDEXED),
  value: Float,
  unit: String,
  normal: Boolean,
  critical: Boolean,
  timestamp: DateTime
})
```

---

#### 6. PhysicalExam Node
```cypher
(:PhysicalExam {
  id: Integer,
  exam_type: String,        // GCS, motor, sensory, cranial_nerve
  gcs_total: Integer,
  gcs_eye: Integer,
  gcs_verbal: Integer,
  gcs_motor: Integer,
  motor_details: String,    // JSON string of motor exam
  timestamp: DateTime,
  pod: Integer
})
```

---

#### 7. ImagingFinding Node
```cypher
(:ImagingFinding {
  id: Integer,
  modality: String,         // MRI, CT, angiogram
  finding: String,
  laterality: String,
  brain_region: String,
  size_mm: Float,
  midline_shift_mm: Float,
  timestamp: DateTime
})
```

---

#### 8. Symptom Node
```cypher
(:Symptom {
  id: Integer,
  name: String (INDEXED),
  severity: String,         // mild, moderate, severe
  onset: String,            // acute, chronic, progressive
  is_negated: Boolean,      // "no headaches" = true
  timestamp: DateTime
})
```

---

#### 9. Document Node
```cypher
(:Document {
  id: Integer,
  document_type: String,    // discharge_summary, progress_note, operative_note
  title: String,
  upload_date: DateTime,
  processed: Boolean,
  fact_count: Integer
})
```

---

#### 10. TemporalEvent Node
```cypher
(:TemporalEvent {
  id: Integer,
  event_type: String,       // surgery, admission, discharge, complication
  event_date: DateTime,
  pod: Integer,
  hospital_day: Integer,
  description: String
})
```

---

### Relationship Types

#### Patient-Centered Relationships

```cypher
(:Patient)-[:HAS_DIAGNOSIS {
  diagnosed_date: DateTime,
  is_primary: Boolean,
  confidence: Float,
  source_document_id: Integer
}]->(:Diagnosis)

(:Patient)-[:UNDERWENT_PROCEDURE {
  procedure_date: DateTime,
  pod: Integer,
  indication: String,
  outcome: String,
  source_document_id: Integer
}]->(:Procedure)

(:Patient)-[:TAKES_MEDICATION {
  start_date: DateTime,
  end_date: DateTime,
  indication: String,
  source_document_id: Integer
}]->(:Medication)

(:Patient)-[:HAS_LAB {
  test_date: DateTime,
  pod: Integer,
  source_document_id: Integer
}]->(:LabValue)

(:Patient)-[:HAS_EXAM {
  exam_date: DateTime,
  pod: Integer,
  source_document_id: Integer
}]->(:PhysicalExam)

(:Patient)-[:EXHIBITS_SYMPTOM {
  onset_date: DateTime,
  resolved_date: DateTime,
  severity: String
}]->(:Symptom)

(:Patient)-[:HAS_IMAGING {
  study_date: DateTime,
  indication: String
}]->(:ImagingFinding)

(:Patient)-[:HAS_DOCUMENT {
  uploaded_at: DateTime
}]->(:Document)
```

---

#### Clinical Logic Relationships

```cypher
// Diagnosis leads to Procedure
(:Diagnosis)-[:INDICATED_PROCEDURE {
  confidence: Float,
  time_gap_days: Integer
}]->(:Procedure)

// Procedure leads to new Diagnosis (complications)
(:Procedure)-[:RESULTED_IN_DIAGNOSIS {
  time_gap_days: Integer,
  is_complication: Boolean
}]->(:Diagnosis)

// Medication prescribed for Diagnosis
(:Medication)-[:PRESCRIBED_FOR {
  indication: String,
  prophylaxis: Boolean      // true for seizure prophylaxis, DVT prophylaxis
}]->(:Diagnosis)

// Medication prescribed after Procedure
(:Medication)-[:POST_PROCEDURE {
  indication: String,       // "edema control", "seizure prophylaxis"
  standard_protocol: Boolean
}]->(:Procedure)

// Lab values track Medication effects
(:LabValue)-[:MONITORS {
  parameter: String         // "sodium for dexamethasone", "CBC for chemotherapy"
}]->(:Medication)

// Imaging shows Diagnosis
(:ImagingFinding)-[:CONFIRMS {
  confidence: Float
}]->(:Diagnosis)

// Symptoms suggest Diagnosis
(:Symptom)-[:SUGGESTS {
  confidence: Float,
  correlation_strength: Float
}]->(:Diagnosis)
```

---

#### Temporal Relationships

```cypher
// Sequencing of events
(:Fact)-[:TEMPORAL_BEFORE {
  days_difference: Integer,
  same_patient: Boolean
}]->(:Fact)

(:Fact)-[:TEMPORAL_AFTER {
  days_difference: Integer
}]->(:Fact)

// Concurrent events
(:Fact)-[:CONCURRENT_WITH {
  same_pod: Boolean,
  time_diff_hours: Integer
}]->(:Fact)
```

---

#### Validation & Quality Relationships

```cypher
// Facts that contradict each other
(:Fact)-[:CONTRADICTS {
  contradiction_type: String,
  confidence: Float
}]->(:Fact)

// Facts that support/corroborate each other
(:Fact)-[:SUPPORTS {
  support_type: String,
  confidence: Float
}]->(:Fact)

// Document contains facts
(:Document)-[:CONTAINS_FACT {
  position_in_doc: Integer
}]->(:Fact)
```

---

## Graph Construction Logic

### Phase 1: Node Creation (From PostgreSQL)

**Input**: AtomicClinicalFact from PostgreSQL
**Process**:
1. Determine entity type (DIAGNOSIS, PROCEDURE, MEDICATION, etc.)
2. Create corresponding node type
3. Populate properties from fact fields
4. Store Neo4j node ID back to PostgreSQL `neo4j_node_id`
5. Mark `synced_to_neo4j = True`

**Cypher Template**:
```cypher
MERGE (e:Diagnosis {id: $fact_id})
SET e.name = $entity_name,
    e.extracted_text = $extracted_text,
    e.laterality = $laterality,
    e.brain_region = $brain_region,
    e.confidence = $confidence,
    e.timestamp = datetime($timestamp)
RETURN elementId(e) as neo4j_id
```

---

### Phase 2: Patient-Entity Relationships

**Process**:
1. For each fact, create relationship from Patient to entity node
2. Populate relationship properties (dates, confidence, context)
3. Enable queries: "MATCH (p:Patient {mrn: 'X'})-[:HAS_DIAGNOSIS]->(d) RETURN d"

**Cypher Template**:
```cypher
MATCH (p:Patient {id: $patient_id})
MATCH (d:Diagnosis {id: $diagnosis_id})
MERGE (p)-[r:HAS_DIAGNOSIS]->(d)
SET r.diagnosed_date = datetime($date),
    r.is_primary = $is_primary,
    r.confidence = $confidence,
    r.source_document_id = $document_id
```

---

### Phase 3: Clinical Logic Relationships

**Diagnosis → Procedure Linking**:
```python
# Logic: If procedure occurs within 30 days after diagnosis
# with matching anatomical location, create INDICATED_PROCEDURE relationship

if diagnosis.brain_region == procedure.brain_region:
    if 0 < (procedure.date - diagnosis.date).days <= 30:
        create_relationship(diagnosis, "INDICATED_PROCEDURE", procedure)
```

**Medication → Diagnosis Linking**:
```python
# Common neurosurgical protocols:
protocols = {
    "dexamethasone": ["glioblastoma", "edema", "mass_effect"],
    "levetiracetam": ["glioblastoma", "craniotomy"],  # seizure prophylaxis
    "enoxaparin": ["craniotomy", "craniectomy"]       # DVT prophylaxis
}

if medication.generic_name in protocols:
    for diagnosis_name in patient.diagnoses:
        if any(keyword in diagnosis_name for keyword in protocols[medication.generic_name]):
            create_relationship(medication, "PRESCRIBED_FOR", diagnosis)
```

---

### Phase 4: Temporal Relationships

**Build Timeline**:
```python
# Sort all facts by timestamp/POD
sorted_facts = sort_by_temporal_context(patient_facts)

# Create TEMPORAL_BEFORE relationships
for i, fact in enumerate(sorted_facts[:-1]):
    next_fact = sorted_facts[i+1]
    days_diff = calculate_days_difference(fact, next_fact)
    create_relationship(fact, "TEMPORAL_BEFORE", next_fact,
                       properties={"days_difference": days_diff})
```

---

## Query Patterns (Use Cases)

### Query 1: Find All Treatments for Diagnosis

```cypher
MATCH (p:Patient)-[:HAS_DIAGNOSIS]->(d:Diagnosis {name: "glioblastoma"})
MATCH (p)-[:UNDERWENT_PROCEDURE]->(proc)
MATCH (p)-[:TAKES_MEDICATION]->(med)
RETURN p.mrn, d.name,
       collect(DISTINCT proc.name) as procedures,
       collect(DISTINCT med.generic_name) as medications
```

**Use Case**: "What procedures and medications are typically used for glioblastoma patients?"

---

### Query 2: Find Similar Patients

```cypher
MATCH (target:Patient {mrn: $target_mrn})-[:HAS_DIAGNOSIS]->(d:Diagnosis)
MATCH (similar:Patient)-[:HAS_DIAGNOSIS]->(d)
WHERE similar <> target
WITH similar, count(d) as shared_diagnoses
MATCH (similar)-[:UNDERWENT_PROCEDURE]->(p:Procedure)
MATCH (target:Patient {mrn: $target_mrn})-[:UNDERWENT_PROCEDURE]->(p)
WITH similar, shared_diagnoses, count(p) as shared_procedures
WHERE shared_diagnoses >= 2 OR shared_procedures >= 1
RETURN similar.mrn, similar.age, similar.sex,
       shared_diagnoses, shared_procedures
ORDER BY (shared_diagnoses + shared_procedures) DESC
LIMIT 10
```

**Use Case**: "Find patients most similar to this one for treatment insights"

---

### Query 3: Temporal Treatment Pathway

```cypher
MATCH path = (p:Patient {mrn: $mrn})-[:HAS_DIAGNOSIS]->(d:Diagnosis)
              -[:INDICATED_PROCEDURE]->(proc:Procedure)
              -[:RESULTED_IN_DIAGNOSIS]->(complication:Diagnosis)
RETURN path
ORDER BY d.timestamp
```

**Use Case**: "Show disease progression and intervention timeline"

---

### Query 4: Medication Protocols

```cypher
MATCH (p:Patient)-[:HAS_DIAGNOSIS]->(d:Diagnosis {name: "glioblastoma"})
MATCH (p)-[r:TAKES_MEDICATION]->(m:Medication)
WITH m.generic_name as medication, count(p) as patient_count
WHERE patient_count >= 5
RETURN medication, patient_count,
       (patient_count * 100.0 / $total_glio_patients) as percentage
ORDER BY patient_count DESC
```

**Use Case**: "What medications do most glioblastoma patients receive?"

---

### Query 5: Complication Detection

```cypher
MATCH (p:Patient)-[:UNDERWENT_PROCEDURE]->(proc:Procedure)
MATCH (p)-[:HAS_DIAGNOSIS]->(comp:Diagnosis)
WHERE comp.timestamp > proc.timestamp
  AND duration.between(proc.timestamp, comp.timestamp).days <= 30
WITH proc.name as procedure, comp.name as complication, count(p) as occurrences
WHERE occurrences >= 3
RETURN procedure, complication, occurrences,
       (occurrences * 100.0 / $total_procedures) as complication_rate
ORDER BY complication_rate DESC
```

**Use Case**: "What are the most common complications after craniotomy?"

---

### Query 6: Treatment Effectiveness

```cypher
MATCH (p:Patient)-[:HAS_DIAGNOSIS]->(d:Diagnosis {name: "glioblastoma"})
MATCH (p)-[:UNDERWENT_PROCEDURE]->(proc:Procedure)
MATCH (p)-[:TAKES_MEDICATION]->(med:Medication)
OPTIONAL MATCH (p)-[:HAS_DIAGNOSIS]->(recurrence:Diagnosis {name: "recurrence"})
WITH proc.name as procedure,
     collect(DISTINCT med.generic_name) as med_regimen,
     count(DISTINCT p) as total_patients,
     count(recurrence) as recurrences
RETURN procedure, med_regimen, total_patients, recurrences,
       ((total_patients - recurrences) * 100.0 / total_patients) as success_rate
ORDER BY success_rate DESC
```

**Use Case**: "Which treatment combinations have best outcomes?"

---

## Implementation Strategy

### Step 1: Sync Existing Data

```python
def sync_all_patients_to_graph():
    """One-time sync of all PostgreSQL data to Neo4j"""
    patients = session.query(Patient).all()
    for patient in patients:
        sync_patient_to_graph(patient)
        sync_patient_facts_to_graph(patient.id)
```

### Step 2: Incremental Sync

```python
def sync_new_fact_to_graph(fact: AtomicClinicalFact):
    """Real-time sync when new fact is extracted"""
    1. Create entity node
    2. Create Patient-Entity relationship
    3. Infer clinical logic relationships
    4. Build temporal relationships
    5. Update fact.neo4j_node_id and synced_to_neo4j
```

### Step 3: Relationship Inference

```python
def infer_clinical_relationships(patient_id: int):
    """Analyze all patient facts and infer logical relationships"""

    # Example: Medication → Diagnosis
    medications = get_patient_medications(patient_id)
    diagnoses = get_patient_diagnoses(patient_id)

    for med in medications:
        if med.generic_name == "dexamethasone":
            for diag in diagnoses:
                if "glioblastoma" in diag.entity_name or "edema" in diag.entity_name:
                    create_graph_relationship(
                        med_node_id, "PRESCRIBED_FOR", diag_node_id,
                        {"indication": "tumor edema control", "prophylaxis": False}
                    )
```

---

## Performance Considerations

### Indexes
```cypher
// Required for query performance
CREATE INDEX patient_mrn FOR (p:Patient) ON (p.mrn)
CREATE INDEX diagnosis_name FOR (d:Diagnosis) ON (d.name)
CREATE INDEX medication_generic FOR (m:Medication) ON (m.generic_name)
CREATE INDEX procedure_name FOR (proc:Procedure) ON (proc.name)

// Full-text search
CREATE FULLTEXT INDEX entity_search FOR (n:Diagnosis|Procedure|Medication|Symptom)
ON EACH [n.name, n.extracted_text]
```

### Constraints
```cypher
// Ensure uniqueness
CREATE CONSTRAINT patient_id_unique FOR (p:Patient) REQUIRE p.id IS UNIQUE
CREATE CONSTRAINT fact_id_unique FOR (f:Diagnosis) REQUIRE f.id IS UNIQUE
```

---

## Data Flow

### Extraction → Graph Sync

```
User uploads document
       ↓
Extraction pipeline runs
       ↓
Facts stored in PostgreSQL (atomic_clinical_facts table)
       ↓
Background Celery task triggered: sync_to_neo4j_task.delay(patient_id)
       ↓
Neo4jGraphService.sync_patient_facts(patient_id)
       ↓
1. Create entity nodes in Neo4j
2. Create Patient-Entity relationships
3. Infer clinical logic relationships
4. Build temporal relationships
5. Update PostgreSQL with neo4j_node_id
       ↓
Graph ready for queries
```

---

## Benefits Analysis

### Clinical Benefits

1. **Relationship Discovery**
   - "Show me all complications that occurred after craniotomy"
   - "Which medications are associated with lower complication rates?"

2. **Treatment Patterns**
   - "What's the typical steroid taper protocol?"
   - "How long do patients stay on seizure prophylaxis?"

3. **Outcome Prediction**
   - "Patients with this profile typically had X outcome"
   - "Risk factors for readmission"

4. **Evidence-Based Medicine**
   - "Treatment pathways with best outcomes"
   - "Standard of care adherence"

### Research Benefits

1. **Cohort Building**
   - Find all patients with specific criteria
   - Build matched control groups

2. **Pattern Mining**
   - Discover novel relationships
   - Hypothesis generation

3. **Temporal Analysis**
   - Disease progression patterns
   - Intervention timing optimization

### Operational Benefits

1. **Quality Improvement**
   - Track compliance with protocols
   - Identify process inefficiencies

2. **Decision Support**
   - "Other similar patients received..."
   - Alert if deviating from common pathways

---

## Graph Maintenance

### Sync Strategies

**Option A: Real-time Sync**
- Trigger on every fact insert
- Pros: Always up-to-date
- Cons: Higher latency on extraction

**Option B: Batch Sync**
- Scheduled job (e.g., hourly)
- Pros: Better performance
- Cons: Slight delay

**Option C: Hybrid** (Recommended)
- Critical data: Real-time (diagnoses, procedures)
- Less critical: Batch (labs, vitals)

### Update Strategy

```python
def update_fact_in_graph(fact_id: int):
    """Update node properties when fact is modified"""
    fact = get_fact_by_id(fact_id)
    if fact.neo4j_node_id:
        update_node_properties(fact.neo4j_node_id, fact.to_dict())
        rebuild_relationships(fact_id)  # Relationships may have changed
```

### Deletion Strategy

```python
def delete_fact_from_graph(fact_id: int):
    """Remove node and relationships when fact is deleted"""
    # Cypher: MATCH (n {id: $fact_id}) DETACH DELETE n
```

---

## Success Metrics

### Performance Targets

- Node creation: <50ms per node
- Relationship creation: <20ms per relationship
- Query response: <200ms for simple queries, <2s for complex
- Sync throughput: 1000+ facts/minute

### Quality Targets

- Sync accuracy: 100% (all facts represented)
- Relationship accuracy: >90% (inferred relationships are valid)
- Query reliability: 100% (queries always return results)

---

## Next Steps

1. **Implement Neo4jGraphService** (app/services/neo4j_service.py)
2. **Add sync methods to extraction pipeline**
3. **Create background sync Celery task**
4. **Build graph query endpoints** (app/routes/graph.py)
5. **Test with real clinical data**
6. **Optimize indexes and constraints**
7. **Document query examples for clinicians**

---

This schema provides a solid foundation for clinical knowledge representation,
enabling advanced queries, pattern discovery, and evidence-based insights.
