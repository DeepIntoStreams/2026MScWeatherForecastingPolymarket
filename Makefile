.PHONY: test migration-audit execute-00-01

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
