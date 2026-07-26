"""Canonical empirical implementation for the dissertation."""

from .config import find_repo_root, load_project_config
from .settlement import (
    EventInterval,
    build_standard_11_event_book,
    certify_book,
    classify_temperature,
    validate_partition,
)

__all__ = [
    "EventInterval",
    "build_standard_11_event_book",
    "certify_book",
    "classify_temperature",
    "find_repo_root",
    "load_project_config",
    "validate_partition",
]
