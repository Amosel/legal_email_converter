PYTHON ?= python3
ifneq ($(origin PYTHON),command line)
ifneq ("$(wildcard .venv/bin/python)","")
PYTHON := .venv/bin/python
endif
endif
SCRIPTS := scripts
VENV ?= .venv
VENV_PYTHON := $(VENV)/bin/python
VENV_PIP := $(VENV)/bin/pip
VENV_BIN := $(VENV)/bin

# Optional variables for targets:
#   make filter-emails SENDER=a@x.com RECIPIENT=b@y.com
#   make export-mbox MBOX="/path/to/box.mbox/mbox" OUT_DIR="/path/to/out" NAME=my_package SKIP_OCR=1 KEEP_ATTACHMENTS=1 FORCE=1
SENDER ?=
RECIPIENT ?=
MBOX ?=
OUT_DIR ?=
NAME ?=
SKIP_OCR ?= 0
KEEP_ATTACHMENTS ?= 0
KEEP_ARTIFACTS ?= 0
FORCE ?= 0
PDF_WORKERS ?=
PDF_OCR_JOBS ?=
PDF_SKIP_OCR ?= 0
TEST_SCOPE ?= all
INTEGRATION_CONFIG ?= tests/integration_pdf_matrix.local.yaml
STRICT_INTEGRATION ?= 0

.PHONY: help install run-all extract-archives create-mbox create-pdf-mbox generate-reports filter-emails list-emails complete-inventory export-mbox test test-all test-unit test-integration test-real-integration test-mbox-export test-cli integration-matrix integration-init-yaml bench only-integration only-unit venv install-cli install-cli-user install-cli-pipx cli-help cli-smoke ocr-bench

help:
	@echo ""
	@echo "Legal Email Converter - Make Commands"
	@echo ""
	@echo "Pipeline"
	@echo "  make run-all                Run full workflow via scripts/run_all.py"
	@echo ""
	@echo "Individual Steps"
	@echo "  make extract-archives       Step 0: extract archive files"
	@echo "  make create-mbox            Step 1: convert .msg -> Apple Mail .mbox"
	@echo "  make create-pdf-mbox        Step 2: OCR PDFs -> mbox"
	@echo "  make generate-reports       Step 3: generate CSV + Markdown reports"
	@echo "  make filter-emails          Step 4: interactive filter"
	@echo "  make list-emails            Step 4 helper: list sender/recipient values"
	@echo "  make complete-inventory     Generate complete file inventory"
	@echo "  make export-mbox            Step 5: raw .mbox -> single review zip"
	@echo ""
	@echo "Testing"
	@echo "  make test                   Exhaustive local tests (unit + integration harness)"
	@echo "  make test-unit              Run unit-focused tests only"
	@echo "  make test-integration       Run integration-focused tests only"
	@echo "  make TEST_SCOPE=unit|integration|all test"
	@echo "  make test-real-integration INTEGRATION_CONFIG=tests/integration_pdf_matrix.local.yaml"
	@echo "  make integration-init-yaml  Create local YAML matrix config template"
	@echo "  make integration-matrix      Run matrix using INTEGRATION_CONFIG (YAML)"
	@echo "  make bench                  Run matrix and print concise benchmark table"
	@echo ""
	@echo "CLI Packaging"
	@echo "  make install                Smart install (pipx if available, else local .venv)"
	@echo "  make venv                   Create local virtual environment"
	@echo "  make install-cli            Install CLI in venv (offline-safe fallback)"
	@echo "  make install-cli-user       Install CLI via pip --user (puts command in user bin)"
	@echo "  make install-cli-pipx       Install CLI via pipx (recommended for global CLI use)"
	@echo "  make cli-help               Show CLI help from venv"
	@echo "  make cli-smoke              Run CLI smoke test and create sample zip"
	@echo "  make ocr-bench              Benchmark PDF OCR profiles (writes logs to /tmp)"
	@echo ""
	@echo "Common Variables"
	@echo "  SENDER, RECIPIENT           Used by make filter-emails"
	@echo "  MBOX                        Input raw mbox file path"
	@echo "  OUT_DIR                     Output directory (default: next to MBOX)"
	@echo "  NAME                        Package base name (default: mailbox_review_package)"
	@echo "  SKIP_OCR=1                  Skip OCR fallback for PDFs (faster)"
	@echo "  PDF_WORKERS=N               Parallel PDF processing workers for create-pdf-mbox"
	@echo "  PDF_OCR_JOBS=N              ocrmypdf --jobs value per processed PDF"
	@echo "  PDF_SKIP_OCR=1              Disable OCR fallback in create-pdf-mbox"
	@echo "  KEEP_ATTACHMENTS=1          Include raw attachments in zip"
	@echo "  KEEP_ARTIFACTS=1            Keep expanded package folder"
	@echo "  FORCE=1                     Overwrite existing output zip"
	@echo ""
	@echo "Examples"
	@echo "  make filter-emails SENDER=a@x.com RECIPIENT=b@y.com"
	@echo "  make export-mbox MBOX=\"/path/Case.mbox/mbox\" SKIP_OCR=1 FORCE=1"
	@echo ""

