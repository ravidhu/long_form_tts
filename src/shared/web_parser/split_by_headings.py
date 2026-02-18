"""Split extracted Markdown into sections by heading level."""

import re
from dataclasses import dataclass


@dataclass
class WebSection:
    """A section of web content, analogous to pdf_parser.TOCSection."""

    title: str
    content: str  # markdown body (without the heading line itself)


def split_by_headings(
    markdown: str,
    max_level: int = 2,
) -> list[WebSection]:
    """Split *markdown* into sections at headings up to *max_level*.

    ``max_level=1`` splits on ``#`` only, ``max_level=2`` splits on
    ``#`` and ``##``, etc.

    If no headings are found the entire text is returned as a single
    section titled "Full article".
    """
    # Pattern: line starting with 1..max_level '#' characters followed by space
    pattern = re.compile(
        rf"^(#{{1,{max_level}}})\s+(.+)$", re.MULTILINE
    )

    matches = list(pattern.finditer(markdown))

    if not matches:
        return [WebSection(title="Full article", content=markdown.strip())]

    sections: list[WebSection] = []

    # Text before the first heading (preamble)
    preamble = markdown[: matches[0].start()].strip()
    if preamble:
        sections.append(WebSection(title="Introduction", content=preamble))

    for i, match in enumerate(matches):
        title = match.group(2).strip()
        start = match.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(markdown)
        body = markdown[start:end].strip()
        if body:
            sections.append(WebSection(title=title, content=body))

    return sections
