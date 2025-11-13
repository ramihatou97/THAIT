# NeuroscribeAI - Quick Start Guide

## Prerequisites

- Docker Desktop installed and running
- (Optional) Python 3.11+ for local development
- (Optional) API keys for OpenAI or Anthropic

## 1. Setup Environment

```bash
# Navigate to project directory
cd ~/Desktop/neuroscribe-ai

# Copy environment template
cp .env.example .env

# Edit .env file (optional - has defaults)
nano .env

# Key settings to configure (optional):
# - OPENAI_API_KEY=your-key-here
# - ANTHROPIC_API_KEY=your-key-here
# - LLM_PROVIDER=anthropic (or openai)
```

## 2. Download NER Models (Local Development Only)

**Note**: If using Docker, skip this step - models are downloaded automatically during build.

For local development without Docker:
```bash
# Download required spaCy and scispaCy models
./scripts/download_models.sh

# Verify models are installed
python3 scripts/test_models.py
```

See [MODEL_SETUP.md](MODEL_SETUP.md) for detailed instructions and troubleshooting.

## 3. Start All Services

```bash
# Start all services in background (includes automatic model download)
docker-compose up -d

# View logs to confirm models loaded
docker-compose logs -f api | grep "Model loading"

# Check service status
docker-compose ps
```

**Expected services:**
- ✅ postgres (port 5432)
- ✅ redis (port 6379)
- ✅ neo4j (ports 7474, 7687)
- ✅ api (port 8000)
- ✅ celery-worker
- ✅ prometheus (port 9090)
- ✅ grafana (port 3000)

## 4. Verify System Health

```bash
# Check API health
curl http://localhost:8000/health

# Expected response:
# {
#   "status": "healthy",
#   "timestamp": "2024-...",
#   "version": "1.0.0",
#   "environment": "development"
# }

# Check readiness (models loaded)
curl http://localhost:8000/health/ready
```

## 5. Test Extraction

### Example 1: Simple Extraction

```bash
curl -X POST "http://localhost:8000/api/v1/extract" \
  -H "Content-Type: application/json" \
  -d '{
    "text": "Patient underwent left frontal craniotomy for glioblastoma. Currently on dexamethasone 4mg BID and levetiracetam 500mg BID for seizure prophylaxis. POD 3, neurologically stable.",
    "patient_id": 1,
    "document_id": 1
  }'
```

**Expected output**: JSON array of extracted facts with:
- Procedure: left frontal craniotomy
- Diagnosis: glioblastoma
- Medications: dexamethasone, levetiracetam
- Temporal: POD 3

### Example 2: Complete Pipeline

```bash
curl -X POST "http://localhost:8000/api/v1/pipeline/complete" \
  -H "Content-Type: application/json" \
  -d '{
    "text": "45-year-old male underwent left frontal craniotomy for glioblastoma resection on 11/10/2024. Currently POD 3. On dexamethasone 4mg BID, levetiracetam 500mg BID. GCS 15, motor 5/5 throughout. Sodium 138. MRI shows expected post-op changes.",
    "patient_id": 1,
    "document_id": 1,
    "summary_type": "discharge_summary",
    "patient_context": {"pod": 3}
  }' | jq .
```

**Expected output**: Complete pipeline results including:
- ✅ Extracted facts
- ✅ Validation report
- ✅ Clinical alerts
- ✅ Generated summary

## 5. Access Web Interfaces

### API Documentation
```
http://localhost:8000/docs
```
Interactive Swagger UI for testing all endpoints

### Neo4j Browser
```
http://localhost:7474
Username: neo4j
Password: neo4j_password
```

### Prometheus Metrics
```
http://localhost:9090
```

### Grafana Dashboards
```
http://localhost:3000
Username: admin
Password: admin
```

## 6. Common Operations

### View Logs
```bash
# All services
docker-compose logs -f

# Specific service
docker-compose logs -f api
docker-compose logs -f postgres
```

### Restart Services
```bash
# Restart all
docker-compose restart

# Restart specific service
docker-compose restart api
```

### Stop Services
```bash
# Stop all (keeps data)
docker-compose down

# Stop and remove volumes (fresh start)
docker-compose down -v
```

### Access Container Shell
```bash
# API container
docker exec -it neuroscribe-api bash

# PostgreSQL
docker exec -it neuroscribe-postgres psql -U neuroscribe -d neuroscribe
```

## 7. Testing Specific Features

### Test Clinical Rules
```bash
curl -X POST "http://localhost:8000/api/v1/rules/evaluate" \
  -H "Content-Type: application/json" \
  -d '{
    "facts": [
      {
        "entity_type": "PROCEDURE",
        "entity_name": "left frontal craniotomy",
        "extracted_text": "craniotomy",
        "source_snippet": "underwent craniotomy",
        "confidence_score": 0.95,
        "extraction_method": "rule_based",
        "anatomical_context": {
          "laterality": "left",
          "brain_region": "frontal"
        }
      }
    ],
    "patient_context": {"pod": 5}
  }' | jq .
```

**Expected**: Alert about seizure prophylaxis if not documented

### Test Validation
```bash
curl -X POST "http://localhost:8000/api/v1/validate" \
  -H "Content-Type: application/json" \
  -d '{
    "facts": [...],
    "source_text": "original document text",
    "patient_id": 1
  }' | jq .
```

**Expected**: Validation report with scores and issues

