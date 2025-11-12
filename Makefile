VENV=.venv
PY=$(VENV)/bin/python
PIP=$(VENV)/bin/pip
RAG=$(VENV)/bin/rag
UVICORN=$(VENV)/bin/uvicorn

.PHONY: install index embed search api clean

install:
	python3 -m venv $(VENV)
	$(PIP) install -U pip wheel
	$(PIP) install -e .[api,embed]

index:
	$(RAG) index

embed:
	$(RAG) embed --execute

search:
	$(RAG) search "$(q)" --json

api:
	$(UVICORN) api.server:app --host 0.0.0.0 --port 8000

clean:
	rm -rf $(VENV) .rag/__pycache__ .rag/*.db __pycache__

