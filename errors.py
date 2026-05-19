class PipelineError(Exception):
    """Base class for operational pipeline failures."""


class ParseFailure(PipelineError):
    """Raised when parsing an input BibTeX file fails."""


class LookupFailure(PipelineError):
    """Raised when upstream lookup operations fail irrecoverably."""


class WriteFailure(PipelineError):
    """Raised when writing output artifacts fails."""
