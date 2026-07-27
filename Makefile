.PHONY: test migration-audit execute-00-01 bundle-02 panels-02 execute-02 support-audit-02 verified-panel-02 create-notebooks-02-03 execute-02-03 models-04 create-notebook-04 execute-04 calibrate-05 create-notebook-05 execute-05 predict-06 create-notebook-06 execute-06 evaluate-07 create-notebook-07 execute-07 construct-events-08 create-notebook-08 execute-08

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

support-audit-02:
	python3 tools/audit_notebook02_support.py

verified-panel-02:
	python3 tools/build_verified_notebook02_panel.py

create-notebooks-02-03:
	python3 tools/create_verified_notebooks_02_03.py

execute-02-03:
	python3 -m jupyter nbconvert --to notebook --execute --inplace --ExecutePreprocessor.timeout=600 notebooks/final/02_deterministic_weather_training_panel.ipynb
	python3 -m jupyter nbconvert --to notebook --execute --inplace --ExecutePreprocessor.timeout=600 notebooks/final/03_chronological_design.ipynb

models-04:
	PYTHONPATH=src python3 tools/run_probabilistic_oof_benchmark.py

create-notebook-04:
	python3 tools/create_notebook04.py

execute-04:
	python3 -m jupyter nbconvert --to notebook --execute --inplace --ExecutePreprocessor.timeout=1800 notebooks/final/04_probabilistic_model_selection.ipynb

calibrate-05:
	PYTHONPATH=src python3 tools/calibrate_selected_oof_distribution.py

create-notebook-05:
	python3 tools/create_notebook05.py

execute-05:
	python3 -m jupyter nbconvert --to notebook --execute --inplace --ExecutePreprocessor.timeout=900 notebooks/final/05_continuous_distribution_calibration.ipynb

predict-06:
	PYTHONPATH=src python3 tools/generate_locked_evaluation_predictions.py

create-notebook-06:
	python3 tools/create_notebook06.py

execute-06:
	python3 -m jupyter nbconvert --to notebook --execute --inplace --ExecutePreprocessor.timeout=1200 notebooks/final/06_locked_predictive_distributions.ipynb

evaluate-07:
	PYTHONPATH=src python3 tools/evaluate_locked_continuous_predictions.py

create-notebook-07:
	python3 tools/create_notebook07.py

execute-07:
	python3 -m jupyter nbconvert --to notebook --execute --inplace --ExecutePreprocessor.timeout=900 notebooks/final/07_locked_continuous_evaluation.ipynb

construct-events-08:
	python3 tools/construct_locked_event_probabilities.py

create-notebook-08:
	python3 tools/create_notebook08.py

execute-08:
	python3 -m jupyter nbconvert --to notebook --execute --inplace --ExecutePreprocessor.timeout=900 notebooks/final/08_locked_event_probabilities.ipynb

calibrate-probabilities-09:
	python3 tools/calibrate_event_probabilities.py

execute-09:
	python3 -m jupyter nbconvert --to notebook --execute --inplace --ExecutePreprocessor.timeout=900 notebooks/final/09_probability_calibration.ipynb

test-09:
	PYTHONPATH=src python3 -m unittest tests.test_notebook09_probability_calibration -v
