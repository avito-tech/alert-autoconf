PYTHON?=python3.7

URL?=localhost:8080/api/
CONFIG_NAME?=etc/example.yaml
LOG_LEVEL=INFO
PYPI_NAME?=yourpypi

help:
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-30s\033[0m %s\n", $$1, $$2}'

clean: clean-build clean-pyc clean-test ## remove all build, test, coverage and Python artifacts

clean-build: ## remove build artifacts
	@rm -fr build/
	@rm -fr dist/
	@rm -fr .eggs/

clean-pyc: ## remove Python file artifacts
	@find . -name '*.pyc' -exec rm -f {} +
	@find . -name '*.pyo' -exec rm -f {} +
	@find . -name '*~' -exec rm -f {} +
	@find . -name '__pycache__' -exec rm -fr {} +

clean-test: ## remove test and coverage artifacts
	@rm -fr .tox/
	@rm -f .coverage
	@rm -fr htmlcov/
	@rm -fr .pytest_cache

run:
	PYTHONPATH=$(PYTHONPATH) $(PYTHON) $(BIN_DIR)/alert.py \
         --url ${URL} \
         --config ${CONFIG_NAME} \
         --log-level ${LOG_LEVEL}

format: ## run black formatter
	${PYTHON} setup.py format

flake: ## run flake8
	${PYTHON} setup.py flake8

test: clean-test ## run tests
	${PYTHON} setup.py pytest

sdist:
	$(PYTHON) ./setup.py sdist

upload:
	$(PYTHON) ./setup.py sdist upload -r $(PYPI_NAME)
