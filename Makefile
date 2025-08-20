# ETL Agent Makefile

.PHONY: help build run interactive clean install test

# Default target
help:
	@echo "ETL Agent - Available commands:"
	@echo "  make install    - Install dependencies locally"
	@echo "  make build      - Build Docker image"
	@echo "  make run        - Run ETL agent with Docker"
	@echo "  make interactive - Run interactive Docker session"
	@echo "  make local      - Run locally (requires local Python setup)"
	@echo "  make clean      - Clean up Docker images and containers"
	@echo "  make test       - Run basic tests"
	@echo ""
	@echo "Usage examples:"
	@echo "  make run DATA=data.csv"
	@echo "  make local SOURCE=file1.csv,file2.csv"

# Install dependencies locally
install:
	pip install -r requirements.txt
	python -m spacy download en_core_web_sm

# Build Docker image
build:
	docker build -t etl-agent .

# Run with Docker (specify DATA environment variable)
run: build
	@if [ -z "$(DATA)" ]; then \
		echo "Usage: make run DATA=your_file.csv"; \
		exit 1; \
	fi
	docker run -it --rm \
		-e GEMINI_API_KEY=${GEMINI_API_KEY} \
		-v $(PWD)/data:/app/data:ro \
		-v $(PWD)/output:/app/output \
		-v $(PWD)/logs:/app/logs \
		etl-agent --source /app/data/$(DATA) --output_dir /app/output

# Run interactive Docker session
interactive: build
	docker run -it --rm \
		-e GEMINI_API_KEY=${GEMINI_API_KEY} \
		-v $(PWD)/data:/app/data:ro \
		-v $(PWD)/output:/app/output \
		-v $(PWD)/logs:/app/logs \
		--entrypoint /bin/bash \
		etl-agent

# Run locally
local:
	@if [ -z "$(SOURCE)" ]; then \
		echo "Usage: make local SOURCE=file1.csv"; \
		exit 1; \
	fi
	python improved_etl.py --source $(subst $(comma), ,$(SOURCE)) --output_dir ./output

# Clean up Docker resources
clean:
	docker system prune -f
	docker image rm etl-agent 2>/dev/null || true

# Basic test
test:
	@echo "Testing ETL agent..."
	python -c "import pandas as pd; import google.generativeai as genai; print('✅ Dependencies OK')"
	@if [ -f .env ]; then \
		python -c "from dotenv import load_dotenv; import os; load_dotenv(); print('✅ API Key:', 'Found' if os.getenv('GEMINI_API_KEY') else 'Missing')"; \
	else \
		echo "⚠️ .env file not found"; \
	fi

# Helper to handle comma-separated values
comma := ,
