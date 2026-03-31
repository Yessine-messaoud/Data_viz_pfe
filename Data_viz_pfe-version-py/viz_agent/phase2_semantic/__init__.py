"""Phase 2: hybrid semantic layer."""

__all__ = ["Phase2SemanticOrchestrator"]


def __getattr__(name: str):
    # Lazy import to keep package import lightweight in minimal test environments.
    if name == "Phase2SemanticOrchestrator":
        from .phase2_orchestrator import Phase2SemanticOrchestrator

        return Phase2SemanticOrchestrator
    raise AttributeError(name)
