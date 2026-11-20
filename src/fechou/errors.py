"""Domain exceptions. Messages are user-facing, so they are written in pt-BR."""


class FechouError(Exception):
    """Base class for expected, user-facing errors."""


class ConfigError(FechouError):
    """The configuration file is missing or invalid."""


class SourceError(FechouError):
    """The data source could not be read."""


class SchemaError(FechouError):
    """The data source does not have the expected columns."""
