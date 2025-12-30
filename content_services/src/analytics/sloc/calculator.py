"""
SLOC calculation utilities with dual metrics support.

Implements both traditional line-based (GitHub-style) and byte-based (Driver-style)
SLOC measurement:
- Line-based: additions - deletions from diff
- Byte-based: UTF-8 bytes ÷ 50 (python-backend compatible)
"""

from dataclasses import dataclass


# Conversion factor (must match python-backend)
BYTES_PER_LINE = 50


class BinaryFileError(Exception):
    """Raised when attempting to calculate SLOC for binary files."""
    pass


class InvalidEncodingError(Exception):
    """Raised when patch contains invalid UTF-8."""
    pass


@dataclass
class SLOCMetrics:
    """
    Dual SLOC metrics for a code change.

    Provides both traditional line-based metrics (GitHub-compatible) and
    byte-based metrics (Driver-compatible) from a single calculation.
    """
    # Traditional line-based metrics
    additions_lines: int
    deletions_lines: int
    net_lines: int  # additions - deletions
    churn_lines: int  # additions + deletions

    # Byte-based SLOC metrics
    addition_bytes: int
    deletion_bytes: int
    patch_bytes: int  # total bytes (addition_bytes + deletion_bytes)
    net_bytes: int  # addition_bytes - deletion_bytes
    sloc: int  # patch_bytes / BYTES_PER_LINE

    # Derived metrics
    bytes_per_line: float

    @property
    def is_empty(self) -> bool:
        """Check if this represents an empty change."""
        return self.churn_lines == 0 and self.patch_bytes == 0


