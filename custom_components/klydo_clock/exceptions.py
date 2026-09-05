"""Sanitized errors; never include raw ADB responses."""


class KlydoError(Exception):
    """Base integration error."""


class KlydoConnectionError(KlydoError):
    """Transport unavailable."""


class KlydoTimeoutError(KlydoConnectionError):
    """Transport deadline exceeded."""


class KlydoAuthenticationError(KlydoError):
    """Device requires unsupported authentication."""


class KlydoUnsupportedError(KlydoError):
    """Not a supported stock clock."""


class KlydoResponseError(KlydoError):
    """Required response missing or invalid."""
