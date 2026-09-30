PYTHON ?= python

install:
	$(PYTHON) -m pip install -r requirements.txt

download:
	$(PYTHON) scripts/download_reports.py

parse:
	$(PYTHON) scripts/parse_reports.py

index-qwen:
	$(PYTHON) scripts/build_index.py --backend qwen

index-cpu:
	$(PYTHON) scripts/setup_local_models.py --light-embedding
	$(PYTHON) scripts/build_index.py --backend semantic --model BAAI/bge-small-zh-v1.5

index-offline:
	$(PYTHON) scripts/build_index.py --backend hash

evaluate:
	$(PYTHON) scripts/evaluate.py

app:
	$(PYTHON) -m streamlit run app.py

