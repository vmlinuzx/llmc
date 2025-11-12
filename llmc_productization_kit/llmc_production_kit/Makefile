VENV=.venv
PY=$(VENV)/bin/python
PIP=$(VENV)/bin/pip
RAG=$(VENV)/bin/rag

.PHONY: install index search api clean

install:
	python3 -m venv $(VENV)
	$(PIP) install -U pip wheel
	$(PIP) install -e .

index:
	$(RAG) index

search:
	$(RAG) search "$(q)"

api:
	$(PIP) install fastapi uvicorn
	$(PY) api/server.py

clean:
	rm -rf $(VENV) .rag/__pycache__ .rag/*.db __pycache__
