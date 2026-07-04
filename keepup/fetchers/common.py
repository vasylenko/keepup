"""Shared HTTP settings for all fetchers."""

# Some sources (e.g. anthropic.com) refuse default python-requests UAs.
CHROME_UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/137.0.0.0 Safari/537.36"
)
TIMEOUT = 30  # seconds; a slow source must not stall the whole run
