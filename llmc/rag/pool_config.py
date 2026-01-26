from dataclasses import dataclass, field
import logging
import re
from typing import Any, Literal

from llmc.rag.config_models import get_default_enrichment_model

logger = logging.getLogger(__name__)

@dataclass
class WorkerConfig:
    id: str
    type: Literal["local", "remote"]
    host: str
    port: int = 11434
    concurrency: int = 1
    gpu: int | None = None
    model: str | None = None
    timeout_seconds: int = 120  # Request timeout for Ollama calls
    options: dict[str, Any] = field(default_factory=dict)  # Ollama options (temperature, num_predict, etc.)
    enabled: bool = True
    schedule: str | None = None
    schedule_timezone: str = "UTC"
    api_key_env: str | None = None
    tier: int = 0

@dataclass
class PoolConfig:
    enabled: bool = False
    strategy: Literal["work-stealing", "round-robin", "priority"] = "work-stealing"
    health_check_interval: int = 30
    max_retries: int = 3
    stale_claim_timeout: int = 600
    workers: list[WorkerConfig] = field(default_factory=list)

    @property
    def max_tier(self) -> int:
        if not self.workers:
            return 0
        return max(w.tier for w in self.workers)

def load_pool_config(config_dict: dict[str, Any]) -> PoolConfig:
    """
    Parses the 'enrichment.pool' section from the main configuration dictionary.
    
    Expected structure:
    [enrichment.pool]
    enabled = true
    strategy = "work-stealing"
    
    [[enrichment.pool.workers]]
    id = "local-4060"
    ...
    """
    enrichment_config = config_dict.get("enrichment", {})
    pool_data = enrichment_config.get("pool", {})
    
    # Extract pool-level fields
    enabled = pool_data.get("enabled", False)
    strategy = pool_data.get("strategy", "work-stealing")
    health_check_interval = pool_data.get("health_check_interval", 30)
    max_retries = pool_data.get("max_retries", 3)
    stale_claim_timeout = pool_data.get("stale_claim_timeout", 600)
    
    workers_data = pool_data.get("workers", [])
    workers: list[WorkerConfig] = []
    
    for w_data in workers_data:
        worker = WorkerConfig(
            id=w_data["id"],
            type=w_data["type"], # This might fail if key missing, but valid for now as it's required
            host=w_data["host"],
            port=w_data.get("port", 11434),
            concurrency=w_data.get("concurrency", 1),
            gpu=w_data.get("gpu"),
            model=w_data.get("model") or get_default_enrichment_model(),
            timeout_seconds=w_data.get("timeout_seconds", 120),
            options=dict(w_data.get("options", {})),
            enabled=w_data.get("enabled", True),
            schedule=w_data.get("schedule"),
            schedule_timezone=w_data.get("schedule_timezone", "UTC"),
            api_key_env=w_data.get("api_key_env"),
            tier=w_data.get("tier", 0)
        )
        workers.append(worker)
        
    return PoolConfig(
        enabled=enabled,
        strategy=strategy,
        health_check_interval=health_check_interval,
        max_retries=max_retries,
        stale_claim_timeout=stale_claim_timeout,
        workers=workers
    )

def validate_pool_config(config: PoolConfig) -> list[str]:
    """
    Validates the pool configuration and returns a list of error messages.
    Returns empty list if valid.
    """
    errors = []
    
    # 1. All worker IDs are unique
    worker_ids = [w.id for w in config.workers]
    if len(worker_ids) != len(set(worker_ids)):
        # Find duplicates
        seen = set()
        duplicates = set()
        for x in worker_ids:
            if x in seen:
                duplicates.add(x)
            seen.add(x)
        errors.append(f"Duplicate worker IDs found: {', '.join(duplicates)}")
        
    # 2. Ports are valid (1-65535)
    for w in config.workers:
        if not (1 <= w.port <= 65535):
            errors.append(f"Worker '{w.id}': Invalid port {w.port}. Must be 1-65535.")
            
    # 3. Schedule syntax is valid (HH:MM-HH:MM)
    for w in config.workers:
        if w.schedule:
            try:
                parse_schedule_to_minutes(w.schedule)
            except ValueError:
                 errors.append(f"Worker '{w.id}': Invalid schedule format '{w.schedule}'. Expected HH:MM-HH:MM (24h).")

    # 4. At least one worker enabled if pool enabled
    if config.enabled:
        enabled_workers = [w for w in config.workers if w.enabled]
        if not enabled_workers:
            errors.append("Pool is enabled but no workers are enabled.")
        
        # 5. Warn if no tier 0 workers found
        if config.workers and not any(w.tier == 0 for w in config.workers):
            logger.warning("Pool is enabled but no tier 0 workers defined. This may cause fallback issues.")
            
    return errors

def parse_schedule_to_minutes(schedule: str) -> tuple[int, int]:
    """
    Parses a schedule string "HH:MM-HH:MM" into start and end minutes from midnight.
    Raises ValueError if format is invalid.
    """
    schedule_pattern = re.compile(r"^([0-1]?[0-9]|2[0-3]):[0-5][0-9]-([0-1]?[0-9]|2[0-3]):[0-5][0-9]$")
    if not schedule_pattern.match(schedule):
        raise ValueError(f"Invalid schedule format '{schedule}'. Expected HH:MM-HH:MM.")

    start_str, end_str = schedule.split('-')
    start_h, start_m = map(int, start_str.split(':'))
    end_h, end_m = map(int, end_str.split(':'))
    
    start_minutes = start_h * 60 + start_m
    end_minutes = end_h * 60 + end_m
    
    return start_minutes, end_minutes