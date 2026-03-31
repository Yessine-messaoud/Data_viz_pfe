"""
ErrorHandler: Gestion des erreurs et self-healing
"""
from typing import Dict, Any
from enum import Enum
import logging

class RecoveryAction(Enum):
    RETRY = "retry"
    FALLBACK = "fallback"
    SKIP = "skip"
    ABORT = "abort"
    RECONFIGURE = "reconfigure"

class ErrorHandler:
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.logger = logging.getLogger("ErrorHandler")
        self.fallback_registry = FallbackRegistry()
        self.recovery_strategies = self._load_strategies()

    def handle_error(self, error: Exception, step: Dict[str, Any], context: Any, retry_count: int) -> RecoveryAction:
        error_type = type(error).__name__
        step_name = step.get("name")
        self.logger.warning(f"Handling error in {step_name}: {error_type} - {error}")
        max_retries = step.get("max_retries", self.config.get("max_retries", 3))
        if retry_count < max_retries and self._is_retryable(error):
            self.logger.info(f"Retrying step {step_name} ({retry_count + 1}/{max_retries})")
            return RecoveryAction.RETRY
        if step.get("fallback_enabled", True):
            fallback = self.fallback_registry.get_fallback(step_name, error_type)
            if fallback:
                self.logger.info(f"Using fallback for {step_name}: {fallback['name']}")
                return RecoveryAction.FALLBACK
        if not step.get("required", True):
            self.logger.warning(f"Skipping non-required step {step_name}")
            return RecoveryAction.SKIP
        self.logger.error(f"No recovery possible for {step_name}, aborting")
        return RecoveryAction.ABORT

    def _is_retryable(self, error: Exception) -> bool:
        retryable_errors = ["TimeoutError", "ConnectionError", "NetworkError", "TransientError", "RateLimitError"]
        error_type = type(error).__name__
        if error_type in retryable_errors:
            return True
        if "ValidationError" in error_type:
            return False
        if "DataError" in error_type:
            return True
        return False

    def _load_strategies(self) -> Dict:
        return {}

class FallbackRegistry:
    def __init__(self):
        self.fallbacks = {}
    def get_fallback(self, step_name: str, error_type: str):
        return self.fallbacks.get(step_name, {}).get(error_type)
    def register_fallback(self, step_name: str, error_type: str, fallback: Dict):
        if step_name not in self.fallbacks:
            self.fallbacks[step_name] = {}
        self.fallbacks[step_name][error_type] = fallback
