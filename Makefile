.DEFAULT_GOAL := help
sources = megad tests

.PHONY: docker  ## Build a docker image
docker:
	docker build . -t app

.PHONY: dev  ## Run app
dev:
	poetry run uvicorn app.app:app --reload

.PHONY: format  ## Auto-format python source files
format:
	poetry run ruff $(sources) --fix
	poetry run black $(sources)

.PHONY: lint  ## Lint python source files
lint:
	poetry run ruff $(sources)
	poetry run black $(sources) --check --diff


.PHONY: mypy  ## Perform type-checking
mypy:
	poetry run mypy megad

.PHONY: test  ## Run all tests, skipping the type-checker integration tests
test:
	poetry run coverage run -m pytest --durations=10

.PHONY: testcov  ## Run tests and generate a coverage report, skipping the type-checker integration tests
testcov: test
	@echo "building coverage html"
	@poetry run coverage html
	@echo "building coverage xml"
	@poetry run coverage xml

.PHONY: all  ## Run the standard set of checks performed in CI
all: lint mypy testcov

.PHONY: clean  ## Clear local caches and build artifacts
clean:
	rm -rf `find . -name __pycache__`
	rm -f `find . -type f -name '*.py[co]'`
	rm -f `find . -type f -name '*~'`
	rm -f `find . -type f -name '.*~'`
	rm -rf .cache
	rm -rf .pytest_cache
	rm -rf .ruff_cache
	rm -rf .mypy_cache
	rm -rf htmlcov
	rm -rf *.egg-info
	rm -f .coverage
	rm -f .coverage.*
	rm -f coverage.xml
	rm -rf build
	rm -rf dist

.PHONY: pre  ## Run pre-commit
pre:
	poetry run pre-commit run --all-files --show-diff-on-failure

.PHONY: help  ## Display this message
help:
	@grep -E \
		'^.PHONY: .*?## .*$$' $(MAKEFILE_LIST) | \
		sort | \
		awk 'BEGIN {FS = ".PHONY: |## "}; {printf "\033[36m%-19s\033[0m %s\n", $$2, $$3}'

db:
	poetry run python3 migrate.py

build:
	poetry build

publish:
	poetry publish