class DualSLOCCalculator:
    """
    Calculate both line-based and byte-based SLOC metrics.

    This calculator processes git diffs to extract dual metrics:
    1. Line-based: Traditional SLOC (additions/deletions by line count)
    2. Byte-based: Driver SLOC (UTF-8 bytes / 50)

    Example:
        >>> calc = DualSLOCCalculator()
        >>> diff = "+def hello():\\n+    print('Hello')\\n-def old():\\n-    pass"
        >>> metrics = calc.from_git_diff(diff)
        >>> metrics.additions_lines
        2
        >>> metrics.sloc
        1
    """

    BYTES_PER_LINE = 50  # Driver standard

    # Binary file indicators
    BINARY_INDICATORS = [
        b'\\0',  # Null byte
        'Binary files',
        'GIT binary patch',
    ]

    @classmethod
    def from_git_diff(cls, diff_text: str, validate_encoding: bool = True) -> SLOCMetrics:
        """
        Calculate metrics from git diff output.

        Args:
            diff_text: Git diff string (unified diff format)
            validate_encoding: If True, validate UTF-8 encoding and raise on errors

        Returns:
            SLOCMetrics with dual metrics calculated

        Raises:
            BinaryFileError: If diff appears to contain binary content
            InvalidEncodingError: If validate_encoding=True and invalid UTF-8 found
        """
        # Check for binary content
        if cls._is_binary_diff(diff_text):
            raise BinaryFileError("Cannot calculate SLOC for binary files")

        if not diff_text or not diff_text.strip():
            return cls._empty_metrics()

        lines_added = 0
        lines_deleted = 0
        bytes_added = 0
        bytes_deleted = 0

        try:
            for line in diff_text.splitlines():
                # Skip diff metadata lines
                if line.startswith('+++') or line.startswith('---') or line.startswith('@@'):
                    continue

                # Process additions
                if line.startswith('+'):
                    lines_added += 1
                    # Count bytes excluding the '+' prefix
                    content = line[1:]
                    if validate_encoding:
                        try:
                            bytes_added += len(content.encode('utf-8'))
                        except UnicodeEncodeError as e:
                            raise InvalidEncodingError(f"Invalid UTF-8 in added line: {e}")
                    else:
                        # Use errors='replace' to handle invalid UTF-8
                        bytes_added += len(content.encode('utf-8', errors='replace'))

                # Process deletions
                elif line.startswith('-'):
                    lines_deleted += 1
                    content = line[1:]
                    if validate_encoding:
                        try:
                            bytes_deleted += len(content.encode('utf-8'))
                        except UnicodeEncodeError as e:
                            raise InvalidEncodingError(f"Invalid UTF-8 in deleted line: {e}")
                    else:
                        bytes_deleted += len(content.encode('utf-8', errors='replace'))

        except UnicodeDecodeError as e:
            if validate_encoding:
                raise InvalidEncodingError(f"Invalid UTF-8 in diff: {e}")
            # If not validating, try to process as best we can
            pass

        return cls._create_metrics(
            lines_added, lines_deleted,
            bytes_added, bytes_deleted
        )

    @classmethod
    def from_line_counts(cls, additions: int, deletions: int, patch: str | None = None) -> SLOCMetrics:
        """
        Calculate from line counts (GitHub API style) plus optional patch.

        This is useful when you have line counts from GitHub API but want to
        calculate byte-based metrics from the patch data.

        Args:
            additions: Number of lines added
            deletions: Number of lines deleted
            patch: Optional git diff patch for byte calculation

        Returns:
            SLOCMetrics with dual metrics
        """
        # Use provided line counts
        lines_added = additions
        lines_deleted = deletions

        # Calculate bytes from patch if provided
        if patch:
            bytes_added, bytes_deleted = cls._count_patch_bytes(patch)
        else:
            # Estimate bytes from line counts if no patch
            bytes_added = additions * cls.BYTES_PER_LINE
            bytes_deleted = deletions * cls.BYTES_PER_LINE

        return cls._create_metrics(
            lines_added, lines_deleted,
            bytes_added, bytes_deleted
        )

    @classmethod
    def from_batch(cls, diffs: list[str], validate_encoding: bool = False) -> list[SLOCMetrics]:
        """
        Calculate metrics for multiple diffs efficiently.

        Args:
            diffs: List of git diff strings
            validate_encoding: If True, validate UTF-8 (slower but safer)

        Returns:
            List of SLOCMetrics, one per diff

        Note:
            Validation is disabled by default for batch operations to improve
            performance. Binary files and encoding errors are handled gracefully.
        """
        results = []
        for diff in diffs:
            try:
                metrics = cls.from_git_diff(diff, validate_encoding=validate_encoding)
                results.append(metrics)
            except (BinaryFileError, InvalidEncodingError):
                # Skip problematic diffs, append empty metrics
                results.append(cls._empty_metrics())
        return results

    @staticmethod
    def _count_patch_bytes(patch: str) -> tuple[int, int]:
        """
        Count bytes in patch additions and deletions.

        Args:
            patch: Git diff patch string

        Returns:
            Tuple of (addition_bytes, deletion_bytes)
        """
        if not patch:
            return (0, 0)

        addition_bytes = 0
        deletion_bytes = 0

        for line in patch.splitlines():
            # Skip diff metadata
            if line.startswith('+++') or line.startswith('---') or line.startswith('@@'):
                continue

            # Count additions (exclude '+' prefix)
            if line.startswith('+'):
                try:
                    addition_bytes += len(line[1:].encode('utf-8', errors='replace'))
                except Exception:
                    # Fallback: estimate
                    addition_bytes += len(line[1:]) * 1

            # Count deletions (exclude '-' prefix)
            elif line.startswith('-'):
                try:
                    deletion_bytes += len(line[1:].encode('utf-8', errors='replace'))
                except Exception:
                    deletion_bytes += len(line[1:]) * 1

        return (addition_bytes, deletion_bytes)

    @staticmethod
    def _create_metrics(
        lines_added: int,
        lines_deleted: int,
        bytes_added: int,
        bytes_deleted: int
    ) -> SLOCMetrics:
        """
        Create SLOCMetrics from raw counts.

        Args:
            lines_added: Number of lines added
            lines_deleted: Number of lines deleted
            bytes_added: Bytes in additions
            bytes_deleted: Bytes in deletions

        Returns:
            Complete SLOCMetrics instance
        """
        # Line-based derived metrics
        net_lines = lines_added - lines_deleted
        churn_lines = lines_added + lines_deleted

        # Byte-based derived metrics
        patch_bytes = bytes_added + bytes_deleted
        net_bytes = bytes_added - bytes_deleted
        sloc = patch_bytes // DualSLOCCalculator.BYTES_PER_LINE

        # Calculate average bytes per line
        bytes_per_line = patch_bytes / churn_lines if churn_lines > 0 else 0.0

        return SLOCMetrics(
            additions_lines=lines_added,
            deletions_lines=lines_deleted,
            net_lines=net_lines,
            churn_lines=churn_lines,
            addition_bytes=bytes_added,
            deletion_bytes=bytes_deleted,
            patch_bytes=patch_bytes,
            net_bytes=net_bytes,
            sloc=sloc,
            bytes_per_line=bytes_per_line
        )

    @staticmethod
    def _empty_metrics() -> SLOCMetrics:
        """Return empty metrics for zero-change diffs."""
        return SLOCMetrics(
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

    @staticmethod
    def _is_binary_diff(diff_text: str) -> bool:
        """
        Check if diff appears to contain binary content.

        Args:
            diff_text: Diff string to check

        Returns:
            True if diff appears to be binary
        """
        # Check for binary indicators in text
        for indicator in DualSLOCCalculator.BINARY_INDICATORS:
            if isinstance(indicator, bytes):
                # Check if binary representation exists
                try:
                    if indicator.decode('unicode_escape') in diff_text:
                        return True
                except:
                    pass
            elif indicator in diff_text:
                return True

        return False


# Legacy functions for backward compatibility
def bytes_to_sloc(bytes_count: int) -> int:
    """
    Convert bytes to source lines of code.

    Uses python-backend's conversion factor of 50 bytes per line.

    Args:
        bytes_count: Total bytes in code changes

    Returns:
        Equivalent SLOC

    Example:
        >>> bytes_to_sloc(1000)
        20
        >>> bytes_to_sloc(75)
        1
        >>> bytes_to_sloc(-50)
        1
    """
    return abs(bytes_count) // BYTES_PER_LINE


def sloc_to_bytes(sloc: int) -> int:
    """
    Convert source lines of code to bytes.

    Args:
        sloc: Source lines of code

    Returns:
        Equivalent bytes

    Example:
        >>> sloc_to_bytes(20)
        1000
        >>> sloc_to_bytes(1)
        50
    """
    return sloc * BYTES_PER_LINE


def calculate_patch_bytes(patch: str | None) -> tuple[int, int, int]:
    """
    Calculate byte sizes of additions and deletions in a git diff patch.

    Args:
        patch: Git diff patch string from GitHub API

    Returns:
        Tuple of (addition_bytes, deletion_bytes, total_bytes)
    """
    addition_bytes, deletion_bytes = DualSLOCCalculator._count_patch_bytes(patch or "")
    total_bytes = addition_bytes + deletion_bytes
    return (addition_bytes, deletion_bytes, total_bytes)