run-all:
	$(PYTHON) $(SCRIPTS)/run_all.py

extract-archives:
	$(PYTHON) $(SCRIPTS)/0_extract_archives.py

create-mbox:
	$(PYTHON) $(SCRIPTS)/1_create_mbox.py

create-pdf-mbox:
	$(PYTHON) $(SCRIPTS)/2_create_pdf_mbox.py \
	$(if $(PDF_WORKERS),--workers $(PDF_WORKERS),) \
	$(if $(PDF_OCR_JOBS),--ocr-jobs $(PDF_OCR_JOBS),) \
	$(if $(filter 1 true TRUE yes YES,$(PDF_SKIP_OCR)),--skip-ocr,)

generate-reports:
	$(PYTHON) $(SCRIPTS)/3_generate_reports.py

filter-emails:
	$(PYTHON) $(SCRIPTS)/4_filter_emails.py $(if $(SENDER),--sender "$(SENDER)",) $(if $(RECIPIENT),--recipient "$(RECIPIENT)",)

list-emails:
	$(PYTHON) $(SCRIPTS)/4_filter_emails.py --list-emails

complete-inventory:
	$(PYTHON) $(SCRIPTS)/generate_complete_inventory.py

export-mbox:
	$(PYTHON) $(SCRIPTS)/5_export_mbox_for_llm.py \
	$(if $(MBOX),--mbox "$(MBOX)",) \
	$(if $(OUT_DIR),--out-dir "$(OUT_DIR)",) \
	$(if $(NAME),--name "$(NAME)",) \
	$(if $(filter 1 true TRUE yes YES,$(SKIP_OCR)),--skip-ocr,) \
	$(if $(filter 1 true TRUE yes YES,$(KEEP_ATTACHMENTS)),--keep-attachments,) \
	$(if $(filter 1 true TRUE yes YES,$(KEEP_ARTIFACTS)),--keep-artifacts,) \
	$(if $(filter 1 true TRUE yes YES,$(FORCE)),--force,)

test:
	@set -e; \
	scope="$(TEST_SCOPE)"; \
	case "$(MAKECMDGOALS)" in \
		*only-unit*) scope=unit ;; \
		*only-integration*) scope=integration ;; \
	esac; \
	case "$$scope" in \
		unit) $(MAKE) test-unit ;; \
		integration) $(MAKE) test-integration ;; \
		all) $(MAKE) test-all ;; \
		*) echo "Unknown TEST_SCOPE=$$scope. Use unit|integration|all" >&2; exit 2 ;; \
	esac

test-all: test-unit test-integration

test-mbox-export:
	$(PYTHON) -m unittest tests/test_export_mbox_for_llm.py -v

