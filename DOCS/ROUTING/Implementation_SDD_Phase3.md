# Implementation SDD – Phase 3

Adds `_get_routing_policy()` (env>toml), `_score_erp()`, and a conflict override stage in `classify_query`.
Default behavior prefers code; toggle allows ERP to win in ties.
