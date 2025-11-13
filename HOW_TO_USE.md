# How to Use NeuroscribeAI - Practical Guide

Complete guide for inputting clinical documentation and extracting structured data.

---

## Quick Start: 3 Ways to Use the System

### Method 1: Interactive Web UI (Easiest) 🌐

**Best for**: Testing, exploring, manual document processing

1. **Open the API documentation**:
   ```bash
   open http://localhost:8000/docs
   ```

2. **Navigate to the extraction endpoint**:
   - Find "POST /api/v1/extract" in the list
   - Click to expand it
   - Click "Try it out" button

3. **Enter your clinical text**:
   - `text`: Paste your clinical note
   - `patient_id`: Enter a number (e.g., 1)
   - `document_id`: Enter a number (e.g., 1)

4. **Click "Execute"**

5. **View results**: Extracted entities appear in the response below

---

### Method 2: Upload Files via API 📄

**Best for**: Processing document files (PDF, DOCX, TXT)

#### Using the Web Interface:

1. Go to http://localhost:8000/docs
2. Find "POST /api/v1/extract/file"
3. Click "Try it out"
4. Click "Choose File" and select your document
5. Enter patient_id and document_id
6. Click "Execute"

#### Using cURL:

```bash
curl -X POST "http://localhost:8000/api/v1/extract/file" \
  -F "file=@/path/to/your/clinical_note.pdf" \
  -F "patient_id=1" \
  -F "document_id=1"
```

**Supported formats**: PDF, DOCX, TXT

---

### Method 3: Command Line (cURL) 💻

**Best for**: Automation, scripting, batch processing

#### Basic Extraction:

```bash
curl -X POST "http://localhost:8000/api/v1/extract" \
  -G \
  --data-urlencode "text=Patient underwent left frontal craniotomy for glioblastoma. Currently on dexamethasone 4mg BID and levetiracetam 500mg BID. POD 3, GCS 15." \
  --data-urlencode "patient_id=1" \
  --data-urlencode "document_id=1" \
  | python3 -m json.tool
```

#### Extract from File:

```bash
# Create a sample clinical note
cat > sample_note.txt << 'EOF'
PATIENT: John Doe, 67M

PROCEDURE: Left frontal craniotomy for glioblastoma resection

CURRENT STATUS (POD 5):
- Neurologically stable
- GCS 15
- Motor strength 5/5 throughout

MEDICATIONS:
- Dexamethasone 4mg QID
- Levetiracetam 500mg BID
- Enoxaparin 40mg daily

LABS:
- Sodium: 138 mEq/L
- Hemoglobin: 12.5 g/dL
EOF

# Extract from file
curl -X POST "http://localhost:8000/api/v1/extract/file" \
  -F "file=@sample_note.txt" \
  -F "patient_id=1" \
  -F "document_id=1" \
  | python3 -m json.tool
```

---

## What Gets Extracted

NeuroscribeAI automatically identifies and extracts:

### 1. **Diagnoses**
- Primary and secondary diagnoses
- Pathology findings
- Tumor grades and types

Example: `glioblastoma multiforme`, `WHO grade IV`

### 2. **Procedures**
- Surgical procedures
- Interventions
- Approaches

Example: `craniotomy`, `resection`, `biopsy`

### 3. **Medications**
- Drug names (generic and brand)
- Dosages
- Frequencies (BID, TID, QID, etc.)
- Routes

Example: `dexamethasone 4mg BID`, `levetiracetam 500mg BID`

### 4. **Physical Exam Findings**
- Glasgow Coma Scale (GCS)
- Motor strength
- Cranial nerve exam
- Sensory exam

Example: `GCS 15`, `motor 5/5`, `deltoid strength 5/5`

### 5. **Lab Values**
- Lab test names
- Values
- Units

Example: `Sodium: 138 mEq/L`, `Hemoglobin: 12.5 g/dL`

### 6. **Anatomical Context**
- Laterality (left, right, bilateral)
- Brain regions (frontal, temporal, etc.)
- Spinal levels
- Size measurements

Example: `left frontal`, `right temporal`, `C5-C6`

### 7. **Temporal Information**
- Post-operative day (POD)
- Hospital day (HD)
- Dates
- Relative time expressions

Example: `POD 5`, `HD 3`, `11/08/2024`

---

## Complete Workflow Example

### Step 1: Extract Facts from Clinical Note

