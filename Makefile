compile:
	pip-compile --generate-hashes requirements.in

compile-dev:
	pip-compile --generate-hashes requirements-dev.in

install:
	pip install -r requirements.txt

install-dev:
	pip install -r requirements-dev.txt

test:
	pytest --disable-warnings --cov=chart_updater --cov-report=html --cov-context=test

test-docker: 
	docker-compose -f docker-compose.test.yaml up
