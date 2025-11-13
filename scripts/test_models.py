#!/usr/bin/env python3
"""
NeuroscribeAI - Model Functionality Test Script
Tests all NER models with sample clinical text
"""

import sys
import logging
from pathlib import Path

# Add parent directory to path to import app modules
sys.path.insert(0, str(Path(__file__).parent.parent))

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def test_spacy_model():
    """Test basic spaCy model"""
    logger.info("\n" + "="*60)
    logger.info("Testing spaCy en_core_web_sm")
    logger.info("="*60)

    try:
        import spacy
        nlp = spacy.load("en_core_web_sm")

        text = "Apple Inc. is looking at buying a U.K. startup for $1 billion in San Francisco."
        doc = nlp(text)

        logger.info(f"✓ Model loaded successfully")
        logger.info(f"Text: {text}")
        logger.info(f"Entities found: {len(doc.ents)}")

        for ent in doc.ents:
            logger.info(f"  - {ent.text:20} | {ent.label_:10} | {ent.start_char}-{ent.end_char}")

        return True
    except Exception as e:
        logger.error(f"✗ spaCy test failed: {e}")
        return False


def test_scispacy_model():
    """Test scispaCy medical model"""
    logger.info("\n" + "="*60)
    logger.info("Testing scispaCy en_ner_bc5cdr_md")
    logger.info("="*60)

    try:
        import spacy
        nlp = spacy.load("en_ner_bc5cdr_md")

        text = (
            "Patient has diabetes mellitus type 2 and hypertension. "
            "Currently taking metformin and lisinopril. "
            "Recent diagnosis of glioblastoma multiforme."
        )
        doc = nlp(text)

        logger.info(f"✓ Model loaded successfully")
        logger.info(f"Text: {text}")
        logger.info(f"Medical entities found: {len(doc.ents)}")

        for ent in doc.ents:
            logger.info(f"  - {ent.text:30} | {ent.label_:10} | {ent.start_char}-{ent.end_char}")

        return True
    except Exception as e:
        logger.error(f"✗ scispaCy test failed: {e}")
        return False


def test_extraction_module():
    """Test the extraction module with clinical text"""
    logger.info("\n" + "="*60)
    logger.info("Testing Extraction Module")
    logger.info("="*60)

    try:
        # Import extraction module
        from app.modules.extraction import NERModels, HybridExtractionEngine

        # Load models
        ner_models = NERModels()
        ner_models.load_models()

        # Get status
        status = ner_models.get_status()
        logger.info(f"✓ Extraction module loaded")
        logger.info(f"Models loaded: {status['models']}")

        if status['errors']:
            logger.warning(f"Errors encountered: {status['errors']}")

        # Test extraction
        logger.info("\nTesting extraction on sample clinical text...")

        sample_text = """
        Patient: 45-year-old male

        PROCEDURE: Left frontal craniotomy for glioblastoma resection

        CURRENT MEDICATIONS:
        - Dexamethasone 4mg BID
        - Levetiracetam 500mg BID for seizure prophylaxis
        - Enoxaparin 40mg daily for DVT prophylaxis

        PHYSICAL EXAM (POD 3):
        - GCS 15 (E4 V5 M6)
        - Motor: 5/5 throughout bilateral upper and lower extremities
        - Right deltoid: 5/5
        - Left grip: 5/5

        LABS:
        - Sodium: 138 mEq/L
        - Hemoglobin: 12.5 g/dL
        - WBC: 8.2 K/uL

        ASSESSMENT: Neurologically stable post-operative day 3 status post
        left frontal craniotomy for glioblastoma resection.
        """

        engine = HybridExtractionEngine()
        facts = engine.extract_all_facts(sample_text, patient_id=1, document_id=1)

        logger.info(f"\n✓ Extraction complete!")
        logger.info(f"Total facts extracted: {len(facts)}")

        # Group by entity type
        by_type = {}
        for fact in facts:
            entity_type = fact.entity_type
            if entity_type not in by_type:
                by_type[entity_type] = []
            by_type[entity_type].append(fact)

        logger.info("\nExtracted facts by type:")
        for entity_type, type_facts in by_type.items():
            logger.info(f"\n  {entity_type.upper()} ({len(type_facts)} facts):")
            for fact in type_facts[:3]:  # Show first 3 of each type
                logger.info(f"    - {fact.entity_name} (confidence: {fact.confidence_score:.2f})")
                logger.info(f"      Method: {fact.extraction_method}")

        return True

    except Exception as e:
        logger.error(f"✗ Extraction module test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def run_all_tests():
    """Run all model tests"""
    logger.info("="*60)
    logger.info("NeuroscribeAI - Model Functionality Tests")
    logger.info("="*60)

    results = {
        "spacy": test_spacy_model(),
        "scispacy": test_scispacy_model(),
        "extraction": test_extraction_module()
    }

    logger.info("\n" + "="*60)
    logger.info("Test Results Summary")
    logger.info("="*60)

    for test_name, result in results.items():
        status = "✓ PASS" if result else "✗ FAIL"
        logger.info(f"{test_name:20} : {status}")

    all_passed = all(results.values())

    if all_passed:
        logger.info("\n✓ All tests passed!")
        return 0
    else:
        logger.info("\n✗ Some tests failed")
        return 1


if __name__ == "__main__":
    sys.exit(run_all_tests())
