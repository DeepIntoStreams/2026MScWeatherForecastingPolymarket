.PHONY: test migration-audit execute-00-01 bundle-02 panels-02 execute-02

test:
PYTHONPATH=src python3 -m unittest discover -s tests -v

migration-audit:
python3 tools/audit_notebook_00_01_sources.py

execute-00-01:
python3 -m jupyter nbconvert \
--to notebook \
--execute \
--inplace \
--ExecutePreprocessor.timeout=300 \
notebooks/final/00_project_configuration_and_manifest.ipynb
python3 -m jupyter nbconvert \
--to notebook \
--execute \
--inplace \
--ExecutePreprocessor.timeout=300 \
notebooks/final/01_hko_settlement_and_event_certification.ipynb

bundle-02:
	python3 tools/materialise_notebook02_sources.py

panels-02:
	python3 tools/build_notebook02_panels.py

execute-02:
	python3 -m jupyter nbconvert \
		--to notebook \
		--execute \
		--inplace \
		--ExecutePreprocessor.timeout=600 \
		notebooks/final/02_deterministic_weather_training_panel.ipynb
