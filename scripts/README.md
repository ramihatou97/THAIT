# NeuroscribeAI - Scripts Directory

## Model Download Scripts

### Quick Start

```bash
# Run the download script
./scripts/download_models.sh
```

### What Gets Downloaded

1. **spaCy Models**
   - `en_core_web_sm` - General English language model (13 MB)
   - Used for: Basic NER, tokenization, POS tagging

2. **scispaCy Models**
   - `en_ner_bc5cdr_md` - Biomedical NER model (100 MB)
   - Trained on: Chemical and disease entities from BioCreative V CDR task
   - Used for: Medical entity extraction (diseases, chemicals, medications)

   - `en_core_sci_sm` - Scientific text processing (15 MB)
   - Used for: Scientific/medical text tokenization and processing

3. **Transformer Models** (Auto-download)
   - `dmis-lab/biobert-base-cased-v1.2` - BioBERT NER (420 MB)
   - Downloads automatically on first use via Hugging Face
   - Used for: Advanced biomedical entity recognition when LLM extraction is enabled

### Installation Methods

#### Method 1: Using Shell Script (Recommended)
```bash
./scripts/download_models.sh
```

#### Method 2: Using Python Script Directly
```bash
python3 scripts/download_models.py
```

#### Method 3: Manual Installation
```bash
# Install spaCy model
python3 -m spacy download en_core_web_sm

# Install scispaCy models (must use pip with direct URLs)
pip install https://s3-us-west-2.amazonaws.com/ai2-s2-scispacy/releases/v0.5.3/en_ner_bc5cdr_md-0.5.3.tar.gz
pip install https://s3-us-west-2.amazonaws.com/ai2-s2-scispacy/releases/v0.5.3/en_core_sci_sm-0.5.3.tar.gz
```

### Docker Installation

Models are automatically downloaded during Docker build:

```bash
docker-compose build
```

The Dockerfile handles all model downloads automatically.

### Verification

After installation, verify models are working:

```bash
python3 -c "import spacy; nlp = spacy.load('en_core_web_sm'); print('✓ spaCy model loaded')"
python3 -c "import spacy; nlp = spacy.load('en_ner_bc5cdr_md'); print('✓ scispaCy model loaded')"
```

### Troubleshooting

#### Problem: "Can't find model 'en_ner_bc5cdr_md'"
**Solution**: scispaCy models must be installed via pip, not spacy download:
```bash
pip install https://s3-us-west-2.amazonaws.com/ai2-s2-scispacy/releases/v0.5.3/en_ner_bc5cdr_md-0.5.3.tar.gz
```

#### Problem: "No module named 'spacy'"
**Solution**: Install requirements first:
```bash
pip install -r requirements.txt
```

#### Problem: Models work in Docker but not locally
**Solution**: Create and use a virtual environment:
```bash
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt
./scripts/download_models.sh
```

### Model Versions

Current versions (as of requirements.txt):
- spaCy: 3.7.2
- scispaCy: 0.5.3
- transformers: 4.37.2

**Important**: scispaCy models must match the scispacy version. If you update scispacy, update the model URLs accordingly.

### Storage Requirements

Total disk space needed:
- spaCy models: ~13 MB
- scispaCy models: ~115 MB
- BioBERT (on first use): ~420 MB
- **Total**: ~550 MB

### Performance Notes

1. **First Run**: BioBERT downloads on first extraction request (if LLM extraction enabled)
2. **Model Loading**: Takes 5-10 seconds on application startup
3. **Memory Usage**: ~1.5 GB RAM when all models loaded
4. **Extraction Speed**: 100-500ms per document depending on length

### Configuration

Control model usage via environment variables in `.env`:

```bash
# Enable/disable NER extraction
EXTRACTION_USE_NER=true

# Enable/disable LLM-based extraction (BioBERT)
EXTRACTION_USE_LLM=true

# Minimum confidence threshold
EXTRACTION_MIN_CONFIDENCE=0.7
```

### References

- [spaCy Models](https://spacy.io/models)
- [scispaCy](https://allenai.github.io/scispacy/)
- [BioBERT](https://github.com/dmis-lab/biobert)
