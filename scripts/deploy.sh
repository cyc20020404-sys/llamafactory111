#!/bin/bash

# LLaMA Factory RAG System - Deployment Script
# Usage: ./scripts/deploy.sh

set -e

echo "========================================="
echo "LLaMA Factory RAG System Deployment"
echo "========================================="

# Color codes for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Check if Docker is installed
if ! command -v docker &> /dev/null; then
    echo -e "${RED}Error: Docker is not installed${NC}"
    exit 1
fi

if ! command -v docker-compose &> /dev/null && ! docker compose version &> /dev/null; then
    echo -e "${RED}Error: Docker Compose is not installed${NC}"
    exit 1
fi

# Determine docker-compose command
DOCKER_COMPOSE_CMD="docker-compose"
if docker compose version &> /dev/null; then
    DOCKER_COMPOSE_CMD="docker compose"
fi

echo -e "${GREEN}Docker and Docker Compose detected${NC}"

# Function to start services
start_services() {
    echo -e "\n${GREEN}Starting RAG services...${NC}"
    $DOCKER_COMPOSE_CMD up -d
    
    echo -e "\n${GREEN}Waiting for Qdrant to be ready...${NC}"
    sleep 5
    
    # Check Qdrant health
    for i in {1..30}; do
        if curl -s http://localhost:6333/readyz > /dev/null 2>&1; then
            echo -e "${GREEN}Qdrant is ready!${NC}"
            break
        fi
        echo "Waiting for Qdrant... ($i/30)"
        sleep 2
    done
    
    echo -e "\n${GREEN}Services started successfully!${NC}"
    echo ""
    echo "Service URLs:"
    echo "  - Qdrant Dashboard: http://localhost:6333/dashboard"
    echo "  - RAG API (FastAPI): http://localhost:8001"
    echo "  - API Docs: http://localhost:8001/docs"
    echo "  - Frontend: http://localhost:5173"
}

# Function to stop services
stop_services() {
    echo -e "\n${YELLOW}Stopping RAG services...${NC}"
    $DOCKER_COMPOSE_CMD down
    echo -e "${GREEN}Services stopped${NC}"
}

# Function to rebuild and start
rebuild() {
    echo -e "\n${YELLOW}Rebuilding and starting services...${NC}"
    $DOCKER_COMPOSE_CMD down
    $DOCKER_COMPOSE_CMD build --no-cache
    $DOCKER_COMPOSE_CMD up -d
    echo -e "${GREEN}Rebuild complete${NC}"
}

# Function to show logs
show_logs() {
    echo -e "\n${GREEN}Showing logs...${NC}"
    $DOCKER_COMPOSE_CMD logs -f
}

# Function to show status
show_status() {
    echo -e "\n${GREEN}Service Status:${NC}"
    $DOCKER_COMPOSE_CMD ps
    echo ""
    
    echo -e "${GREEN}RAG System Health:${NC}"
    if curl -s http://localhost:6333/readyz > /dev/null 2>&1; then
        echo -e "  Qdrant: ${GREEN}Healthy${NC}"
    else
        echo -e "  Qdrant: ${RED}Unhealthy${NC}"
    fi
    
    if curl -s http://localhost:8001/health > /dev/null 2>&1; then
        echo -e "  RAG API: ${GREEN}Healthy${NC}"
    else
        echo -e "  RAG API: ${RED}Unhealthy${NC}"
    fi
}

# Parse command line arguments
case "${1:-start}" in
    start)
        start_services
        ;;
    stop)
        stop_services
        ;;
    restart)
        stop_services
        start_services
        ;;
    rebuild)
        rebuild
        ;;
    logs)
        show_logs
        ;;
    status)
        show_status
        ;;
    *)
        echo "Usage: $0 {start|stop|restart|rebuild|logs|status}"
        exit 1
        ;;
esac
