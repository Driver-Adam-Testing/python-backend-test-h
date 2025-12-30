"""Storage module."""
from .hot_storage import HotStorage
from .parquet_storage import ParquetStorage

__all__ = ["HotStorage", "ParquetStorage"]

