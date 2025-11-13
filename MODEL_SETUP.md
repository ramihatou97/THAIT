# NeuroscribeAI - NER Model Setup Guide

Complete guide for downloading and configuring NER models for clinical text extraction.

## Overview

NeuroscribeAI uses a hybrid extraction approach combining three types of NER models:

1. **spaCy** - General English language processing
2. **scispaCy** - Biomedical and clinical entity recognition
3. **BioBERT** - Advanced transformer-based biomedical NER

## Quick Start

### Option 1: Automated Setup (Recommended)

```bash
# Run the automated download script
./scripts/download_models.sh
```

This will:
- Check Python installation
- Verify required packages are installed
- Download all necessary models
- Verify installations
- Report any errors

### Option 2: Docker Setup (Production)

```bash
# Build Docker image (includes model downloads)
docker-compose build

# Start all services
docker-compose up -d

# Verify models loaded
docker-compose logs api | grep "Model loading"
```

Models are automatically downloaded during the Docker build process.

### Option 3: Manual Setup

See the [Manual Installation](#manual-installation) section below.

## Model Details

### 1. spaCy General Model

**Model**: `en_core_web_sm`
- **Size**: ~13 MB
- **Purpose**: General English NER, tokenization, POS tagging
- **Entities**: PERSON, ORG, GPE, DATE, MONEY, etc.
- **Installation**:
  ```bash
  python3 -m spacy download en_core_web_sm
  ```

### 2. scispaCy Biomedical Models

**Primary Model**: `en_ner_bc5cdr_md`
- **Size**: ~100 MB
- **Purpose**: Biomedical entity recognition
- **Trained on**: BioCreative V CDR task corpus
- **Entities**: DISEASE, CHEMICAL (includes medications)
- **Installation**:
  ```bash
  pip install https://s3-us-west-2.amazonaws.com/ai2-s2-scispacy/releases/v0.5.3/en_ner_bc5cdr_md-0.5.3.tar.gz
  ```

**Secondary Model**: `en_core_sci_sm`
- **Size**: ~15 MB
- **Purpose**: Scientific text processing
- **Installation**:
  ```bash
  pip install https://s3-us-west-2.amazonaws.com/ai2-s2-scispacy/releases/v0.5.3/en_core_sci_sm-0.5.3.tar.gz
  ```

### 3. BioBERT Transformer Model

**Model**: `dmis-lab/biobert-base-cased-v1.2`
- **Size**: ~420 MB
- **Purpose**: Advanced biomedical NER using transformers
- **Installation**: Auto-downloads from Hugging Face on first use
- **Controlled by**: `EXTRACTION_USE_LLM=true` in `.env`

## Installation Steps

### Prerequisites

1. **Python 3.8+** (Python 3.11+ recommended)
   ```bash
   python3 --version  # Should show 3.8 or higher
   ```

2. **Required packages** (from requirements.txt)
   ```bash
   pip install -r requirements.txt
   ```

3. **Storage space**: ~550 MB free disk space

### Installation Process

#### Step 1: Set up Python Environment

**For local development** (recommended):
```bash
# Create virtual environment
python3 -m venv venv

# Activate virtual environment
source venv/bin/activate  # On macOS/Linux
# OR
venv\Scripts\activate  # On Windows

# Install requirements
pip install -r requirements.txt
```

**For system-wide installation**:
```bash
# Install requirements directly
pip install -r requirements.txt
```

#### Step 2: Download Models

**Automated (recommended)**:
```bash
./scripts/download_models.sh
```

**Python script directly**:
```bash
python3 scripts/download_models.py
```

**Manual installation**:
```bash
# spaCy model
python3 -m spacy download en_core_web_sm

# scispaCy models
pip install https://s3-us-west-2.amazonaws.com/ai2-s2-scispacy/releases/v0.5.3/en_ner_bc5cdr_md-0.5.3.tar.gz
pip install https://s3-us-west-2.amazonaws.com/ai2-s2-scispacy/releases/v0.5.3/en_core_sci_sm-0.5.3.tar.gz
```

#### Step 3: Verify Installation

```bash
# Run test script
python3 scripts/test_models.py
```

Expected output:
```
============================================================
NeuroscribeAI - Model Functionality Tests
============================================================

Testing spaCy en_core_web_sm
✓ Model loaded successfully
Entities found: 4

Testing scispaCy en_ner_bc5cdr_md
✓ Model loaded successfully
Medical entities found: 5

Testing Extraction Module
✓ Extraction module loaded
✓ Extraction complete!
Total facts extracted: 15+

============================================================
Test Results Summary
============================================================
spacy               : ✓ PASS
scispacy            : ✓ PASS
extraction          : ✓ PASS

✓ All tests passed!
```

## Configuration

### Environment Variables

Configure model usage in `.env` file:

```bash
# Enable/disable NER extraction
EXTRACTION_USE_NER=true

# Enable/disable LLM-based extraction (BioBERT)
# Set to false to skip BioBERT download and reduce memory usage
EXTRACTION_USE_LLM=true

# Minimum confidence threshold for extracted facts
EXTRACTION_MIN_CONFIDENCE=0.7

# Extraction timeout in seconds
EXTRACTION_TIMEOUT=300
```

### Model Loading Behavior

The application loads models with graceful degradation:

1. **All models available**: Full extraction capability
2. **scispaCy only**: Medical entity extraction works
3. **spaCy only**: Basic entity extraction (limited medical entities)
4. **No models**: Application fails to start with clear error message

## Troubleshooting

### Common Issues

#### Issue 1: "Can't find model 'en_ner_bc5cdr_md'"

**Problem**: scispaCy models are not installed or were installed incorrectly.

**Solution**:
```bash
# DO NOT use spacy download for scispaCy models
# Instead, use pip with direct URL:
pip install https://s3-us-west-2.amazonaws.com/ai2-s2-scispacy/releases/v0.5.3/en_ner_bc5cdr_md-0.5.3.tar.gz
```

#### Issue 2: "No module named 'spacy'"

**Problem**: Requirements not installed.

**Solution**:
```bash
pip install -r requirements.txt
```

#### Issue 3: Models work in Docker but not locally

**Problem**: Different Python environments.

**Solution**: Use a virtual environment locally:
```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
./scripts/download_models.sh
```

#### Issue 4: BioBERT download fails or is very slow

**Problem**: Large model downloading from Hugging Face.

**Solutions**:
- **Disable BioBERT**: Set `EXTRACTION_USE_LLM=false` in `.env`
- **Wait for download**: First download can take 5-10 minutes
- **Check internet**: Ensure stable connection to Hugging Face
- **Manual cache**: Pre-download model:
  ```python
  from transformers import pipeline
  pipeline("ner", model="dmis-lab/biobert-base-cased-v1.2")
  ```

#### Issue 5: Out of memory errors

**Problem**: All models loaded require ~1.5GB RAM.

**Solutions**:
- Disable BioBERT: Set `EXTRACTION_USE_LLM=false`
- Increase Docker memory limit in Docker Desktop settings
- Use smaller scispaCy model: `en_core_sci_sm` instead of `en_ner_bc5cdr_md`

### Verification Commands

```bash
# Check if spaCy model is installed
python3 -c "import spacy; nlp = spacy.load('en_core_web_sm'); print('✓ OK')"

# Check if scispaCy model is installed
python3 -c "import spacy; nlp = spacy.load('en_ner_bc5cdr_md'); print('✓ OK')"

# List all installed spaCy models
python3 -m spacy info

# Check transformers installation
python3 -c "from transformers import pipeline; print('✓ OK')"
```

### Getting Help

If models still don't work after following this guide:

1. Check the logs: `docker-compose logs api` (for Docker)
2. Run the test script with verbose logging: `python3 scripts/test_models.py`
3. Check model versions match scispacy version in requirements.txt
4. See `scripts/README.md` for additional troubleshooting

## Model Updates

### Updating Models

Models should be updated when:
- Updating spaCy or scispaCy version
- New model versions are released
- Switching to different model sizes

**Update process**:
```bash
# Update packages
pip install --upgrade spacy scispacy transformers

# Remove old models
pip uninstall en_ner_bc5cdr_md en_core_sci_sm

# Download new versions
./scripts/download_models.sh
```

### Version Compatibility

**Current versions** (as of requirements.txt):
- spaCy: 3.7.2
- scispaCy: 0.5.3
- Transformers: 4.37.2

**Important**: scispaCy model URLs must match the scispacy version:
- scispacy 0.5.3 → Use v0.5.3 model URLs
- scispacy 0.5.4 → Use v0.5.4 model URLs (when available)

## Performance Characteristics

### Model Loading Time
- **First load**: 5-15 seconds (excluding BioBERT auto-download)
- **BioBERT first download**: 5-10 minutes (one-time)
- **Subsequent loads**: 5-10 seconds

### Memory Usage
- spaCy model: ~100 MB RAM
- scispaCy model: ~400 MB RAM
- BioBERT model: ~1000 MB RAM
- **Total**: ~1.5 GB RAM when all loaded

### Extraction Performance
- **Short text** (<500 words): 100-200ms
- **Medium text** (500-2000 words): 200-500ms
- **Long text** (>2000 words): 500-1500ms

## Advanced Configuration

### Using Different Models

To use different spaCy or scispaCy models, update `app/modules/extraction.py`:

```python
# Change in NERModels.load_models()

# For larger spaCy model:
self.spacy_model = spacy.load("en_core_web_md")  # or en_core_web_lg

# For different scispaCy model:
self.scispacy_model = spacy.load("en_core_sci_md")  # Medium scientific model
```

### Disabling Specific Models

Edit `.env` to control model usage:

```bash
# Disable NER completely (use only rule-based extraction)
EXTRACTION_USE_NER=false

# Disable BioBERT only
EXTRACTION_USE_LLM=false
```

## References

- [spaCy Documentation](https://spacy.io/)
- [spaCy Models](https://spacy.io/models)
- [scispaCy](https://allenai.github.io/scispacy/)
- [scispaCy Models](https://allenai.github.io/scispacy/#available-models)
- [BioBERT Paper](https://arxiv.org/abs/1901.08746)
- [Hugging Face Transformers](https://huggingface.co/transformers/)

## Support

For issues specific to NeuroscribeAI model integration:
- Check `scripts/README.md` for detailed script documentation
- Run `python3 scripts/test_models.py` for diagnostics
- Review logs in `docker-compose logs api`

For model-specific issues:
- spaCy: https://github.com/explosion/spaCy/issues
- scispaCy: https://github.com/allenai/scispacy/issues
- Transformers: https://github.com/huggingface/transformers/issues
