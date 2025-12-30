"""SLOC calculation module."""
from .calculator import (
    DualSLOCCalculator,
    SLOCMetrics,
    bytes_to_sloc,
    sloc_to_bytes,
    calculate_patch_bytes,
    BYTES_PER_LINE,
)

__all__ = [
    "DualSLOCCalculator",
    "SLOCMetrics",
    "bytes_to_sloc",
    "sloc_to_bytes",
    "calculate_patch_bytes",
    "BYTES_PER_LINE",
]

