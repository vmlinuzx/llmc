# llmcwrapper/rag_client.py
# Minimal RAG client veneer: HTTP HEAD check for health; no-op in yolo.

import urllib.request


class NullRAG:
    def head(self, url): return True

class HttpRAG:
    def head(self, url, timeout=2):
        req = urllib.request.Request(url, method="HEAD")
        urllib.request.urlopen(req, timeout=timeout)
        return True