## 8. Sample Clinical Note

Use this sample for testing:

```
DISCHARGE SUMMARY

Patient: John Doe
MRN: 12345678
Age: 45 years
Sex: Male

ADMISSION DATE: 11/10/2024
DISCHARGE DATE: 11/15/2024
SURGERY DATE: 11/10/2024

PRIMARY DIAGNOSIS:
Left frontal glioblastoma, WHO grade IV

PROCEDURES PERFORMED:
1. Left frontal craniotomy for tumor resection (11/10/2024)
2. Intraoperative MRI
3. Awake craniotomy with motor mapping

HOSPITAL COURSE:
Patient is a 45-year-old right-handed male who presented with new-onset seizures. MRI revealed a 3.5 x 2.8 x 2.1 cm heterogeneously enhancing left frontal mass with surrounding edema. He underwent left frontal craniotomy with near-total resection.

POSTOPERATIVE COURSE:
- POD 0: Neurologically intact, GCS 15, motor 5/5 throughout
- POD 1: Started on enoxaparin 40mg SQ daily for DVT prophylaxis
- POD 2: Physical therapy evaluation, ambulating independently
- POD 3: Drain removed, sodium 138 mmol/L
- POD 4: Post-op MRI shows expected changes, no hemorrhage
- POD 5: Discharge planning, neurosurgery follow-up scheduled

NEUROLOGICAL EXAMINATION AT DISCHARGE:
- Mental status: Alert and oriented x3
- GCS: 15 (E4 V5 M6)
- Motor: 5/5 strength throughout all extremities
- Cranial nerves: II-XII intact
- Sensory: Intact to light touch
- Coordination: Normal finger-to-nose

DISCHARGE MEDICATIONS:
1. Dexamethasone 4mg PO BID (taper: 3mg BID x3d, 2mg BID x3d, then discontinue)
2. Levetiracetam 500mg PO BID
3. Pantoprazole 40mg PO daily
4. Acetaminophen 650mg PO q6h PRN pain
5. Oxycodone 5mg PO q4h PRN severe pain

DISCHARGE CONDITION:
Neurologically stable, ambulating independently, pain well controlled

FOLLOW-UP:
- Neurosurgery clinic in 2 weeks
- Oncology consult for adjuvant therapy
- Pathology: Glioblastoma, WHO grade IV, IDH wildtype

DISCHARGE INSTRUCTIONS:
- Keep incision clean and dry
- No heavy lifting >10 lbs for 6 weeks
- May shower, no submersion
- Return to ED for severe headache, vision changes, weakness, seizures
- Continue seizure precautions
```

Save to file and test:

```bash
echo "DISCHARGE SUMMARY..." > /tmp/sample_note.txt

curl -X POST "http://localhost:8000/api/v1/extract/file" \
  -F "file=@/tmp/sample_note.txt" \
  -F "patient_id=1" \
  -F "document_id=1" | jq .
```

## 9. Troubleshooting

### NER Models Not Loading
```bash
# Download models manually
docker exec -it neuroscribe-api bash
python -m spacy download en_core_web_sm
python -m spacy download en_ner_bc5cdr_md
exit

# Restart API
docker-compose restart api
```

### Database Connection Issues
```bash
# Check PostgreSQL logs
docker-compose logs postgres

# Reset database
docker-compose down -v
docker-compose up -d
```

### Port Already in Use
```bash
# Find process using port 8000
lsof -i :8000

# Kill process
kill -9 <PID>

# Or change port in docker-compose.yml
```

### Memory Issues
```bash
# Increase Docker memory limit in Docker Desktop settings
# Recommended: 8GB RAM, 4 CPU cores
```

## 10. Development Mode

### Local Development (without Docker)

```bash
# Create virtual environment
python3.11 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
python -m spacy download en_core_web_sm
python -m spacy download en_ner_bc5cdr_md

# Start databases (Docker)
docker-compose up -d postgres redis neo4j

# Run API locally
uvicorn app.main:app --reload --port 8000
```

### Run Tests
```bash
# Activate virtual environment
source venv/bin/activate

# Run all tests
pytest tests/ -v

# Run specific test file
pytest tests/test_extraction.py -v

# Run with coverage
pytest --cov=app --cov-report=html
```

## 11. Production Deployment

### Update Configuration
```bash
# Edit .env
ENVIRONMENT=production
DEBUG=false
API_RELOAD=false
SECRET_KEY=<generate-secure-key>
```

### Generate Secure Key
```bash
python -c "import secrets; print(secrets.token_urlsafe(32))"
```

### Build and Deploy
```bash
# Build production image
docker-compose build

# Deploy
docker-compose up -d

# Check health
curl http://localhost:8000/health
```

## 12. Monitoring

### Check Metrics
```bash
# Prometheus metrics
curl http://localhost:8000/metrics

# System health
curl http://localhost:8000/health/ready
```

### View Dashboards
- Prometheus: http://localhost:9090
- Grafana: http://localhost:3000

## Need Help?

- 📖 **Full Documentation**: See README.md
- 📋 **Implementation Details**: See IMPLEMENTATION_SUMMARY.md
- 🐛 **Issues**: Check logs with `docker-compose logs -f`
- 💬 **API Docs**: http://localhost:8000/docs

---

**🎉 You're ready to use NeuroscribeAI!**

Start with the sample clinical note above and explore the API endpoints through the Swagger UI at http://localhost:8000/docs