```bash
# Create a sample clinical document
cat > discharge_summary.txt << 'EOF'
DISCHARGE SUMMARY

Patient: Jane Smith, 58F
MRN: 123456
Date: 11/13/2024

ADMISSION DIAGNOSIS:
Right parietal glioblastoma

PROCEDURES PERFORMED:
1. Right parietal craniotomy with frameless stereotactic navigation
2. Gross total resection of right parietal tumor
3. External ventricular drain (EVD) placement

HOSPITAL COURSE:
Patient underwent successful right parietal craniotomy on 11/08/2024 for
glioblastoma resection. Pathology confirmed WHO grade IV astrocytoma,
IDH1 wild-type, MGMT promoter unmethylated.

Post-operatively, patient remained neurologically stable. Maintained on:
- Dexamethasone 4mg Q6H (to taper to BID over 2 weeks)
- Levetiracetam 500mg BID for seizure prophylaxis
- Enoxaparin 40mg daily for DVT prophylaxis
- Acetaminophen 650mg Q6H PRN pain

PHYSICAL EXAMINATION (POD 5):
- Vital Signs: BP 128/76, HR 72, Temp 98.6F
- Neurological: GCS 15, alert and oriented x3
- Motor: 5/5 strength throughout
- Sensory: Intact to light touch
- Incision: Clean, dry, intact. No signs of infection.

LABS (11/13/2024):
- Sodium: 138 mEq/L (normal)
- Potassium: 4.2 mEq/L
- Hemoglobin: 12.5 g/dL
- WBC: 8.2 K/uL
- Platelets: 245 K/uL

IMAGING:
Post-op MRI (11/10/2024): Expected post-surgical changes in right parietal
region. No acute hemorrhage. No significant edema.

DISCHARGE MEDICATIONS:
1. Dexamethasone 4mg BID x 1 week, then 2mg BID x 1 week, then off
2. Levetiracetam 500mg BID
3. Enoxaparin 40mg daily x 4 weeks
4. Acetaminophen 650mg Q6H PRN

FOLLOW-UP:
- Neurosurgery clinic in 1 week
- Oncology consultation for adjuvant therapy
- Wound check in 10 days for staple removal
EOF

# Extract structured data
curl -X POST "http://localhost:8000/api/v1/extract/file" \
  -F "file=@discharge_summary.txt" \
  -F "patient_id=123456" \
  -F "document_id=1" \
  > extracted_data.json

# View results
python3 -m json.tool < extracted_data.json | head -100
```

### Step 2: What You Get Back

The system returns a JSON array of extracted facts:

```json
[
  {
    "entity_type": "DIAGNOSIS",
    "entity_name": "glioblastoma",
    "extracted_text": "glioblastoma multiforme",
    "confidence_score": 0.95,
    "extraction_method": "scispacy_ner",
    "anatomical_context": {
      "laterality": "right",
      "brain_region": "parietal"
    },
    "temporal_context": {
      "pod": 5
    }
  },
  {
    "entity_type": "PROCEDURE",
    "entity_name": "craniotomy",
    "confidence_score": 0.90,
    "extraction_method": "rule_based",
    "anatomical_context": {
      "laterality": "right",
      "brain_region": "parietal"
    }
  },
  {
    "entity_type": "MEDICATION",
    "entity_name": "dexamethasone",
    "medication_detail": {
      "generic_name": "dexamethasone",
      "dose_value": 4.0,
      "dose_unit": "mg",
      "frequency": "Q6H"
    }
  }
  // ... more entities
]
```

### Step 3: Use the Complete Pipeline

For full processing (extraction + validation + timeline + summary):

```bash
curl -X POST "http://localhost:8000/api/v1/pipeline/complete" \
  -H "Content-Type: application/json" \
  -d '{
    "text": "YOUR CLINICAL TEXT HERE",
    "patient_id": 123456,
    "document_id": 1,
    "summary_type": "discharge_summary",
    "patient_context": {"pod": 5}
  }' | python3 -m json.tool
```

---

## Real-World Use Cases

### Use Case 1: Process Daily Progress Notes

```python
# Python script for batch processing
import requests

progress_notes = [
    {"text": "POD 1: Patient stable, GCS 15...", "patient_id": 1, "doc_id": 1},
    {"text": "POD 2: Continues to improve...", "patient_id": 1, "doc_id": 2},
    {"text": "POD 3: Ready for discharge...", "patient_id": 1, "doc_id": 3},
]

for note in progress_notes:
    response = requests.post(
        "http://localhost:8000/api/v1/extract",
        params={
            "text": note["text"],
            "patient_id": note["patient_id"],
            "document_id": note["doc_id"]
        }
    )
    facts = response.json()
    print(f"Document {note['doc_id']}: {len(facts)} facts extracted")
```

### Use Case 2: Upload Multiple Documents

