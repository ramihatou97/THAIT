# NeuroscribeAI - Database Setup Guide

Complete guide for initializing and managing the NeuroscribeAI database.

## Database Architecture

### PostgreSQL with Extensions

NeuroscribeAI uses PostgreSQL with specialized extensions:

1. **pgvector** (v0.5.1) - Vector similarity search for embeddings
2. **pg_trgm** (v1.6) - Fuzzy text matching for entity disambiguation
3. **uuid-ossp** (v1.1) - UUID generation
4. **btree_gin** (v1.3) - Multi-column indexes

### Database Schema

**10 core tables**:

| Table | Purpose |
|-------|---------|
| patients | Patient demographics and core info |
| documents | Clinical documents and metadata |
| atomic_clinical_facts | Extracted clinical entities |
| inferred_facts | AI-inferred medical facts |
| clinical_alerts | Safety alerts and warnings |
| document_chunks | Text chunks for vector search |
| temporal_events | Timeline of clinical events |
| generated_summaries | AI-generated summaries |
| validation_results | Data quality validation |
| audit_logs | System audit trail |

## Quick Start

### Automatic Setup (Docker)

```bash
# Start all services (database auto-initializes)
docker-compose up -d

# Create tables
docker-compose exec api python -c "
from app.models import Base
from sqlalchemy import create_engine
from app.config import settings
engine = create_engine(settings.get_database_url(for_alembic=True))
Base.metadata.create_all(engine)
print('✓ Tables created!')
"

# Verify tables
docker-compose exec postgres psql -U neuroscribe -d neuroscribe -c "\dt"
```

### Manual Setup (Local Development)

```bash
# Ensure PostgreSQL is running
docker-compose up -d postgres

# Wait for PostgreSQL to be ready
docker-compose exec postgres pg_isready -U neuroscribe

# Initialize extensions
docker-compose exec postgres psql -U neuroscribe -d neuroscribe < db/init/01_init_extensions.sql

# Create tables (from your local Python environment)
python3 -c "
from app.models import Base
from sqlalchemy import create_engine
from app.config import settings
engine = create_engine(settings.get_database_url(for_alembic=True))
Base.metadata.create_all(engine)
"
```

## Database Initialization Status

### ✓ Completed Setup

The following have been successfully configured and initialized:

1. **PostgreSQL Extensions** ✓
   - uuid-ossp v1.1
   - vector v0.5.1
   - pg_trgm v1.6
   - btree_gin v1.3

2. **Custom Types** ✓
   - entity_type enum
   - alert_severity enum

3. **Database Tables** ✓
   All 10 tables created with proper:
   - Primary keys
   - Foreign keys
   - Indexes
   - Constraints
   - Vector columns

4. **Database User** ✓
   - User: neuroscribe
   - Privileges: ALL on database neuroscribe

## Database Connection

### Connection Details

```bash
Host: localhost
Port: 5432
Database: neuroscribe
User: neuroscribe
Password: neuroscribe_pass (from .env)
```

### Connection Strings

**Async (FastAPI/SQLAlchemy)**:
```
postgresql+asyncpg://neuroscribe:neuroscribe_pass@localhost:5432/neuroscribe
```

**Sync (Alembic/migrations)**:
```
postgresql://neuroscribe:neuroscribe_pass@localhost:5432/neuroscribe
```

**Docker Internal**:
```
postgresql://neuroscribe:neuroscribe_pass@postgres:5432/neuroscribe
```

## Verification Commands

### Check Database Connection
```bash
docker-compose exec postgres psql -U neuroscribe -d neuroscribe -c "SELECT version();"
```

### List All Tables
```bash
docker-compose exec postgres psql -U neuroscribe -d neuroscribe -c "\dt"
```

### Check Extensions
```bash
docker-compose exec postgres psql -U neuroscribe -d neuroscribe -c "\dx"
```

### View Table Structure
```bash
# Example: View patients table
docker-compose exec postgres psql -U neuroscribe -d neuroscribe -c "\d patients"

# Example: View atomic_clinical_facts table
docker-compose exec postgres psql -U neuroscribe -d neuroscribe -c "\d atomic_clinical_facts"
```

### Check Table Row Counts
```bash
docker-compose exec postgres psql -U neuroscribe -d neuroscribe -c "
SELECT
    schemaname,
    tablename,
    (SELECT COUNT(*) FROM pg_class WHERE relname = tablename) as row_count
FROM pg_tables
WHERE schemaname = 'public'
ORDER BY tablename;
"
```

## Database Management

### Backup Database

