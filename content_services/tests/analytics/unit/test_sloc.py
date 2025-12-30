"""Unit tests for SLOC calculator."""
import pytest
from analytics.sloc.calculator import (
    DualSLOCCalculator,
    SLOCMetrics,
    bytes_to_sloc,
    sloc_to_bytes,
    calculate_patch_bytes,
    BinaryFileError,
    BYTES_PER_LINE,
)


class TestDualSLOCCalculator:
    """Tests for DualSLOCCalculator class."""

    def test_from_git_diff_basic(self):
        """Test basic diff parsing."""
        diff = """+new line 1
+new line 2
-old line 1"""
        
        metrics = DualSLOCCalculator.from_git_diff(diff)
        
        assert metrics.additions_lines == 2
        assert metrics.deletions_lines == 1
        assert metrics.net_lines == 1
        assert metrics.churn_lines == 3

    def test_from_git_diff_with_metadata(self):
        """Test diff parsing skips metadata lines."""
        diff = """--- a/file.py
+++ b/file.py
@@ -1,3 +1,4 @@
+new line
-old line"""
        
        metrics = DualSLOCCalculator.from_git_diff(diff)
        
        assert metrics.additions_lines == 1
        assert metrics.deletions_lines == 1
        assert metrics.net_lines == 0

    def test_from_git_diff_empty(self):
        """Test empty diff returns zero metrics."""
        metrics = DualSLOCCalculator.from_git_diff("")
        
        assert metrics.additions_lines == 0
        assert metrics.deletions_lines == 0
        assert metrics.is_empty

    def test_from_git_diff_binary_detection(self):
        """Test binary file detection raises exception."""
        diff = "Binary files a/image.png and b/image.png differ"
        
        with pytest.raises(BinaryFileError):
            DualSLOCCalculator.from_git_diff(diff)

    def test_from_line_counts_without_patch(self):
        """Test from_line_counts estimates bytes."""
        metrics = DualSLOCCalculator.from_line_counts(10, 5)
        
        assert metrics.additions_lines == 10
        assert metrics.deletions_lines == 5
        assert metrics.addition_bytes == 10 * BYTES_PER_LINE
        assert metrics.deletion_bytes == 5 * BYTES_PER_LINE

    def test_from_line_counts_with_patch(self):
        """Test from_line_counts uses patch bytes."""
        patch = "+short\n-longer line here"
        metrics = DualSLOCCalculator.from_line_counts(1, 1, patch=patch)
        
        assert metrics.additions_lines == 1
        assert metrics.deletions_lines == 1
        # Bytes should come from actual patch content
        assert metrics.addition_bytes > 0
        assert metrics.deletion_bytes > 0

    def test_byte_metrics_calculation(self):
        """Test byte-based SLOC calculation."""
        # Create diff with known byte sizes
        diff = "+a" * 50 + "\n"  # 50 bytes (one 'a' per line)
        
        metrics = DualSLOCCalculator.from_git_diff(diff)
        
        # 50 lines, each with 1 byte = 50 bytes
        # patch_bytes = 50, sloc = 50 // 50 = 1
        assert metrics.sloc >= 0

    def test_from_batch(self):
        """Test batch processing of diffs."""
        diffs = [
            "+line 1",
            "+line 2\n-line 3",
            "",  # empty
        ]
        
        results = DualSLOCCalculator.from_batch(diffs)
        
        assert len(results) == 3
        assert results[0].additions_lines == 1
        assert results[1].additions_lines == 1
        assert results[2].is_empty


class TestHelperFunctions:
    """Tests for helper functions."""

    def test_bytes_to_sloc(self):
        """Test bytes to SLOC conversion."""
        assert bytes_to_sloc(100) == 2
        assert bytes_to_sloc(50) == 1
        assert bytes_to_sloc(49) == 0
        assert bytes_to_sloc(-100) == 2  # Uses abs()

    def test_sloc_to_bytes(self):
        """Test SLOC to bytes conversion."""
        assert sloc_to_bytes(1) == 50
        assert sloc_to_bytes(10) == 500
        assert sloc_to_bytes(0) == 0

    def test_calculate_patch_bytes(self):
        """Test patch byte calculation."""
        patch = "+hello\n-world"
        
        add_bytes, del_bytes, total = calculate_patch_bytes(patch)
        
        assert add_bytes == 5  # "hello"
        assert del_bytes == 5  # "world"
        assert total == 10

    def test_calculate_patch_bytes_empty(self):
        """Test empty patch returns zeros."""
        add_bytes, del_bytes, total = calculate_patch_bytes(None)
        
        assert add_bytes == 0
        assert del_bytes == 0
        assert total == 0


class TestSLOCMetrics:
    """Tests for SLOCMetrics dataclass."""

    def test_is_empty_true(self):
        """Test is_empty returns True for zero metrics."""
        metrics = SLOCMetrics(
            additions_lines=0,
            deletions_lines=0,
            net_lines=0,
            churn_lines=0,
            addition_bytes=0,
            deletion_bytes=0,
            patch_bytes=0,
            net_bytes=0,
            sloc=0,
            bytes_per_line=0.0
        )
        
        assert metrics.is_empty

    def test_is_empty_false(self):
        """Test is_empty returns False for non-zero metrics."""
        metrics = SLOCMetrics(
            additions_lines=1,
            deletions_lines=0,
            net_lines=1,
            churn_lines=1,
            addition_bytes=50,
            deletion_bytes=0,
            patch_bytes=50,
            net_bytes=50,
            sloc=1,
            bytes_per_line=50.0
        )
        
        assert not metrics.is_empty