```bash
# Process multiple files
for file in clinical_notes/*.txt; do
    echo "Processing: $file"
    curl -X POST "http://localhost:8000/api/v1/extract/file" \
      -F "file=@$file" \
      -F "patient_id=1" \
      -F "document_id=$(basename $file .txt)" \
      -o "extracted_$(basename $file .txt).json"
done
```

### Use Case 3: Generate Timeline

```bash
# After extracting facts from multiple documents,
# build a temporal timeline

curl -X POST "http://localhost:8000/api/v1/temporal/timeline" \
  -H "Content-Type: application/json" \
  -d '{
    "patient_id": 1,
    "facts": [/* array of extracted facts */]
  }' | python3 -m json.tool
```

### Use Case 4: Evaluate Clinical Rules

```bash
# Check for clinical safety issues
curl -X POST "http://localhost:8000/api/v1/rules/evaluate" \
  -H "Content-Type: application/json" \
  -d '{
    "patient_id": 1,
    "facts": [/* array of extracted facts */],
    "patient_context": {"pod": 5, "procedure": "craniotomy"}
  }' | python3 -m json.tool

# Returns clinical alerts like:
# - Missing seizure prophylaxis
# - DVT prophylaxis needed
# - Steroid taper required
# - Sodium monitoring needed
```

---

## Python Integration Example

### Complete Python Client

```python
#!/usr/bin/env python3
"""
NeuroscribeAI Python Client Example
Process clinical documents and extract structured data
"""

import requests
import json
from pathlib import Path

class NeuroscribeClient:
    def __init__(self, base_url="http://localhost:8000"):
        self.base_url = base_url

    def extract_from_text(self, text: str, patient_id: int, document_id: int):
        """Extract clinical facts from text"""
        response = requests.post(
            f"{self.base_url}/api/v1/extract",
            params={
                "text": text,
                "patient_id": patient_id,
                "document_id": document_id
            }
        )
        response.raise_for_status()
        return response.json()

    def extract_from_file(self, file_path: str, patient_id: int, document_id: int):
        """Extract from document file"""
        with open(file_path, 'rb') as f:
            response = requests.post(
                f"{self.base_url}/api/v1/extract/file",
                files={"file": f},
                data={
                    "patient_id": patient_id,
                    "document_id": document_id
                }
            )
        response.raise_for_status()
        return response.json()

    def complete_pipeline(self, text: str, patient_id: int, document_id: int):
        """Run complete extraction + validation + summarization pipeline"""
        response = requests.post(
            f"{self.base_url}/api/v1/pipeline/complete",
            json={
                "text": text,
                "patient_id": patient_id,
                "document_id": document_id,
                "summary_type": "discharge_summary",
                "include_timeline": True
            }
        )
        response.raise_for_status()
        return response.json()

# Example usage
if __name__ == "__main__":
    client = NeuroscribeClient()

    # Process a clinical note
    text = """
    Patient underwent left frontal craniotomy for glioblastoma.
    Currently POD 3 on dexamethasone 4mg BID.
    GCS 15, neurologically stable.
    """

    facts = client.extract_from_text(text, patient_id=1, document_id=1)

    print(f"Extracted {len(facts)} clinical facts:")
    for fact in facts:
        print(f"  - {fact['entity_type']}: {fact['entity_name']}")
```

Save this as `client.py` and run:
```bash
python3 client.py
```

---

## Sample Clinical Documents to Test

### Example 1: Simple Progress Note

```
PROGRESS NOTE - POD 3

S: Patient reports feeling well. No headaches, nausea, or visual changes.

O:
- Vital signs stable
- GCS 15, alert and oriented x3
- Motor: 5/5 throughout
- Incision: Clean, dry, intact

Current meds:
- Dexamethasone 4mg BID
- Keppra 500mg BID
- Lovenox 40mg daily

Labs today:
- Sodium 138
- Hemoglobin 12.5

A: Neurologically stable POD 3 s/p left frontal craniotomy for GBM

P: Continue current medications, advance diet as tolerated, PT/OT consults
```

**What gets extracted**:
- Temporal: POD 3
- Vital Signs: GCS 15
- Motor exam: 5/5 throughout
- 3 Medications with dosages
- 2 Lab values
- Diagnosis: GBM (glioblastoma)
- Procedure: craniotomy
- Anatomical: left frontal

### Example 2: Operative Note

```
OPERATIVE NOTE

PREOPERATIVE DIAGNOSIS: Right temporal glioblastoma

PROCEDURE: Right temporal craniotomy with stereotactic navigation and
intraoperative motor mapping

FINDINGS:
- Firm, grayish tumor in right temporal lobe
- Tumor size approximately 4.5 x 3.2 x 3.8 cm
- Invasion into insular cortex
- Preserved motor cortex

PROCEDURE DETAILS:
Standard pterional craniotomy was performed. Tumor was debulked using
ultrasonic aspiration. Gross total resection achieved based on
intraoperative MRI.

EBL: 300 mL
```

