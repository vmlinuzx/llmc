# Dependency Demon Report: 2026-01-16

## 1. Summary

Dependency scan identified critical vulnerabilities, outdated packages, and significant drift between `requirements.txt` and the installed environment.

| Severity | Count | Type |
| --- | --- | --- |
| **P0** | 1 | Critical CVE |
| **P1** | 3 | High CVE |
| **P2** | 5 | Medium CVE |
| **P3** | 88 | Outdated Package |
| **Info** | 1 | Drift Detected |

**Exit Code: 1** (1 Critical Vulnerability Found)

---

## 2. P0: Critical Vulnerabilities (CVSS >= 9.0)

| Package | Version | CVE ID | CVSS | Details | Fix Version |
| --- | --- | --- | --- | --- | --- |
| `langchain-core` | `1.1.0` | `CVE-2025-68664` | 9.3 | Serialization injection via 'lc' key, may lead to RCE. | `1.2.5` |

---

## 3. P1: High Vulnerabilities (CVSS 7.0 - 8.9)

| Package | Version | CVE ID | CVSS | Details | Fix Version |
| --- | --- | --- | --- | --- | --- |
| `urllib3` | `2.3.0` | `CVE-2025-66418` | 8.6 | Unbounded decompression chain can lead to DoS. | `2.6.0` |
| `urllib3` | `2.3.0` | `CVE-2025-66471` | 7.5 | Improper handling of highly compressed data can lead to DoS. | `2.6.0` |
| `urllib3` | `2.3.0` | `CVE-2026-21441` | 8.9 | Decompression bomb safeguards can be bypassed during redirects. | `2.6.3` |

---

## 4. P2: Medium Vulnerabilities (CVSS 4.0 - 6.9)

| Package | Version | CVE ID | CVSS | Details | Fix Version |
| --- | --- | --- | --- | --- | --- |
| `filelock` | `3.20.1` | `CVE-2026-22701` | 5.3 | TOCTOU race condition in SoftFileLock. | `3.20.3` |
| `pip` | `24.0` | `CVE-2025-8869` | 5.9 | Tar archive extraction may not verify symlinks. | `25.3` |
| `pyasn1` | `0.6.1` | `CVE-2026-23490` | N/A | DoS from malformed RELATIVE-OID data. (Score pending) | `0.6.2` |
| `urllib3` | `2.3.0` | `CVE-2025-50182` | 5.3 | Redirects not controlled in Pyodide runtime. | `2.5.0` |
| `urllib3` | `2.3.0` | `CVE-2025-50181` | 5.3 | Disabling redirects at PoolManager level is ignored. | `2.5.0` |

---

## 5. P3: Outdated Packages

88 packages are outdated. Full list below.

<details>
<summary>Click to expand full list of outdated packages</summary>

