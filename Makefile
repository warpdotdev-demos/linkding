.PHONY: serve serve-bg serve-stop serve-status serve-logs \
	tasks tasks-bg tasks-stop tasks-logs \
	frontend frontend-bg frontend-stop frontend-logs

# Host/port used by the background dev server targets.
HOST ?= 127.0.0.1
PORT ?= 8000

init:
	uv sync
	[ -d data ] || mkdir data data/assets data/favicons data/previews
	uv run manage.py migrate
	npm install

serve:
	uv run manage.py runserver

# Background variants: these return once the process is up instead of blocking
# the shell, which makes them usable from scripts and coding agents.
serve-bg:
	@scripts/dev-process.sh start serve "http://$(HOST):$(PORT)/" uv run manage.py runserver $(HOST):$(PORT)

serve-stop:
	@scripts/dev-process.sh stop serve

serve-status:
	@scripts/dev-process.sh status serve || true

serve-logs:
	@scripts/dev-process.sh logs serve

tasks:
	uv run manage.py run_huey

tasks-bg:
	@scripts/dev-process.sh start tasks "log:Huey consumer started" uv run manage.py run_huey

tasks-stop:
	@scripts/dev-process.sh stop tasks

tasks-logs:
	@scripts/dev-process.sh logs tasks

test:
	uv run pytest -n auto

lint:
	uv run ruff check bookmarks

format:
	uv run ruff format bookmarks
	uv run djlint bookmarks/templates --reformat --quiet --warn
	npx prettier bookmarks/frontend --write
	npx prettier bookmarks/styles --write

prepare-e2e:
	uv run playwright install chromium
	rm -rf static
	npm run build
	uv run manage.py collectstatic --no-input

e2e:
	make prepare-e2e
	uv run pytest bookmarks/tests_e2e -n auto -o "python_files=e2e_test_*.py"

frontend:
	npm run dev

frontend-bg:
	@scripts/dev-process.sh start frontend "log:created bookmarks/static/bundle.js|waiting for changes" npm run dev

frontend-stop:
	@scripts/dev-process.sh stop frontend

frontend-logs:
	@scripts/dev-process.sh logs frontend
