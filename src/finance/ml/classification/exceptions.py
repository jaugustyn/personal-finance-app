"""Domain exceptions for category-classification workflows."""
from __future__ import annotations


class ClassificationError(ValueError):
    """Base class for category-classification errors."""


class NoLabelledRows(ClassificationError):
    """Raised when evaluation receives no usable category labels."""


class InsufficientClassSupport(ClassificationError):
    """Raised when labels are present but cannot support the requested operation."""


class UnknownEstimator(ClassificationError):
    """Raised when a caller requests an estimator outside the registry."""


class UnknownFeatureSet(ClassificationError):
    """Raised when a caller requests an unsupported feature set."""