```
Package                                  Version         Latest          Type
---------------------------------------- --------------- --------------- -----
anyio                                    4.12.0          4.12.1          wheel
build                                    1.3.0           1.4.0           wheel
cachetools                               6.2.2           6.2.4           wheel
certifi                                  2025.11.12      2026.1.4        wheel
chromadb                                 1.3.5           1.4.1           wheel
coverage                                 7.12.0          7.13.1          wheel
fastapi                                  0.121.3         0.128.0         wheel
filelock                                 3.20.1          3.20.3          wheel
flatbuffers                              25.9.23         25.12.19        wheel
fsspec                                   2025.9.0        2026.1.0        wheel
GitPython                                3.1.45          3.1.46          wheel
google-auth                              2.43.0          2.47.0          wheel
huggingface-hub                          0.36.0          1.3.2           wheel
humanize                                 4.14.0          4.15.0          wheel
importlib_metadata                       8.7.0           8.7.1           wheel
joblib                                   1.5.2           1.5.3           wheel
jsonschema                               4.25.1          4.26.0          wheel
kubernetes                               34.1.0          35.0.0          wheel
langchain                                1.0.8           1.2.6           wheel
langchain-core                           1.1.0           1.2.7           wheel
langgraph                                1.0.3           1.0.6           wheel
langgraph-checkpoint                     3.0.1           4.0.0           wheel
langgraph-prebuilt                       1.0.5           1.0.6           wheel
langgraph-sdk                            0.2.9           0.3.3           wheel
langsmith                                0.4.46          0.6.4           wheel
librt                                    0.7.4           0.7.8           wheel
MarkupSafe                               2.1.5           3.0.3           wheel
mcp                                      1.24.0          1.25.0          wheel
mistune                                  3.1.4           3.2.0           wheel
mypy                                     1.18.2          1.19.1          wheel
networkx                                 3.5             3.6.1           wheel
numpy                                    2.3.5           2.4.1           wheel
nvidia-cublas-cu12                       12.8.4.1        12.9.1.4        wheel
nvidia-cuda-cupti-cu12                   12.8.90         12.9.79         wheel
nvidia-cuda-nvrtc-cu12                   12.8.93         12.9.86         wheel
nvidia-cuda-runtime-cu12                 12.8.90         12.9.79         wheel
nvidia-cudnn-cu12                        9.10.2.21       9.18.0.77       wheel
nvidia-cufft-cu12                        11.3.3.83       11.4.1.4        wheel
nvidia-cufile-cu12                       1.13.1.3        1.14.1.1        wheel
nvidia-curand-cu12                       10.3.9.90       10.3.10.19      wheel
nvidia-cusolver-cu12                     11.7.3.90       11.7.5.82       wheel
nvidia-cusparse-cu12                     12.5.8.93       12.5.10.65      wheel
nvidia-cusparselt-cu12                   0.7.1           0.8.1           wheel
nvidia-nccl-cu12                         2.27.5          2.29.2          wheel
nvidia-nvjitlink-cu12                    12.8.93         12.9.86         wheel
nvidia-nvshmem-cu12                      3.3.20          3.5.19          wheel
nvidia-nvtx-cu12                         12.8.90         12.9.79         wheel
opentelemetry-api                        1.38.0          1.39.1          wheel
opentelemetry-exporter-otlp-proto-common 1.38.0          1.39.1          wheel
opentelemetry-exporter-otlp-proto-grpc   1.38.0          1.39.1          wheel
opentelemetry-proto                      1.38.0          1.39.1          wheel
opentelemetry-sdk                        1.38.0          1.39.1          wheel
orjson                                   3.11.4          3.11.5          wheel
ormsgpack                                1.12.0          1.12.1          wheel
pathspec                                 0.12.1          1.0.3           wheel
pillow                                   12.0.0          12.1.0          wheel
pip                                      24.0            25.3            wheel
platformdirs                             4.5.0           4.5.1           wheel
posthog                                  5.4.0           7.5.1           wheel
protobuf                                 6.33.1          6.33.4          wheel
psutil                                   7.1.3           7.2.1           wheel
pyasn1                                   0.6.1           0.6.2           wheel
pybase64                                 1.4.2           1.4.3           wheel
pyparsing                                3.2.5           3.3.1           wheel
PyPika                                   0.48.9          0.50.0          wheel
pytest                                   9.0.1           9.0.2           wheel
regex                                    2025.11.3       2026.1.15       wheel
ruff                                     0.14.6          0.14.13         wheel
scikit-learn                             1.7.2           1.8.0           wheel
scipy                                    1.16.3          1.17.0          wheel
sentence-transformers                    5.1.2           5.2.0           wheel
sse-starlette                            3.0.4           3.1.2           wheel
starlette                                0.50.0          0.51.0          wheel
textual                                  6.7.1           7.3.0           wheel
tokenizers                               0.22.1          0.22.2          wheel
tomli                                    2.3.0           2.4.0           wheel
tomlkit                                  0.13.3          0.14.0          wheel
transformers                             4.57.1          4.57.6          wheel
tree_sitter                              0.20.1          0.25.2          wheel
tree-sitter-languages                    1.9.1           1.10.2          wheel
typer                                    0.20.0          0.21.1          wheel
types-requests                           2.32.4.20250913 2.32.4.20260107 wheel
urllib3                                  2.3.0           2.6.3           wheel
uuid_utils                               0.12.0          0.13.0          wheel
uvicorn                                  0.38.0          0.40.0          wheel
websockets                               15.0.1          16.0            wheel
```

</details>

---

## 6. Drift Analysis (`requirements.txt` vs. `pip freeze`)

Significant drift was detected between the declared dependencies in `requirements.txt` and the actual installed packages in the virtual environment. This indicates that packages have been installed or updated manually without updating the `requirements.txt` file, or that `requirements.txt` specifies ranges that are not met by the environment. This makes the build non-reproducible and can mask vulnerabilities.

<details>
<summary>Click to expand diff</summary>

```diff
--- requirements.txt (sorted)
+++ pip freeze (sorted)
-aiohappyeyeballs==2.6.1
-aiohttp==3.13.3
-aiosignal==1.4.0
-detect-secrets==1.5.0
--e git+https://github.com/vmlinuzx/llmc.git@6191a5b3248ee30d7d152b0c4fb3f9dabf1b25f8#egg=llmc
-fastuuid==0.14.0
-frozenlist==1.8.0
-jiter==0.12.0
+langchain-core>=1.2.5
-langchain-core==1.1.0
-librt==0.7.4
-litellm==1.80.16
-multidict==6.7.0
-nvidia-cublas-cu12==12.8.4.1
-nvidia-cuda-cupti-cu12==12.8.90
-nvidia-cuda-nvrtc-cu12==12.8.93
-nvidia-cuda-runtime-cu12==12.8.90
-nvidia-cudnn-cu12==9.10.2.21
-nvidia-cufft-cu12==11.3.3.83
-nvidia-cufile-cu12==1.13.1.3
-nvidia-curand-cu12==10.3.9.90
-nvidia-cusolver-cu12==11.7.3.90
-nvidia-cusparse-cu12==12.5.8.93
-nvidia-cusparselt-cu12==0.7.1
-nvidia-nccl-cu12==2.27.5
-nvidia-nvjitlink-cu12==12.8.93
-nvidia-nvshmem-cu12==3.3.20
-nvidia-nvtx-cu12==12.8.90
-openai==2.15.0
-propcache==0.4.1
-requests-mock==1.12.1
-respx==0.22.0
-tiktoken==0.12.0
-triton==3.5.1
+urllib3>=2.6.0
-urllib3==2.3.0
-uuid_utils==0.12.0
-yarl==1.22.0

```

</details>
