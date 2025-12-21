# Dependency Analysis Report for llmc

**Date:** 2025-12-21
**Analyst:** Rem, the Dependency Testing Demon

## 1. Summary

This report provides a dependency analysis for the `llmc` repository. The analysis found **5 known vulnerabilities** in 2 packages. Additionally, **19 packages** were identified as outdated. This report details these findings to help prioritize dependency updates and mitigate security risks.

---

## 2. Vulnerability Analysis

The following vulnerabilities were detected in the environment. It is recommended to update these packages to the specified "Fix Versions" as soon as possible.

| Package | Version | Vulnerability ID | Fix Versions |
|---|---|---|---|
| pip | 24.0 | CVE-2025-8869 | 25.3 |
| urllib3 | 2.3.0 | CVE-2025-50182 | 2.5.0 |
| urllib3 | 2.3.0 | CVE-2025-50181 | 2.5.0 |
| urllib3 | 2.3.0 | CVE-2025-66418 | 2.6.0 |
| urllib3 | 2.3.0 | CVE-2025-66471 | 2.6.0 |

---

## 3. Outdated Dependencies

The following packages are outdated. Updating these packages can provide new features, bug fixes, and security patches.

| Package | Current Version | Latest Version |
|---|---|---|
| huggingface-hub | 0.36.0 | 1.2.3 |
| nvidia-cublas-cu12 | 12.8.4.1 | 12.9.1.4 |
| nvidia-cuda-cupti-cu12 | 12.8.90 | 12.9.79 |
| nvidia-cuda-nvrtc-cu12 | 12.8.93 | 12.9.86 |
| nvidia-cuda-runtime-cu12 | 12.8.90 | 12.9.79 |
| nvidia-cudnn-cu12 | 9.10.2.21 | 9.17.0.29 |
| nvidia-cufft-cu12 | 11.3.3.83 | 11.4.1.4 |
| nvidia-cufile-cu12 | 1.13.1.3 | 1.14.1.1 |
| nvidia-curand-cu12 | 10.3.9.90 | 10.3.10.19 |
| nvidia-cusolver-cu12 | 11.7.3.90 | 11.7.5.82 |
| nvidia-cusparse-cu12 | 12.5.8.93 | 12.5.10.65 |
| nvidia-cusparselt-cu12 | 0.7.1 | 0.8.1 |
| nvidia-nccl-cu12 | 2.27.5 | 2.28.9 |
| nvidia-nvjitlink-cu12 | 12.8.93 | 12.9.86 |
| nvidia-nvshmem-cu12 | 3.3.20 | 3.4.5 |
| nvidia-nvtx-cu12 | 12.8.90 | 12.9.79 |
| pip | 24.0 | 25.3 |
| posthog | 5.4.0 | 7.4.0 |
| urllib3 | 2.3.0 | 2.6.2 |

---

## 4. Project Dependencies

### Direct Dependencies

These are the core dependencies as specified in `pyproject.toml`.

- requests
- tomli; python_version<'3.11'
- typer
- rich
- tomli-w
- textual
- tomlkit
- simpleeval

### Full Dependency List

The analysis was performed on the environment defined by `requirements.txt`, which includes direct, transitive, and development dependencies. The full list is included in the project's `requirements.txt` file.
