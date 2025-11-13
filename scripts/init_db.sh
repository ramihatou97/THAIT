#!/bin/bash
# NeuroscribeAI - Database Initialization Script
# Initializes PostgreSQL database and runs migrations

set -e  # Exit on error

echo "============================================================"
echo "NeuroscribeAI - Database Initialization"
echo "============================================================"

# Colors for output
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Wait for PostgreSQL to be ready
echo ""
echo "Waiting for PostgreSQL to be ready..."
max_attempts=30
attempt=0

while [ $attempt -lt $max_attempts ]; do
    if docker-compose exec -T postgres pg_isready -U neuroscribe > /dev/null 2>&1; then
        echo -e "${GREEN}✓ PostgreSQL is ready${NC}"
        break
    fi
    attempt=$((attempt+1))
    echo "  Attempt $attempt/$max_attempts..."
    sleep 2
done

if [ $attempt -eq $max_attempts ]; then
    echo -e "${RED}✗ PostgreSQL failed to start${NC}"
    exit 1
fi

# Run init SQL script
echo ""
echo "Running database initialization script..."
if docker-compose exec -T postgres psql -U neuroscribe -d neuroscribe < db/init/01_init_extensions.sql; then
    echo -e "${GREEN}✓ Database extensions and types created${NC}"
else
    echo -e "${YELLOW}⚠ Database initialization may have already been done${NC}"
fi

# Generate initial migration if not exists
echo ""
echo "Checking for existing migrations..."
if [ -z "$(ls -A alembic/versions/*.py 2>/dev/null)" ]; then
    echo "No migrations found. Creating initial migration..."

    if docker-compose exec -T api alembic revision --autogenerate -m "Initial schema"; then
        echo -e "${GREEN}✓ Initial migration created${NC}"
    else
        echo -e "${RED}✗ Failed to create migration${NC}"
        exit 1
    fi
else
    echo -e "${GREEN}✓ Migrations already exist${NC}"
fi

# Run migrations
echo ""
echo "Running database migrations..."
if docker-compose exec -T api alembic upgrade head; then
    echo -e "${GREEN}✓ Migrations applied successfully${NC}"
else
    echo -e "${RED}✗ Failed to apply migrations${NC}"
    exit 1
fi

# Verify tables were created
echo ""
echo "Verifying database tables..."
table_count=$(docker-compose exec -T postgres psql -U neuroscribe -d neuroscribe -t -c "SELECT COUNT(*) FROM information_schema.tables WHERE table_schema = 'public' AND table_type = 'BASE TABLE';" | tr -d ' ')

if [ "$table_count" -gt 0 ]; then
    echo -e "${GREEN}✓ Database initialized with $table_count tables${NC}"

    echo ""
    echo "Tables created:"
    docker-compose exec -T postgres psql -U neuroscribe -d neuroscribe -c "\dt"
else
    echo -e "${RED}✗ No tables found in database${NC}"
    exit 1
fi

echo ""
echo -e "${GREEN}============================================================${NC}"
echo -e "${GREEN}✓ Database initialization complete!${NC}"
echo -e "${GREEN}============================================================${NC}"
