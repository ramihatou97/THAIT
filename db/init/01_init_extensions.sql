-- NeuroscribeAI Database Initialization
-- Enable required PostgreSQL extensions

-- Enable UUID generation
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Enable pgvector for vector similarity search
CREATE EXTENSION IF NOT EXISTS vector;

-- Enable pg_trgm for fuzzy text matching
CREATE EXTENSION IF NOT EXISTS pg_trgm;

-- Enable btree_gin for multi-column indexes
CREATE EXTENSION IF NOT EXISTS btree_gin;

-- Create database user if not exists (for reference)
DO $$
BEGIN
    IF NOT EXISTS (SELECT FROM pg_user WHERE usename = 'neuroscribe') THEN
        CREATE USER neuroscribe WITH PASSWORD 'neuroscribe_pass';
    END IF;
END
$$;

-- Grant privileges
GRANT ALL PRIVILEGES ON DATABASE neuroscribe TO neuroscribe;
GRANT ALL ON SCHEMA public TO neuroscribe;

-- Create custom types
DO $$
BEGIN
    -- Entity type enum
    IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'entity_type') THEN
        CREATE TYPE entity_type AS ENUM (
            'DIAGNOSIS', 'PROCEDURE', 'MEDICATION', 'LAB_VALUE',
            'IMAGING', 'VITAL_SIGN', 'PHYSICAL_EXAM', 'SYMPTOM',
            'ALLERGY', 'FAMILY_HISTORY'
        );
    END IF;

    -- Alert severity enum
    IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'alert_severity') THEN
        CREATE TYPE alert_severity AS ENUM (
            'CRITICAL', 'HIGH', 'MEDIUM', 'LOW'
        );
    END IF;
END
$$;

-- Add comments
COMMENT ON EXTENSION vector IS 'Vector similarity search for embeddings';
COMMENT ON EXTENSION pg_trgm IS 'Fuzzy text matching for entity disambiguation';
