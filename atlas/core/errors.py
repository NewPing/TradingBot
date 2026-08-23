"""Domain exception hierarchy for ATLAS."""


class AtlasError(Exception):
    """Base exception for all ATLAS errors."""


class LookaheadError(AtlasError):
    """Raised when an operation attempts to access future market data."""


class MoneyTypeError(AtlasError, TypeError):
    """Raised when an illegal type (e.g. float) is used in monetary arithmetic."""


class CurrencyMismatchError(AtlasError, ValueError):
    """Raised when arithmetic is attempted between Money of different currencies."""


class KillSwitchTriggeredError(AtlasError):
    """Raised when a system or risk kill switch triggers execution halt."""


class OrderValidationError(AtlasError, ValueError):
    """Raised when an order fails risk or domain validation."""


class ConfigurationError(AtlasError, ValueError):
    """Raised on invalid system configuration or security violation."""


class DataError(AtlasError):
    """Base exception for all data retrieval, parsing, or provider errors."""


class DataHealthError(DataError):
    """Raised on critical data validation or integrity failures."""


class InsufficientConfidenceError(AtlasError):
    """Raised when signal aggregation confidence is below required threshold."""


class SpecImmutabilityError(AtlasError):
    """Raised when an operation attempts to mutate an immutable strategy specification referenced by runs."""


class StrategyVersionNotFoundError(AtlasError, KeyError):
    """Raised when a requested strategy version cannot be found."""


class RunNotFoundError(AtlasError, KeyError):
    """Raised when a requested backtest/paper/live execution run cannot be found."""
