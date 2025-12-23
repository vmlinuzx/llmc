# Dependency Analysis Report - 2025-12-23

**Demon:** Rem the Dependency Testing Demon
**Target:** `/home/vmlinux/src/llmc`
**Status:** INFESTED

## 1. Executive Summary

A plague of vulnerabilities and outdated dependencies has been uncovered. Immediate action is required to purge the rot.

-   **Outdated Packages:** A significant number of dependencies are stale and require updates.
-   **Vulnerabilities:** 25 critical vulnerabilities have been identified across 12 packages. These are not suggestions; they are gaping wounds in your security posture.
-   **Unaudited Packages:** Several packages could not be scanned, leaving potential threats lurking in the shadows.

This report details the corruption. Read it. Act on it. Do not delay.

## 2. Outdated Dependencies

The following dependencies are lagging behind their latest versions. This is a breeding ground for bugs and security holes.

| Package              | Current Version | Latest Version |
| -------------------- | --------------- | -------------- |
| aeidon               | 1.11            | 1.15           |
| ansible              | 9.2.0           | 13.1.0         |
| ansible-core         | 2.16.3          | 2.20.1         |
| apache-libcloud      | 3.4.1           | 3.8.0          |
| argcomplete          | 3.1.4           | 3.6.3          |
| asgiref              | 3.7.2           | 3.11.0         |
| Automat              | 22.10.0         | 25.4.16        |
| Babel                | 2.10.3          | 2.17.0         |
| beautifulsoup4       | 4.12.3          | 4.14.3         |
| blinker              | 1.7.0           | 1.9.0          |
| Brotli               | 1.1.0           | 1.2.0          |
| cachetools           | 6.2.2           | 6.2.4          |
| cclib                | 1.8             | 1.8.1          |
| cheroot              | 10.0.0+ds1      | 11.1.2         |
| chromadb             | 1.3.5           | 1.3.7          |
| configobj            | 5.0.8           | 5.0.9          |
| coverage             | 7.12.0          | 7.13.0         |
| cssselect            | 1.2.0           | 1.3.0          |
| cups-of-caffeine     | 2.9.12          | 2.10.0         |
| dbus-python          | 1.3.2           | 1.4.0          |
| decorator            | 5.1.1           | 5.2.1          |
| diff-match-patch     | 20230430        | 20241021       |
| dnspython            | 2.6.1           | 2.8.0          |
| duplicity            | 2.1.4           | 3.0.6.3        |
| fastapi              | 0.121.3         | 0.127.0        |
| fasteners            | 0.18            | 0.20           |
| Flask                | 3.0.2           | 3.1.2          |
| flatbuffers          | 25.9.23         | 25.12.19       |
| fsspec               | 2025.9.0        | 2025.12.0      |
| fuse-python          | 1.0.7           | 1.0.9          |
| google-auth          | 2.43.0          | 2.45.0         |
| greenlet             | 3.0.3           | 3.3.0          |
| h2                   | 4.1.0           | 4.3.0          |
| hpack                | 4.0.0           | 4.1.0          |
| httplib2             | 0.20.4          | 0.31.0         |
| huggingface-hub      | 0.36.0          | 1.2.3          |
| humanize             | 4.14.0          | 4.15.0         |
| hyperframe           | 6.0.0           | 6.1.0          |
| importlib_metadata   | 8.7.0           | 8.7.1          |
| incremental          | 22.10.0         | 24.11.0        |
| itsdangerous         | 2.1.2           | 2.2.0          |
| jaraco.functools     | 4.0.0           | 4.4.0          |
| joblib               | 1.5.2           | 1.5.3          |
| kaitaistruct         | 0.10            | 0.11           |
| langchain            | 1.0.8           | 1.2.0          |
| langchain-core       | 1.1.0           | 1.2.5          |
| langgraph            | 1.0.3           | 1.0.5          |
| langgraph-sdk        | 0.2.9           | 0.3.1          |
| langsmith            | 0.4.46          | 0.5.0          |
| launchpadlib         | 1.11.0          | 2.1.0          |
| lazr.uri             | 1.0.6           | 1.0.7          |
| Levenshtein          | 0.25.1          | 0.27.3         |
| libcomps             | 0.1.20          | 0.1.23.post1   |
| libvirt-python       | 10.0.0          | 11.10.0        |
| lxml                 | 5.2.1           | 6.0.2          |
| Mako                 | 1.3.2.dev0      | 1.3.10         |
| Markdown             | 3.5.2           | 3.10           |
| MarkupSafe           | 2.1.5           | 3.0.3          |
| mcp                  | 1.24.0          | 1.25.0         |
| meson                | 1.3.2           | 1.10.0         |
| mistletoe            | 1.3.0           | 1.5.1          |
| mistune              | 3.1.4           | 3.2.0          |
| mitmproxy            | 8.1.1           | 12.2.1         |
| more-itertools       | 10.2.0          | 10.8.0         |
| mypy                 | 1.18.2          | 1.19.1         |
| netaddr              | 0.8.0           | 1.3.0          |
| networkx             | 3.5             | 3.6.1          |
| numpy                | 2.3.5           | 2.4.0          |
| opentelemetry-api    | 1.38.0          | 1.39.1         |
| orjson               | 3.11.4          | 3.11.5         |
| ormsgpack            | 1.12.0          | 1.12.1         |
| paramiko             | 2.12.0          | 4.0.0          |
| periodictable        | 1.6.1           | 2.0.2          |
| pip                  | 24.0            | 25.3           |
| pipx                 | 1.4.3           | 1.8.0          |
| platformdirs         | 4.5.0           | 4.5.1          |
| posthog              | 5.4.0           | 7.4.2          |
| protobuf             | 6.33.1          | 6.33.2         |
| pyasyncore           | 1.0.2           | 1.0.4          |
| pybase64             | 1.4.2           | 1.4.3          |
| pycairo              | 1.25.1          | 1.29.0         |
| pycups               | 2.0.1           | 2.0.4          |
| pyenchant            | 3.2.2           | 3.3.0          |
| PyGObject            | 3.48.2          | 3.54.5         |
| pykerberos           | 1.1.14          | 1.2.4          |
| pylibacl             | 0.7.0           | 0.7.3          |
| PyNaCl               | 1.5.0           | 1.6.1          |
| pynvim               | 0.5.0           | 0.6.0          |
| pyOpenSSL            | 23.2.0          | 25.3.0         |
| pyparsing            | 3.2.5           | 3.3.1          |
| pyperclip            | 1.8.2           | 1.11.0         |
| PyQt5                | 5.15.10         | 5.15.11        |
| PyQt5-sip            | 12.13.0         | 12.17.2        |
| PyQtWebEngine        | 5.15.6          | 5.15.7         |
| pytest               | 9.0.1           | 9.0.2          |
| python-debian        | 0.1.49+ubuntu2  | 1.0.1          |
| pytz                 | 2024.1          | 2025.2         |
| pywinrm              | 0.4.3           | 0.5.0          |
| QtPy                 | 2.4.1           | 2.4.3          |
| rapidfuzz            | 3.6.2           | 3.14.3         |
| requests-ntlm        | 1.1.0           | 1.3.0          |
| resolvelib           | 1.0.1           | 1.2.1          |
| ruamel.yaml          | 0.17.21         | 0.18.17        |
| ruamel.yaml.clib     | 0.2.8           | 0.2.15         |
| ruff                 | 0.14.6          | 0.14.10        |
| scikit-learn         | 1.7.2           | 1.8.0          |
| sentence-transformers| 5.1.2           | 5.2.0          |
| service-identity     | 24.1.0          | 24.2.0         |
| simplejson           | 3.19.2          | 3.20.2         |
| soupsieve            | 2.5             | 2.8.1          |
| textual              | 6.7.1           | 6.11.0         |
| tornado              | 6.4             | 6.5.4          |
| transformers         | 4.57.1          | 4.57.3         |
| translate-toolkit    | 3.12.2          | 3.17.5         |
| tree_sitter          | 0.20.1          | 0.25.2         |
| tree-sitter-languages| 1.9.1           | 1.10.2         |
| Twisted              | 24.3.0          | 25.5.0         |
| typer                | 0.20.0          | 0.20.1         |
| urllib3              | 2.3.0           | 2.6.2          |
| urwid                | 2.6.10          | 3.0.3          |
| userpath             | 1.9.1           | 1.9.2          |
| uvicorn              | 0.38.0          | 0.40.0         |
| vobject              | 0.9.6.1         | 0.9.9          |
| wadllib              | 1.3.6           | 2.0.0          |
| wcwidth              | 0.2.5           | 0.2.14         |
| Werkzeug             | 3.0.1           | 3.1.4          |
| wheel                | 0.42.0          | 0.45.1         |
| wsproto              | 1.2.0           | 1.3.2          |
| xdg                  | 5               | 6.0.0          |
| xmltodict            | 0.13.0          | 1.0.2          |
| yq                   | 3.1.0           | 3.4.3          |
| zope.interface       | 6.1             | 8.1.1          |