test-pdf-ingest:
	$(PYTHON) -m unittest tests/test_pdf_ingest.py -v

test-cli:
	$(PYTHON) -m unittest tests/test_cli.py -v

test-unit: test-mbox-export test-cli

test-integration: test-pdf-ingest
	@set -e; \
	if [ -f "$(INTEGRATION_CONFIG)" ]; then \
		if ! $(PYTHON) -c "import yaml" >/dev/null 2>&1; then \
			if [ "$(STRICT_INTEGRATION)" = "1" ]; then \
				echo "STRICT_INTEGRATION=1 and PyYAML missing for $(INTEGRATION_CONFIG)." >&2; \
				echo "Install with: pip install pyyaml" >&2; \
				exit 2; \
			fi; \
			echo "Skipping real PDF integration matrix (PyYAML missing for $(INTEGRATION_CONFIG))."; \
			echo "Install with: pip install pyyaml"; \
		else \
			echo "Detected real integration config at $(INTEGRATION_CONFIG)"; \
			$(MAKE) test-real-integration INTEGRATION_CONFIG="$(INTEGRATION_CONFIG)"; \
		fi; \
	elif [ "$(STRICT_INTEGRATION)" = "1" ]; then \
		echo "STRICT_INTEGRATION=1 but config not found: $(INTEGRATION_CONFIG)" >&2; \
		exit 2; \
	else \
		echo "Skipping real PDF integration matrix (config not found: $(INTEGRATION_CONFIG))"; \
		echo "Tip: run 'make integration-init-yaml' and fill real paths."; \
	fi

test-real-integration:
	@set -e; \
	if [ ! -f "$(INTEGRATION_CONFIG)" ]; then \
		if [ "$(STRICT_INTEGRATION)" = "1" ]; then \
			echo "Config not found: $(INTEGRATION_CONFIG)" >&2; \
			echo "Tip: run 'make integration-init-yaml' then edit paths/expectations." >&2; \
			exit 2; \
		fi; \
		echo "Skipping real integration matrix (config not found: $(INTEGRATION_CONFIG))."; \
		echo "Tip: run 'make integration-init-yaml' then edit paths/expectations."; \
		exit 0; \
	fi; \
	if ! $(PYTHON) -c "import yaml" >/dev/null 2>&1; then \
		if [ "$(STRICT_INTEGRATION)" = "1" ]; then \
			echo "Missing dependency: PyYAML" >&2; \
			echo "Install with: pip install pyyaml" >&2; \
			exit 2; \
		fi; \
		echo "Skipping real integration matrix (PyYAML not installed)."; \
		echo "Install with: pip install pyyaml"; \
		exit 0; \
	fi; \
	$(PYTHON) scripts/run_pdf_integration_matrix.py --config "$(INTEGRATION_CONFIG)"

integration-matrix:
	@set -e; \
	cfg="$(if $(CONFIG),$(CONFIG),$(INTEGRATION_CONFIG))"; \
	if [ ! -f "$$cfg" ]; then \
		if [ "$$cfg" = "tests/integration_pdf_matrix.local.yaml" ]; then \
			$(MAKE) integration-init-yaml; \
			echo "Template created at $$cfg"; \
		fi; \
		if [ "$(STRICT_INTEGRATION)" = "1" ]; then \
			echo "Config not found: $$cfg" >&2; \
			echo "Next: edit $$cfg and rerun 'make integration-matrix'." >&2; \
			exit 2; \
		fi; \
		echo "Skipping integration matrix (config not found: $$cfg)."; \
		echo "Next: edit $$cfg and rerun 'make integration-matrix'."; \
		exit 0; \
	fi; \
	if ! $(PYTHON) -c "import yaml" >/dev/null 2>&1; then \
		if [ "$(STRICT_INTEGRATION)" = "1" ]; then \
			echo "Missing dependency: PyYAML" >&2; \
			echo "Install with: pip install pyyaml" >&2; \
			exit 2; \
		fi; \
		echo "Skipping integration matrix (PyYAML not installed)."; \
		echo "Install with: pip install pyyaml"; \
		exit 0; \
	fi; \
	$(PYTHON) scripts/run_pdf_integration_matrix.py --config "$$cfg"

