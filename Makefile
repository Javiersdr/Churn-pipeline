.PHONY: help up down clean fclean test pipeline network dashboard

GREEN  := \033[0;32m
YELLOW := \033[0;33m
NC     := \033[0m

help: ## Show this help
	@echo "$(GREEN)Available commands:$(NC)"
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "  $(YELLOW)%-20s$(NC) %s\n", $$1, $$2}'

up: ## Start all services (MinIO, Airflow, Postgres, Dashboard)
	docker-compose up -d
	@echo "$(GREEN)✓ Services started$(NC)"
	@echo "  MinIO:      http://localhost:9001"
	@echo "  Airflow:    http://localhost:8080"
	@echo "  Dashboard:  http://localhost:8501"

down: ## Stop all services
	docker compose down

clean: ## Remove local data, logs, and generated files (keep Docker volumes)
	rm -rf data/churn_data.duckdb data/churn_data.duckdb.wal logs/*
	rm -rf dbt_churn/target dbt_churn/target_* dbt_churn/logs
	rm -rf results_network results_RF models images
	@echo "$(GREEN)✓ Cleaned$(NC)"

fclean: down clean ## Full clean: stop services and remove Docker volumes
	docker compose down -v
	@echo "$(GREEN)✓ Full clean (volumes removed)$(NC)"

test: ## Run dbt data quality tests
	docker compose run --rm dbt dbt test --profiles-dir /app/dbt_churn

pipeline: up ## Run the full pipeline
	@echo "$(GREEN)Starting ingestion...$(NC)"
	docker compose run --rm dashboard python src/ingestion.py
	@echo "$(GREEN)Running dbt...$(NC)"
	docker compose run --rm dashboard sh -c "cd /app/dbt_churn && dbt run && dbt test && cd .."
	@echo "$(GREEN)Training Random Forest model...$(NC)"
	docker compose run --rm dashboard python ML/RF_churn.py
	@echo "$(GREEN)Running network analysis...$(NC)"
	docker compose run --rm dashboard python ML/co-churn_network.py
	@echo "$(GREEN)Pipeline complete$(NC)"

ci-pipeline: ## Run pipeline in CI (MinIO + execution container only)
	docker compose up -d minio
	docker compose run --rm dashboard python src/ingestion.py
	docker compose run --rm dashboard sh -c "cd /app/dbt_churn && DBT_PROFILES_DIR=docker dbt run && DBT_PROFILES_DIR=docker dbt test"
	docker compose run --rm dashboard python ML/RF_churn.py
	docker compose run --rm dashboard python ML/co-churn_network.py
	docker compose down
	@echo "$(GREEN)✓ CI pipeline complete$(NC)"

dashboard: ## Launch the Streamlit dashboard (if not already running)
	@echo "$(GREEN)Dashboard is already started with 'make up'. Access at http://localhost:8501$(NC)"