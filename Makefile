PYTHON := ./venv/bin/python

.PHONY: help db-up db-down db-logs migrate seed seed-reset seed-small seed-files demo test lint

help:
	@echo "Targets:"
	@echo "  db-up         поднять PostgreSQL в docker"
	@echo "  db-down       остановить PostgreSQL"
	@echo "  db-logs       логи postgres"
	@echo "  migrate       alembic upgrade head"
	@echo "  seed          заполнить БД (30 сотрудников, 5 команд)"
	@echo "  seed-reset    то же, но с TRUNCATE"
	@echo "  seed-small    8 сотрудников, 2 команды (программно)"
	@echo "  seed-files    small из CSV/JSON фикстур (scripts/seed_data/small/)"
	@echo "  demo          db-up + migrate + seed-reset (одна команда для demo)"
	@echo "  test          pytest"
	@echo "  lint          ruff check"

db-up:
	docker compose up -d
	@echo "Жду готовности postgres..."
	@until docker compose exec postgres pg_isready -U worktime -d worktime_sync >/dev/null 2>&1; do sleep 1; done
	@echo "postgres готов."

db-down:
	docker compose down

db-logs:
	docker compose logs -f postgres

migrate:
	$(PYTHON) -m alembic upgrade head

seed:
	$(PYTHON) -m scripts.seed

seed-reset:
	$(PYTHON) -m scripts.seed --reset

seed-small:
	$(PYTHON) -m scripts.seed --reset --small

seed-files:
	$(PYTHON) -m scripts.seed --reset --small --from-files

demo: db-up migrate seed-reset
	@echo ""
	@echo "Готово. Запусти API:  $(PYTHON) -m uvicorn app.main:app --reload"
	@echo "Логин:  test@example.com / pass1234"

test:
	$(PYTHON) -m pytest -q

lint:
	$(PYTHON) -m ruff check .
