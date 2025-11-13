#!/usr/bin/env python3
"""
NeuroscribeAI - Database Table Creation Script
Creates all tables using SQLAlchemy ORM
"""

import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import create_engine
from app.models import Base
from app.config import settings

def create_all_tables():
    """Create all database tables"""
    print("="*60)
    print("NeuroscribeAI - Database Table Creation")
    print("="*60)

    # Get database URL (non-async version for Alembic/direct connection)
    db_url = settings.get_database_url(for_alembic=True)
    print(f"\nConnecting to database...")
    print(f"URL: {db_url.split('@')[1] if '@' in db_url else 'hidden'}")

    try:
        # Create engine
        engine = create_engine(db_url, echo=True)

        # Create all tables
        print("\nCreating all tables...")
        Base.metadata.create_all(engine)

        print("\n" + "="*60)
        print("✓ All tables created successfully!")
        print("="*60)

        # List all tables
        print("\nTables created:")
        for table in Base.metadata.sorted_tables:
            print(f"  - {table.name}")

        return 0

    except Exception as e:
        print(f"\n✗ Error creating tables: {e}")
        import traceback
        traceback.print_exc()
        return 1

if __name__ == "__main__":
    sys.exit(create_all_tables())