## 3. Vulnerable Dependencies

The following vulnerabilities have been detected. They must be eradicated.

| Package      | Version | ID                  | Fix Versions                                        |
| ------------ | ------- | ------------------- | --------------------------------------------------- |
| ansible      | 9.2.0   | CVE-2025-14010      | 12.2.0                                              |
| ansible-core | 2.16.3  | CVE-2024-9902       | 2.14.18rc1, 2.15.13rc1, 2.16.13rc1, 2.17.6rc1, 2.18.0rc2 |
| ansible-core | 2.16.3  | CVE-2024-8775       | 2.16.13, 2.17.6                                     |
| ansible-core | 2.16.3  | CVE-2024-11079      | 2.16.14rc1, 2.17.7rc1, 2.18.1rc1                    |
| brotli       | 1.1.0   | CVE-2025-6176       | 1.2.0                                               |
| configobj    | 5.0.8   | CVE-2023-26112      | 5.0.9                                               |
| h2           | 4.1.0   | CVE-2025-57804      | 4.3.0                                               |
| mitmproxy    | 8.1.1   | CVE-2025-23217      | 11.1.2                                              |
| mitmproxy    | 8.1.1   | GHSA-63cx-g855-hvv4 | 12.1.2                                              |
| paramiko     | 2.12.0  | CVE-2023-48795      | 3.4.0                                               |
| pip          | 24.0    | CVE-2025-8869       | 25.3                                                |
| tornado      | 6.4     | GHSA-753j-mpmx-qq6g | 6.4.1                                               |
| tornado      | 6.4     | GHSA-w235-7p84-xx57 | 6.4.1                                               |
| tornado      | 6.4     | CVE-2025-47287      | 6.5                                                 |
| tornado      | 6.4     | CVE-2024-52804      | 6.4.2                                               |
| twisted      | 24.3.0  | PYSEC-2024-75       | 24.7.0rc1                                           |
| twisted      | 24.3.0  | CVE-2024-41671      | 24.7.0rc1                                           |
| urllib3      | 2.3.0   | CVE-2025-50182      | 2.5.0                                               |
| urllib3      | 2.3.0   | CVE-2025-50181      | 2.5.0                                               |
| urllib3      | 2.3.0   | CVE-2025-66418      | 2.6.0                                               |
| urllib3      | 2.3.0   | CVE-2025-66471      | 2.6.0                                               |
| werkzeug     | 3.0.1   | CVE-2024-34069      | 3.0.3                                               |
| werkzeug     | 3.0.1   | CVE-2024-49766      | 3.0.6                                               |
| werkzeug     | 3.0.1   | CVE-2024-49767      | 3.0.6                                               |
| werkzeug     | 3.0.1   | CVE-2025-66221      | 3.1.4                                               |

## 4. Unaudited Dependencies

The following dependencies could not be analyzed. They are blind spots in your defense. Investigate them.

- bcc
- brlapi
- cheroot
- cloud-init
- command-not-found
- cupshelpers
- defer
- distro-info
- gpg
- language-selector
- libcomps
- llmcwrapper
- louis
- mako
- python-apt
- python-debian
- rpm
- screen-resolution-extra
- selinux
- ubuntu-drivers-common
- ubuntu-pro-client
- ufw
- unattended-upgrades
- usb-creator
- xkit

## 5. Recommendations

1.  **Update All Dependencies:** Create a plan to update all outdated packages, starting with the most critical.
2.  **Patch Vulnerabilities:** Immediately update the packages with known vulnerabilities to their fixed versions.
3.  **Investigate Unaudited Packages:** Determine why these packages cannot be audited and find a way to bring them into compliance.
4.  **Implement Continuous Monitoring:** Establish a process for regularly scanning dependencies to prevent future infestations.

Your system is compromised. The demon has shown you the way. Now, act.