```bash
# Backup to file
docker-compose exec postgres pg_dump -U neuroscribe neuroscribe > backup_$(date +%Y%m%d).sql

# Backup with compression
docker-compose exec postgres pg_dump -U neuroscribe neuroscribe | gzip > backup_$(date +%Y%m%d).sql.gz
```

### Restore Database

```bash
# Restore from backup
docker-compose exec -T postgres psql -U neuroscribe neuroscribe < backup_20251113.sql

# Restore from compressed backup
gunzip < backup_20251113.sql.gz | docker-compose exec -T postgres psql -U neuroscribe neuroscribe
```

### Reset Database

```bash
# WARNING: This deletes all data!

# Drop all tables
docker-compose exec postgres psql -U neuroscribe -d neuroscribe -c "
DROP SCHEMA public CASCADE;
CREATE SCHEMA public;
GRANT ALL ON SCHEMA public TO neuroscribe;
"

# Recreate extensions and tables
docker-compose exec postgres psql -U neuroscribe -d neuroscribe < db/init/01_init_extensions.sql

docker-compose exec api python -c "
from app.models import Base
from sqlalchemy import create_engine
from app.config import settings
engine = create_engine(settings.get_database_url(for_alembic=True))
Base.metadata.create_all(engine)
print('✓ Tables recreated!')
"
```

## Troubleshooting

### Issue: "relation does not exist"

**Problem**: Tables not created.

**Solution**:
```bash
docker-compose exec api python -c "
from app.models import Base
from sqlalchemy import create_engine
from app.config import settings
engine = create_engine(settings.get_database_url(for_alembic=True))
Base.metadata.create_all(engine)
"
```

### Issue: "extension 'vector' does not exist"

**Problem**: pgvector extension not installed.

**Solution**:
```bash
docker-compose exec postgres psql -U neuroscribe -d neuroscribe -c "CREATE EXTENSION IF NOT EXISTS vector;"
```

### Issue: "permission denied for schema public"

**Problem**: User permissions not granted.

**Solution**:
```bash
docker-compose exec postgres psql -U postgres -d neuroscribe -c "
GRANT ALL PRIVILEGES ON DATABASE neuroscribe TO neuroscribe;
GRANT ALL ON SCHEMA public TO neuroscribe;
"
```

### Issue: Database not accessible from API

**Problem**: Connection string incorrect or database not ready.

**Solution**:
```bash
# Check database is ready
docker-compose exec postgres pg_isready -U neuroscribe

# Check connection from API container
docker-compose exec api python -c "
from sqlalchemy import create_engine
from app.config import settings
engine = create_engine(settings.get_database_url(for_alembic=True))
with engine.connect() as conn:
    result = conn.execute('SELECT 1')
    print('✓ Database connection successful!')
"
```

## Future: Alembic Migrations

Currently, tables are created using `Base.metadata.create_all()`. For production, Alembic migrations should be set up:

### Setting Up Alembic (Future Enhancement)

1. Alembic configuration files have been created:
   - `alembic.ini`
   - `alembic/env.py`
   - `alembic/script.py.mako`

2. To use Alembic in the future:
```bash
# Generate initial migration
docker-compose exec api alembic revision --autogenerate -m "Initial schema"

# Apply migrations
docker-compose exec api alembic upgrade head

# View migration history
docker-compose exec api alembic history
```

## Database Schema Details

### Key Features

1. **Vector Search Ready**
   - document_chunks has vector column for embeddings
   - Supports similarity search with pgvector

2. **Full Audit Trail**
   - audit_logs table tracks all changes
   - Timestamp tracking on all tables

3. **Temporal Reasoning**
   - temporal_events table for timeline construction
   - POD (post-operative day) tracking

4. **Data Validation**
   - validation_results table stores quality scores
   - Supports completeness, accuracy tracking

5. **Clinical Safety**
   - clinical_alerts table for rule-based warnings
   - Severity levels: CRITICAL, HIGH, MEDIUM, LOW

## Neo4j Graph Database

In addition to PostgreSQL, the system uses Neo4j for knowledge graphs:

```bash
# Access Neo4j browser
http://localhost:7474

# Credentials
Username: neo4j
Password: neo4j_password
```

## Summary

✓ **Database Status**: Fully initialized and operational
✓ **Extensions**: 4/4 installed (vector, pg_trgm, uuid-ossp, btree_gin)
✓ **Tables**: 10/10 created successfully
✓ **API Connection**: Healthy and responding
✓ **Health Endpoint**: http://localhost:8000/health

The database is ready for clinical data extraction and processing!
