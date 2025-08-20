#!/bin/bash
set -e

echo "🤖 ETL Agent Deployment"
echo "======================="

# Check Docker
if ! command -v docker &> /dev/null; then
    echo "❌ Docker is not installed. Please install Docker first."
    exit 1
fi

# Check Docker Compose
if ! command -v docker-compose &> /dev/null; then
    echo "❌ Docker Compose is not installed. Please install Docker Compose first."
    exit 1
fi

# Create folders
mkdir -p data output logs

# Check .env
if [ ! -f .env ]; then
    echo "⚠️  No .env file found. Creating from example..."
    cp .env.example .env
    echo "📌 Edit the .env file to add your Gemini API Key"
    echo "🔑 Get it from: https://aistudio.google.com/apikey"
    exit 1
fi

# Pull latest image
echo "📥 Pulling image..."
docker-compose pull

echo "✅ Ready!"
echo ""
echo "Put your CSVs in 'data/' and run:"
echo "  docker-compose up etl-agent-interactive"
