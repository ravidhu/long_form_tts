"""Fetch a webpage and extract its main content as Markdown via trafilatura."""

import trafilatura


def fetch_url_content(url: str) -> str:
    """Download *url* and return the main content as Markdown.

    Raises ``RuntimeError`` if the page cannot be fetched or yields no
    extractable content.
    """
    downloaded = trafilatura.fetch_url(url)
    if downloaded is None:
        raise RuntimeError(f"Failed to fetch URL: {url}")

    text = trafilatura.extract(
        downloaded,
        output_format="markdown",
        include_links=False,
        include_images=False,
        include_formatting=True,
        include_tables=True,
    )
    if not text:
        raise RuntimeError(f"No extractable content found at: {url}")

    return text
