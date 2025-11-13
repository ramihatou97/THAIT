# NeuroscribeAI - Alembic Migration Setup Guide

Database migration management using Alembic for schema versioning and upgrades.

## Current Status

✓ **Database Tables**: Created via SQLAlchemy `Base.metadata.create_all()`
✓ **Alembic Files**: Configured locally (not yet in Docker containers)

**Next Steps**: Rebuild containers to include Alembic support for proper migration management.

## Alembic Files Created

The following Alembic configuration files have been created locally:

1. **alembic.ini** - Main configuration file
2. **alembic/env.py** - Migration environment
3. **alembic/script.py.mako** - Migration template
4. **alembic/versions/** - Migration scripts directory

## Adding Alembic to Docker

### Step 1: Verify Local Files

```bash
ls -la alembic.ini
ls -la alembic/env.py
ls -la alembic/script.py.mako
ls -la alembic/versions/
```

All files should exist (they were created during setup).

### Step 2: Rebuild Docker Containers

The Dockerfile already includes these files via the `COPY . /app` command.

```bash
# Rebuild containers to include Alembic files
docker-compose build api celery-worker

# Restart services
docker-compose up -d
```

### Step 3: Verify Alembic in Container

```bash
# Check if alembic.ini exists in container
docker-compose exec api ls -la /app/alembic.ini

# Check if alembic directory exists
docker-compose exec api ls -la /app/alembic/

# Test alembic command
docker-compose exec api alembic --version
```

## Using Alembic for Migrations

### Creating Initial Migration

Since tables already exist, create a baseline migration:

```bash
# Create initial migration (marks current state)
docker-compose exec api alembic revision --autogenerate -m "Initial schema baseline"

# This will create: alembic/versions/YYYYMMDD_HHMM_xxx_initial_schema_baseline.py
```

### Applying Migrations

```bash
# Apply all pending migrations
docker-compose exec api alembic upgrade head

# View current migration version
docker-compose exec api alembic current

# View migration history
docker-compose exec api alembic history --verbose
```

### Creating New Migrations

When you modify models in `app/models.py`:

```bash
# 1. Update your model (e.g., add a new field to Patient model)

# 2. Generate migration automatically
docker-compose exec api alembic revision --autogenerate -m "Add patient email field"

# 3. Review the generated migration
cat alembic/versions/YYYYMMDD_HHMM_*_add_patient_email_field.py

# 4. Apply the migration
docker-compose exec api alembic upgrade head
```

### Rollback Migrations

```bash
# Downgrade one version
docker-compose exec api alembic downgrade -1

# Downgrade to specific version
docker-compose exec api alembic downgrade <revision_id>

# Downgrade to base (remove all migrations)
docker-compose exec api alembic downgrade base
```

## Migration Best Practices

### 1. Always Review Auto-generated Migrations

```bash
# After generating migration, review it:
cat alembic/versions/latest_migration.py

# Check for:
# - Correct operations
# - No data loss
# - Proper indexes
# - Constraint handling
```

### 2. Test Migrations Before Production

```bash
# In development environment:
docker-compose exec api alembic upgrade head

# Test the application

# If issues found, downgrade and fix:
docker-compose exec api alembic downgrade -1
# Fix migration file
docker-compose exec api alembic upgrade head
```

### 3. Backup Before Migrations

```bash
# Always backup before running migrations in production
docker-compose exec postgres pg_dump -U neuroscribe neuroscribe > backup_pre_migration_$(date +%Y%m%d).sql
```

### 4. Use Descriptive Migration Messages

```bash
# Good examples:
alembic revision -m "Add patient risk score field"
alembic revision -m "Create index on documents timestamp"
alembic revision -m "Add validation_results table"

# Bad examples:
alembic revision -m "Update database"
alembic revision -m "Fix"
```

## Alembic Configuration Details

### alembic.ini

Key settings:
```ini
script_location = alembic
file_template = %%(year)d%%(month).2d%%(day).2d_%%(hour).2d%%(minute).2d_%%(rev)s_%%(slug)s
sqlalchemy.url = postgresql://neuroscribe:neuroscribe_pass@localhost:5432/neuroscribe
```

### env.py

Configured to:
- Import models from `app.models`
- Use settings from `app.config`
- Support both online and offline migrations
- Enable type and default comparisons

## Migration Workflow

### Typical Development Workflow

1. **Modify Model**
   ```python
   # app/models.py
   class Patient(Base, TimestampMixin):
       # Add new field
       risk_score: Mapped[Optional[float]] = mapped_column(Float)
   ```

2. **Generate Migration**
   ```bash
   docker-compose exec api alembic revision --autogenerate -m "Add patient risk score"
   ```

3. **Review Migration**
   ```bash
   # Check generated file in alembic/versions/
   cat alembic/versions/20251113_*_add_patient_risk_score.py
   ```

4. **Apply Migration**
   ```bash
   docker-compose exec api alembic upgrade head
   ```

5. **Verify**
   ```bash
   docker-compose exec postgres psql -U neuroscribe -d neuroscribe -c "\d patients"
   ```

### Production Deployment Workflow

1. **Test migrations in staging**
2. **Backup production database**
3. **Run migrations during maintenance window**
4. **Verify application functionality**
5. **Monitor for errors**

## Troubleshooting

### Issue: "Can't locate revision identified by 'xyz'"

**Problem**: Migration history mismatch.

**Solution**:
```bash
# Check current version
docker-compose exec api alembic current

# View all migrations
docker-compose exec api alembic history

# Stamp database with specific version
docker-compose exec api alembic stamp head
```

### Issue: "Target database is not up to date"

**Problem**: Alembic version table missing or out of sync.

**Solution**:
```bash
# Create/update alembic_version table
docker-compose exec api alembic stamp head

# Then upgrade
docker-compose exec api alembic upgrade head
```

### Issue: Auto-generate doesn't detect changes

**Problem**: Models not imported in env.py.

**Solution**:
- Ensure `from app.models import Base` in alembic/env.py
- Verify `target_metadata = Base.metadata`
- Check all models are defined before import

### Issue: Migration fails halfway

**Problem**: Database in inconsistent state.

**Solution**:
```bash
# 1. Restore from backup
docker-compose exec -T postgres psql -U neuroscribe neuroscribe < backup.sql

# 2. Or manually fix the database state
docker-compose exec postgres psql -U neuroscribe -d neuroscribe
# Fix the issue manually

# 3. Update alembic version table
docker-compose exec api alembic stamp <last_successful_version>
```

## Alternative: SQLAlchemy create_all()

### Current Approach (Faster for Development)

```bash
# One-command table creation
docker-compose exec api python -c "
from app.models import Base
from sqlalchemy import create_engine
from app.config import settings
engine = create_engine(settings.get_database_url(for_alembic=True))
Base.metadata.create_all(engine)
print('✓ Tables created!')
"
```

**Pros**:
- Simple and fast
- No migration files to manage
- Good for development

**Cons**:
- No version history
- Can't rollback changes
- Difficult to manage schema changes in production

### When to Use Alembic

Use Alembic when:
- Moving to production
- Need schema versioning
- Multiple developers working on schema
- Need to rollback changes
- Deploying across multiple environments

Use create_all() when:
- Local development
- Testing
- Prototyping
- Single developer

## Future Enhancements

1. **Auto-migration on startup**: Add migration check to app startup
2. **Migration validation**: Pre-migration checks
3. **Data migrations**: Complex data transformations
4. **Multi-database support**: Separate read/write replicas

## References

- [Alembic Documentation](https://alembic.sqlalchemy.org/)
- [SQLAlchemy Migrations](https://docs.sqlalchemy.org/en/20/tutorial/metadata.html#altering-database-objects-through-migrations)
- [FastAPI with Alembic](https://fastapi.tiangolo.com/tutorial/sql-databases/#create-a-database-migration)

## Summary

**Current State**: Tables created via SQLAlchemy (fully functional)
**Alembic Status**: Configured locally, not yet in Docker containers
**Next Step**: Rebuild containers when ready for production-grade migration management

The system is operational with or without Alembic. Alembic is recommended for production deployments with schema versioning needs.
