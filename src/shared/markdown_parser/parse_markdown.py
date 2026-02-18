import re
from dataclasses import dataclass


@dataclass
class Section:
    title: str
    content: str
    has_table: bool
    has_list: bool
    language: str  # "en" or "fr" — detected or set manually

    @classmethod
    def from_content(cls, title: str, content: str, language: str = "en") -> "Section":
        """Create a Section with auto-detected has_table and has_list."""
        return cls(
            title=title,
            content=content,
            has_table="|" in content and "---" in content,
            has_list=bool(re.search(r"^\s*[-*\d]+[.)]\s", content, re.M)),
            language=language,
        )


def parse_markdown(text: str, default_lang: str = "en") -> list[Section]:
    """Split markdown by ## headers, detect structural elements."""
    sections = []
    current_title = "Introduction"
    current_lines = []

    for line in text.split("\n"):
        if line.startswith("## "):
            if current_lines:
                content = "\n".join(current_lines)
                sections.append(
                    Section(
                        title=current_title,
                        content=content,
                        has_table="|" in content and "---" in content,
                        has_list=bool(
                            re.search(r"^\s*[-*\d]+[.)]\s", content, re.M)
                        ),
                        language=default_lang,
                    )
                )
            current_title = line.lstrip("#").strip()
            current_lines = []
        else:
            current_lines.append(line)

    if current_lines:
        content = "\n".join(current_lines)
        sections.append(
            Section(
                title=current_title,
                content=content,
                has_table="|" in content and "---" in content,
                has_list=bool(re.search(r"^\s*[-*\d]+[.)]\s", content, re.M)),
                language=default_lang,
            )
        )

    return sections