integration-init-yaml:
	@test -f tests/integration_pdf_matrix.local.yaml || cp tests/integration_pdf_matrix.example.yaml tests/integration_pdf_matrix.local.yaml
	@echo "Ready: tests/integration_pdf_matrix.local.yaml"

bench:
	@set -e; \
	py="$(PYTHON)"; \
	cfg="$(INTEGRATION_CONFIG)"; \
	if [ ! -f "$$cfg" ]; then \
		$(MAKE) integration-init-yaml; \
		echo "Template created at $$cfg"; \
		if [ "$(STRICT_INTEGRATION)" = "1" ]; then \
			echo "Config not found: $$cfg" >&2; \
			echo "Next: edit $$cfg and rerun 'make bench'." >&2; \
			exit 2; \
		fi; \
		echo "Skipping benchmark (config not ready)."; \
		echo "Next: edit $$cfg and rerun 'make bench'."; \
		exit 0; \
	fi; \
	if ! "$$py" -c "import yaml" >/dev/null 2>&1; then \
		alt_py="$$(command -v python3 || true)"; \
		if [ -n "$$alt_py" ] && [ "$$alt_py" != "$$py" ] && "$$alt_py" -c "import yaml" >/dev/null 2>&1; then \
			echo "PyYAML available in $$alt_py; using that interpreter for bench."; \
			py="$$alt_py"; \
		fi; \
	fi; \
	if ! "$$py" -c "import yaml" >/dev/null 2>&1; then \
		if [ "$$py" != "$(VENV)/bin/python" ]; then \
			echo "PyYAML not available in $$py; switching to local .venv..."; \
			$(MAKE) venv; \
			py="$(VENV)/bin/python"; \
		else \
			echo "PyYAML not available in $$py; installing into existing .venv..."; \
		fi; \
		wheel="$$(ls -1 vendor/wheels/PyYAML-*.whl PyYAML-*.whl 2>/dev/null | head -n 1 || true)"; \
		if [ -n "$$wheel" ] && "$$py" -m pip install "$$wheel"; then \
			:; \
		elif ! "$$py" -m pip install pyyaml; then \
			echo "Automatic install failed for PyYAML in .venv." >&2; \
			echo "Install manually with: $$py -m pip install pyyaml" >&2; \
			echo "Or place wheel at: vendor/wheels/PyYAML-<ver>-*.whl" >&2; \
			exit 2; \
		fi; \
		if ! "$$py" -c "import yaml" >/dev/null 2>&1; then \
			echo "PyYAML install completed but import still fails for $$py." >&2; \
			exit 2; \
		fi; \
	fi; \
	echo "Using Python interpreter: $$py"; \
	"$$py" scripts/run_pdf_integration_matrix.py --config "$$cfg" --bench

# Backward-compatible aliases; keep canonical entrypoints as:
#   make test-unit
#   make test-integration
only-integration:
	@:

only-unit:
	@:

install:
	@set -e; \
	if command -v pipx >/dev/null 2>&1; then \
		$(MAKE) install-cli-pipx; \
	else \
		echo "pipx not found; falling back to local venv install (make install-cli)."; \
		$(MAKE) install-cli; \
	fi

venv:
	$(PYTHON) -m venv $(VENV)

