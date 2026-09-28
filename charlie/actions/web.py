"""Web search and URL opening action handlers for Charlie.

Loads site URL templates, URL-encodes search queries, and opens target URLs
in the default or specified browser.
"""

from __future__ import annotations

import subprocess
import urllib.parse
from typing import Optional
from charlie.config import get_config

BROWSER_ALIASES = {
    "chrome": "Google Chrome",
    "google chrome": "Google Chrome",
    "safari": "Safari",
    "firefox": "Firefox",
    "brave": "Brave Browser",
    "edge": "Microsoft Edge",
    "arc": "Arc",
}

DEFAULT_SITES = {
    "google": "https://www.google.com/search?q={query}",
    "amazon": "https://www.amazon.in/s?k={query}",
    "flipkart": "https://www.flipkart.com/search?q={query}",
    "youtube": "https://www.youtube.com/results?search_query={query}",
    "myntra": "https://www.myntra.com/{query}",
    "meesho": "https://www.meesho.com/search?q={query}",
}

HOMEPAGES = {
    "google": "https://www.google.com",
    "amazon": "https://www.amazon.in",
    "flipkart": "https://www.flipkart.com",
    "youtube": "https://www.youtube.com",
    "myntra": "https://www.myntra.com",
    "meesho": "https://www.meesho.com",
    "github": "https://github.com",
    "reddit": "https://www.reddit.com",
    "twitter": "https://twitter.com",
    "x": "https://x.com",
    "linkedin": "https://www.linkedin.com",
    "netflix": "https://www.netflix.com",
    "spotify": "https://open.spotify.com",
}


def resolve_browser(browser_name: Optional[str]) -> Optional[str]:
    """Resolve browser name or alias to the official macOS application name."""
    if not browser_name:
        cfg = get_config()
        browser_name = cfg.default_browser

    if not browser_name:
        return None

    clean = browser_name.strip().lower()
    return BROWSER_ALIASES.get(clean, browser_name.strip())


def build_search_url(query: str, site: str = "google") -> str:
    """Build a search URL for a given query and site."""
    cfg = get_config()
    sites = {**DEFAULT_SITES, **cfg.sites}

    site_key = site.lower().strip() if site else "google"
    template = sites.get(site_key, sites.get("google", DEFAULT_SITES["google"]))

    encoded_query = urllib.parse.quote_plus(query.strip())
    return template.format(query=encoded_query)


def open_browser_command(url: str, browser: Optional[str] = None) -> list[str]:
    """Build the subprocess command list to open a URL."""
    resolved_browser = resolve_browser(browser)
    if resolved_browser:
        return ["open", "-a", resolved_browser, url]
    return ["open", url]


def web_search(
    query: str,
    site: str = "google",
    browser: Optional[str] = None,
) -> tuple[bool, str]:
    """Execute a web search on the target site."""
    if not query or not query.strip():
        return False, "Search query cannot be empty."

    site_name = site.strip() if site else "google"
    url = build_search_url(query, site_name)
    cmd = open_browser_command(url, browser)

    try:
        res = subprocess.run(cmd, capture_output=True, text=True, check=False)
        if res.returncode == 0:
            display_site = site_name.capitalize()
            return True, f"Searching {display_site} for '{query}'."
        return False, f"Failed to open browser: {res.stderr.strip() or 'Unknown error'}"
    except Exception as e:
        return False, f"Failed to perform web search: {str(e)}"


def open_url(
    url: Optional[str] = None,
    site: Optional[str] = None,
    browser: Optional[str] = None,
) -> tuple[bool, str]:
    """Open a URL or a recognized site homepage."""
    target_url = None

    if url and url.strip():
        raw_url = url.strip()
        if not raw_url.startswith(("http://", "https://")):
            target_url = f"https://{raw_url}"
        else:
            target_url = raw_url
    elif site and site.strip():
        site_key = site.strip().lower()
        if site_key in HOMEPAGES:
            target_url = HOMEPAGES[site_key]
        else:
            target_url = f"https://www.{site_key}.com"

    if not target_url:
        return False, "No valid URL or site provided."

    cmd = open_browser_command(target_url, browser)
    try:
        res = subprocess.run(cmd, capture_output=True, text=True, check=False)
        if res.returncode == 0:
            return True, f"Opened {target_url}."
        return False, f"Failed to open URL: {res.stderr.strip() or 'Unknown error'}"
    except Exception as e:
        return False, f"Failed to open URL: {str(e)}"