**What gets extracted**:
- Diagnosis: glioblastoma
- Procedure: craniotomy
- Anatomical: right temporal, insular cortex
- Size: 4.5 x 3.2 x 3.8 cm (with volume calculation)
- Finding: gross total resection
- Lab: EBL 300 mL

---

## Advanced Usage

### Validate Extracted Data

```bash
curl -X POST "http://localhost:8000/api/v1/validate" \
  -H "Content-Type: application/json" \
  -d '{
    "patient_id": 1,
    "facts": [/* array of extracted facts */]
  }' | python3 -m json.tool
```

Returns validation report with:
- Completeness score (0-100)
- Accuracy score (0-100)
- Critical issues
- Missing data warnings

### Build Patient Timeline

```bash
curl -X POST "http://localhost:8000/api/v1/temporal/timeline" \
  -H "Content-Type: application/json" \
  -d '{
    "patient_id": 1,
    "facts": [/* facts from multiple documents */]
  }' | python3 -m json.tool
```

Returns chronological timeline of:
- Surgical events
- Medication changes
- Lab trends
- Clinical milestones

### Generate Clinical Summary

```bash
curl -X POST "http://localhost:8000/api/v1/summarize" \
  -H "Content-Type: application/json" \
  -d '{
    "patient_mrn": "123456",
    "summary_type": "discharge_summary",
    "include_timeline": true
  }' | python3 -m json.tool
```

---

## Input Format Tips

### Best Practices for Input Text

✅ **DO**:
- Include context (patient age, diagnosis)
- Use standard medical abbreviations
- Include temporal markers (POD, HD, dates)
- Specify laterality (left/right)
- Include units for measurements

❌ **DON'T**:
- Remove all formatting (keep structure helps extraction)
- Use non-standard abbreviations without context
- Omit critical information

### Formatting That Helps Extraction

**Good**:
```
MEDICATIONS:
- Dexamethasone 4mg BID
- Levetiracetam 500mg BID

LABS:
- Sodium: 138 mEq/L
- Hemoglobin: 12.5 g/dL
```

**Also works but less structured**:
```
Currently on dexamethasone 4mg BID and levetiracetam 500mg BID.
Sodium is 138, hemoglobin 12.5.
```

Both will be extracted, but structured format may give slightly better results.

---

## Batch Processing Script

### Process Multiple Documents

```bash
#!/bin/bash
# batch_process.sh - Process all clinical documents in a directory

PATIENT_ID=1
DOC_ID=1

for file in clinical_notes/*; do
    echo "Processing: $file"

    curl -X POST "http://localhost:8000/api/v1/extract/file" \
      -F "file=@$file" \
      -F "patient_id=$PATIENT_ID" \
      -F "document_id=$DOC_ID" \
      -o "results/extracted_${DOC_ID}.json"

    echo "✓ Saved to results/extracted_${DOC_ID}.json"
    DOC_ID=$((DOC_ID + 1))
done

echo "Batch processing complete!"
```

---

## Troubleshooting

### Issue: "No entities extracted"

**Possible causes**:
1. Text too short (< 50 characters)
2. No medical entities in text
3. Non-English text

**Solution**: Add more clinical context, ensure medical terminology is present

### Issue: "Extraction timeout"

**Possible causes**:
- Text too long (> 10,000 words)
- Complex processing

**Solution**:
- Break into smaller chunks
- Increase timeout in .env: `EXTRACTION_TIMEOUT=600`

### Issue: Low confidence scores

**Possible causes**:
- Ambiguous text
- Non-standard terminology
- Complex medical relationships

**Solution**: Add API keys for LLM-enhanced extraction (see ACTIVATE_LLM.md)

---

## Next Steps

1. **Try the interactive interface**: http://localhost:8000/docs
2. **Test with sample clinical text** (examples above)
3. **Process your own clinical documents**
4. **Explore validation and timeline features**
5. **Add API keys for enhanced accuracy** (optional)

---

## Quick Reference

**API Documentation**: http://localhost:8000/docs
**Health Check**: http://localhost:8000/health
**Example Text**: See examples above
**File Upload**: Supports PDF, DOCX, TXT

**Support Docs**:
- QUICK_START.md - Getting started
- SYSTEM_STATUS_REPORT.md - System capabilities
- API_KEYS_SETUP.md - Enhanced features

---

The system is ready to process your clinical documentation right now!
Visit http://localhost:8000/docs to start extracting structured data.
