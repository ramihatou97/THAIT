#!/usr/bin/env python3
"""
NeuroscribeAI - NER Model Download Script
Downloads all required spaCy, scispaCy, and transformer models
"""

import sys
import subprocess
import logging
from pathlib import Path

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def run_command(cmd, description):
    """Run a shell command and handle errors"""
    logger.info(f"Running: {description}")
    logger.info(f"Command: {' '.join(cmd)}")

    try:
        result = subprocess.run(
            cmd,
            check=True,
            capture_output=True,
            text=True
        )
        logger.info(f"✓ {description} completed successfully")
        if result.stdout:
            logger.debug(result.stdout)
        return True
    except subprocess.CalledProcessError as e:
        logger.error(f"✗ {description} failed")
        logger.error(f"Error: {e.stderr}")
        return False
    except Exception as e:
        logger.error(f"✗ Unexpected error during {description}: {e}")
        return False


def download_spacy_models():
    """Download required spaCy models"""
    logger.info("\n" + "="*60)
    logger.info("Downloading spaCy Models")
    logger.info("="*60)

    models = [
        ("en_core_web_sm", "spaCy General English (small)"),
    ]

    success = True
    for model_name, description in models:
        logger.info(f"\nDownloading {description}...")
        if not run_command(
            [sys.executable, "-m", "spacy", "download", model_name],
            f"Download {model_name}"
        ):
            success = False
            logger.warning(f"Failed to download {model_name}, continuing...")

    return success


def download_scispacy_models():
    """Download required scispaCy models"""
    logger.info("\n" + "="*60)
    logger.info("Downloading scispaCy Models")
    logger.info("="*60)

    # scispaCy models must be installed via pip from direct URLs
    models = [
        (
            "en_ner_bc5cdr_md",
            "https://s3-us-west-2.amazonaws.com/ai2-s2-scispacy/releases/v0.5.3/en_ner_bc5cdr_md-0.5.3.tar.gz",
            "BC5CDR disease and chemical NER"
        ),
        (
            "en_core_sci_sm",
            "https://s3-us-west-2.amazonaws.com/ai2-s2-scispacy/releases/v0.5.3/en_core_sci_sm-0.5.3.tar.gz",
            "Scientific text processing (small)"
        ),
    ]

    success = True
    for model_name, url, description in models:
        logger.info(f"\nDownloading {description} ({model_name})...")
        if not run_command(
            [sys.executable, "-m", "pip", "install", url],
            f"Install {model_name}"
        ):
            success = False
            logger.warning(f"Failed to download {model_name}, continuing...")

    return success


def verify_installations():
    """Verify all models are installed correctly"""
    logger.info("\n" + "="*60)
    logger.info("Verifying Model Installations")
    logger.info("="*60)

    try:
        import spacy
        logger.info("\n✓ spaCy is installed")

        # Test spaCy model
        try:
            nlp = spacy.load("en_core_web_sm")
            logger.info("✓ en_core_web_sm loaded successfully")

            # Quick test
            doc = nlp("Apple is looking at buying U.K. startup for $1 billion")
            logger.info(f"  Test: Found {len(doc.ents)} entities")
        except Exception as e:
            logger.error(f"✗ Failed to load en_core_web_sm: {e}")
            return False

        # Test scispaCy model
        try:
            nlp = spacy.load("en_ner_bc5cdr_md")
            logger.info("✓ en_ner_bc5cdr_md loaded successfully")

            # Quick test
            doc = nlp("The patient has diabetes and hypertension")
            logger.info(f"  Test: Found {len(doc.ents)} medical entities")
        except Exception as e:
            logger.error(f"✗ Failed to load en_ner_bc5cdr_md: {e}")
            return False

        # Test transformers
        try:
            from transformers import pipeline
            logger.info("✓ transformers library is installed")

            logger.info("  Note: BioBERT model will be downloaded automatically on first use")
            logger.info("  Model: dmis-lab/biobert-base-cased-v1.2")
        except Exception as e:
            logger.error(f"✗ Failed to import transformers: {e}")
            return False

        logger.info("\n" + "="*60)
        logger.info("All Models Verified Successfully!")
        logger.info("="*60)
        return True

    except ImportError as e:
        logger.error(f"✗ Missing required package: {e}")
        return False
    except Exception as e:
        logger.error(f"✗ Verification failed: {e}")
        return False


def main():
    """Main execution function"""
    logger.info("NeuroscribeAI - NER Model Download Script")
    logger.info("="*60)

    # Check Python version
    if sys.version_info < (3, 8):
        logger.error("Python 3.8+ is required")
        sys.exit(1)

    logger.info(f"Python version: {sys.version}")

    # Download models
    spacy_success = download_spacy_models()
    scispacy_success = download_scispacy_models()

    # Verify installations
    if spacy_success and scispacy_success:
        logger.info("\n" + "="*60)
        logger.info("Download Phase Complete")
        logger.info("="*60)

        if verify_installations():
            logger.info("\n✓ All models downloaded and verified successfully!")
            return 0
        else:
            logger.error("\n✗ Model verification failed")
            return 1
    else:
        logger.error("\n✗ Some downloads failed")
        logger.info("Attempting verification of what was downloaded...")
        verify_installations()
        return 1


if __name__ == "__main__":
    sys.exit(main())
