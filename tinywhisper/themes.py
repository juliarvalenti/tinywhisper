"""Built-in waveform themes inspired by popular coding color schemes."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class Theme:
    label: str
    color: str  # solid bar color (used when gradient is off)
    bg_color: str
    gradient_colors: list[str] = field(default_factory=list)  # left-to-right
    opacity: float = 0.90


# Ordered dict of built-in themes.  Keys are config identifiers.
THEMES: dict[str, Theme] = {
    "dracula": Theme(
        label="Dracula",
        color="#BD93F9",
        bg_color="#282A36",
        gradient_colors=["#FF79C6", "#BD93F9", "#8BE9FD"],
    ),
    "monokai": Theme(
        label="Monokai",
        color="#A6E22E",
        bg_color="#272822",
        gradient_colors=["#A6E22E", "#E6DB74", "#FD971F"],
    ),
    "tokyo-night": Theme(
        label="Tokyo Night",
        color="#7AA2F7",
        bg_color="#1A1B26",
        gradient_colors=["#7AA2F7", "#BB9AF7"],
    ),
    "catppuccin": Theme(
        label="Catppuccin Mocha",
        color="#CBA6F7",
        bg_color="#1E1E2E",
        gradient_colors=["#F5C2E7", "#CBA6F7", "#89B4FA"],
    ),
    "gruvbox": Theme(
        label="Gruvbox",
        color="#FE8019",
        bg_color="#282828",
        gradient_colors=["#FB4934", "#FE8019", "#FABD2F", "#8EC07C"],
    ),
    "nord": Theme(
        label="Nord",
        color="#88C0D0",
        bg_color="#2E3440",
        gradient_colors=["#5E81AC", "#81A1C1", "#88C0D0", "#8FBCBB"],
    ),
    "solarized": Theme(
        label="Solarized Dark",
        color="#2AA198",
        bg_color="#002B36",
        gradient_colors=["#2AA198", "#859900"],
    ),
    "one-dark": Theme(
        label="One Dark",
        color="#61AFEF",
        bg_color="#282C34",
        gradient_colors=["#61AFEF", "#C678DD"],
    ),
    "cyberpunk": Theme(
        label="Cyberpunk",
        color="#FF2079",
        bg_color="#0D0221",
        gradient_colors=["#FF2079", "#F222FF", "#00FFF1"],
        opacity=0.92,
    ),
    "matrix": Theme(
        label="Matrix",
        color="#00FF41",
        bg_color="#0A0A0A",
        gradient_colors=["#003B00", "#00FF41"],
        opacity=0.92,
    ),
    "synthwave": Theme(
        label="Synthwave '84",
        color="#F97E72",
        bg_color="#2B213A",
        gradient_colors=["#F97E72", "#FF7EDB", "#36F9F6"],
    ),
    "rose-pine": Theme(
        label="Rose Pine",
        color="#EBBCBA",
        bg_color="#191724",
        gradient_colors=["#EBBCBA", "#F6C177", "#C4A7E7"],
    ),
    "kanagawa": Theme(
        label="Kanagawa",
        color="#7E9CD8",
        bg_color="#1F1F28",
        gradient_colors=["#7E9CD8", "#957FB8", "#D27E99"],
    ),
    "everforest": Theme(
        label="Everforest",
        color="#A7C080",
        bg_color="#2D353B",
        gradient_colors=["#83C092", "#A7C080", "#DBBC7F"],
    ),
    "github-dark": Theme(
        label="GitHub Dark",
        color="#58A6FF",
        bg_color="#0D1117",
        gradient_colors=["#58A6FF", "#3FB950"],
    ),
}

# Display order for UI
THEME_ORDER: list[str] = list(THEMES.keys())