install-cli: venv
	@set -e; \
	. $(VENV)/bin/activate; \
	$(VENV_PYTHON) -m ensurepip --upgrade >/dev/null 2>&1 || true; \
	if $(VENV_PYTHON) -c "import setuptools" >/dev/null 2>&1; then \
		echo "Installing package with pip..."; \
		$(VENV_PIP) install --no-deps --no-build-isolation .; \
	else \
		echo "setuptools not available; creating local shim command in $(VENV_BIN)"; \
		printf '%s\n' '#!/bin/sh' \
			'SCRIPT_DIR="$$(CDPATH= cd -- "$$(dirname -- "$$0")" && pwd)"' \
			'REPO_ROOT="$$(CDPATH= cd -- "$$SCRIPT_DIR/../.." && pwd)"' \
			'PYTHONPATH="$$REPO_ROOT/src:$$PYTHONPATH" exec "$$SCRIPT_DIR/python" -m legal_email_converter "$$@"' \
			> "$(VENV_BIN)/legal-email-converter"; \
		chmod +x "$(VENV_BIN)/legal-email-converter"; \
	fi; \
	echo "CLI ready: $(VENV_BIN)/legal-email-converter"

install-cli-user:
	$(PYTHON) -m pip install --user --no-deps --no-build-isolation .
	@echo "If command is not found, add this to PATH:"
	@echo "  export PATH=\"$$HOME/Library/Python/$$(python3 -c 'import sys; print(f\"{sys.version_info.major}.{sys.version_info.minor}\")')/bin:$$PATH\""

install-cli-pipx:
	@command -v pipx >/dev/null 2>&1 || (echo "pipx not found. Install with: brew install pipx" && exit 1)
	pipx install . --force
	@echo "CLI ready: legal-email-converter"

cli-help: install-cli
	$(VENV_BIN)/legal-email-converter --help

cli-smoke: install-cli
	@set -e; \
	mkdir -p /tmp/lec_smoke_make; \
	printf '%s\n' \
		'From sender@example.com Mon Jan 01 00:00:00 2024' \
		'Date: Mon, 01 Jan 2024 10:00:00 +0000' \
		'From: Alice <alice@example.com>' \
		'To: Bob <bob@example.com>' \
		'Subject: Make Smoke Test' \
		'Message-ID: <make-smoke@example.com>' \
		'Content-Type: text/plain; charset="utf-8"' \
		'' \
		'Hello from make smoke test.' \
		'' \
		> /tmp/lec_smoke_make/sample.mbox; \
	$(VENV_BIN)/legal-email-converter export-mbox --mbox /tmp/lec_smoke_make/sample.mbox --out-dir /tmp/lec_smoke_make/out --name smoke_pkg --force --skip-ocr; \
	ls -l /tmp/lec_smoke_make/out/smoke_pkg.zip

ocr-bench:
	@set -e; \
	ts=$$(date +%Y%m%d_%H%M%S); \
	out_dir=/tmp/lec_ocr_bench_$$ts; \
	mkdir -p $$out_dir; \
	echo "Writing benchmark logs to: $$out_dir"; \
	run_profile() { \
		name="$$1"; shift; \
		log="$$out_dir/$$name.log"; \
		echo ""; \
		echo "=== $$name ==="; \
		/usr/bin/time -p sh -c "$(PYTHON) $(SCRIPTS)/2_create_pdf_mbox.py $$* > \"$$log\" 2>&1" 2>"$$out_dir/$$name.time"; \
		real_time=$$(awk '/^real / {print $$2}' "$$out_dir/$$name.time"); \
		ok_count=$$(rg -c "Processing .*✓" "$$log" || true); \
		skipped_count=$$(rg -c "no text extracted" "$$log" || true); \
		failed_count=$$(rg -c "✗ Error:" "$$log" || true); \
		echo "real=$$real_time s | ok=$$ok_count skipped=$$skipped_count failed=$$failed_count"; \
	}; \
	run_profile "baseline_skip_ocr_w4" "--workers 4 --skip-ocr"; \
	run_profile "balanced_ocr_w2_j2" "--workers 2 --ocr-jobs 2"; \
	run_profile "throughput_ocr_w4_j2" "--workers 4 --ocr-jobs 2"; \
	echo ""; \
	echo "Benchmark complete. Inspect logs in $$out_dir"
