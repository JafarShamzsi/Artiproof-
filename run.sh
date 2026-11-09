#!/bin/bash
# ArtiProof - Development Run Script
# Usage: bash run.sh [start|stop|restart|seed|status]

set -e

PROJECT_DIR="$(cd "$(dirname "$0")" && pwd)"
BACKEND_DIR="$PROJECT_DIR/backend"
FRONTEND_DIR="$PROJECT_DIR/frontend"

# Container names — must match docker-compose.yml
PG_CONTAINER="artiproof-postgres"
REDIS_CONTAINER="artiproof-redis"
PG_USER="artiproof"
PG_DB="artiproof"
DEMO_EMAIL="${DEMO_EMAIL:-demo@artiproof.com}"
DEMO_PASSWORD="${DEMO_PASSWORD:-demo1234}"

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'

log() { echo -e "${CYAN}[ArtiProof]${NC} $1"; }
success() { echo -e "${GREEN}[OK]${NC} $1"; }
warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }
error() { echo -e "${RED}[ERROR]${NC} $1"; }

start_docker() {
    log "Starting Docker services (PostgreSQL + Redis)..."
    cd "$PROJECT_DIR"
    docker-compose up -d postgres redis 2>&1 | tail -5

    log "Waiting for services to be healthy..."
    for i in {1..30}; do
        if docker exec "$PG_CONTAINER" pg_isready -U "$PG_USER" -d "$PG_DB" > /dev/null 2>&1; then
            success "PostgreSQL is ready"
            break
        fi
        sleep 1
    done

    if docker exec "$REDIS_CONTAINER" redis-cli -a "${REDIS_PASSWORD:-artiproof-redis-dev}" ping > /dev/null 2>&1; then
        success "Redis is ready"
    fi
}

start_backend() {
    log "Starting backend (FastAPI on :8000)..."
    cd "$BACKEND_DIR"
    source venv/Scripts/activate 2>/dev/null || source venv/bin/activate 2>/dev/null
    uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload &
    BACKEND_PID=$!
    echo $BACKEND_PID > "$PROJECT_DIR/.backend.pid"
    sleep 2

    if curl -s http://localhost:8000/health > /dev/null 2>&1; then
        success "Backend running at http://localhost:8000"
    else
        warn "Backend may still be starting..."
    fi
}

start_frontend() {
    log "Starting frontend (Next.js on :3000)..."
    cd "$FRONTEND_DIR"
    npm run dev &
    FRONTEND_PID=$!
    echo $FRONTEND_PID > "$PROJECT_DIR/.frontend.pid"
    sleep 3
    success "Frontend running at http://localhost:3000"
}

seed_data() {
    log "Seeding database..."
    curl -s -X POST http://localhost:8000/api/seed/demo | python -m json.tool 2>/dev/null || echo "Seed request sent"
    success "Database seeded"
}

stop_all() {
    log "Stopping services..."

    if [ -f "$PROJECT_DIR/.backend.pid" ]; then
        kill $(cat "$PROJECT_DIR/.backend.pid") 2>/dev/null || true
        rm "$PROJECT_DIR/.backend.pid"
        success "Backend stopped"
    fi

    if [ -f "$PROJECT_DIR/.frontend.pid" ]; then
        kill $(cat "$PROJECT_DIR/.frontend.pid") 2>/dev/null || true
        rm "$PROJECT_DIR/.frontend.pid"
        success "Frontend stopped"
    fi

    cd "$PROJECT_DIR"
    docker-compose stop postgres redis 2>/dev/null
    success "Docker services stopped"
}

show_status() {
    echo ""
    echo -e "${CYAN}=== ArtiProof Status ===${NC}"
    echo ""

    if curl -s http://localhost:8000/health > /dev/null 2>&1; then
        success "Backend:    http://localhost:8000"
    else
        error "Backend:    NOT RUNNING"
    fi

    if curl -s http://localhost:3000 > /dev/null 2>&1; then
        success "Frontend:   http://localhost:3000"
    else
        error "Frontend:   NOT RUNNING"
    fi

    if docker exec "$PG_CONTAINER" pg_isready -U "$PG_USER" > /dev/null 2>&1; then
        success "PostgreSQL: localhost:5432"
    else
        error "PostgreSQL: NOT RUNNING"
    fi

    if docker exec "$REDIS_CONTAINER" redis-cli -a "${REDIS_PASSWORD:-artiproof-redis-dev}" ping > /dev/null 2>&1; then
        success "Redis:      localhost:6379"
    else
        error "Redis:      NOT RUNNING"
    fi

    echo ""
    echo -e "${YELLOW}Demo Login:${NC}"
    echo "  Email:    $DEMO_EMAIL"
    echo "  Password: $DEMO_PASSWORD"
    echo ""
}

case "${1:-start}" in
    start)
        echo ""
        echo -e "${CYAN}========================================${NC}"
        echo -e "${CYAN}    ArtiProof - Development Server     ${NC}"
        echo -e "${CYAN}========================================${NC}"
        echo ""
        start_docker
        start_backend
        start_frontend
        echo ""
        echo -e "${GREEN}========================================${NC}"
        echo -e "${GREEN}   All services are running!           ${NC}"
        echo -e "${GREEN}========================================${NC}"
        echo ""
        echo -e "  Frontend:  ${CYAN}http://localhost:3000${NC}"
        echo -e "  Backend:   ${CYAN}http://localhost:8000${NC}"
        echo -e "  API Docs:  ${CYAN}http://localhost:8000/docs${NC}"
        echo ""
        echo -e "  ${YELLOW}Demo Login:${NC}"
        echo -e "    Email:    $DEMO_EMAIL"
        echo -e "    Password: $DEMO_PASSWORD"
        echo ""
        echo -e "  Press Ctrl+C to stop all services"
        wait
        ;;
    stop)
        stop_all
        ;;
    restart)
        stop_all
        sleep 2
        bash "$0" start
        ;;
    seed)
        seed_data
        ;;
    status)
        show_status
        ;;
    *)
        echo "Usage: bash run.sh [start|stop|restart|seed|status]"
        exit 1
        ;;
esac
