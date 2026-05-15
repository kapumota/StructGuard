.PHONY: install test smoke demo validate clean

install:
	python -m pip install -e .

test:
	PYTHONPATH=src pytest -q

smoke:
	bash scripts/smoke_test.sh

demo:
	bash scripts/final_demo.sh

validate:
	bash scripts/validate_release.sh

clean:
	rm -rf .pytest_cache build dist *.egg-info report/smoke_* demos/final_demo
	find . -type d -name '__pycache__' -prune -exec rm -rf {} +
	find . -type f -name '*.pyc' -delete
