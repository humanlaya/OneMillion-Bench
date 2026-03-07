"""
Gruvbox color palette constants for consistent theming.

This module provides manually curated Gruvbox colors for both
terminal output (Rich library) and Excel reports.
"""

# Gruvbox Dark Palette
# Background colors
GRUVBOX_BG_DARK = "#282828"  # dark0_hard
GRUVBOX_BG = "#32302f"  # dark0
GRUVBOX_BG_LIGHT = "#3c3836"  # dark1
GRUVBOX_BG_LIGHTER = "#504945"  # dark2

# Foreground colors
GRUVBOX_FG = "#ebdbb2"  # light1
GRUVBOX_FG_DIM = "#d5c4a1"  # light2
GRUVBOX_FG_DIMMER = "#bdae93"  # light3

# Accent colors (bright variants)
GRUVBOX_RED = "#fb4934"  # bright red
GRUVBOX_GREEN = "#b8bb26"  # bright green
GRUVBOX_YELLOW = "#fabd2f"  # bright yellow
GRUVBOX_BLUE = "#83a598"  # bright blue
GRUVBOX_PURPLE = "#d3869b"  # bright purple
GRUVBOX_AQUA = "#8ec07c"  # bright aqua
GRUVBOX_ORANGE = "#fe8019"  # bright orange

# Accent colors (dark variants for backgrounds)
GRUVBOX_RED_DARK = "#cc241d"
GRUVBOX_GREEN_DARK = "#98971a"
GRUVBOX_YELLOW_DARK = "#d79921"
GRUVBOX_BLUE_DARK = "#458588"
GRUVBOX_PURPLE_DARK = "#b16286"
GRUVBOX_AQUA_DARK = "#689d6a"
GRUVBOX_ORANGE_DARK = "#d65d0e"

# Gray tones
GRUVBOX_GRAY = "#928374"
GRUVBOX_GRAY_DARK = "#665c54"  # dark3


# Rich terminal color names (mapped to Gruvbox)
class RichColors:
    """Rich library color names using Gruvbox palette."""

    # Primary text colors
    CYAN = f"#{GRUVBOX_AQUA.lstrip('#')}"
    BLUE = f"#{GRUVBOX_BLUE.lstrip('#')}"
    GREEN = f"#{GRUVBOX_GREEN.lstrip('#')}"
    YELLOW = f"#{GRUVBOX_YELLOW.lstrip('#')}"
    RED = f"#{GRUVBOX_RED.lstrip('#')}"
    MAGENTA = f"#{GRUVBOX_PURPLE.lstrip('#')}"
    ORANGE = f"#{GRUVBOX_ORANGE.lstrip('#')}"

    # Dimmed variants
    DIM = f"#{GRUVBOX_FG_DIM.lstrip('#')}"

    # Named styles for Rich
    HEADER = f"bold {GRUVBOX_AQUA}"
    HEADER_BORDER = GRUVBOX_BLUE
    SUCCESS = f"bold {GRUVBOX_GREEN}"
    WARNING = f"bold {GRUVBOX_YELLOW}"
    ERROR = f"bold {GRUVBOX_RED}"
    INFO = GRUVBOX_AQUA
    SECTION = f"bold {GRUVBOX_ORANGE}"


# Excel hex colors (without # prefix)
class ExcelColors:
    """Excel color codes using Gruvbox palette (hex without #)."""

    # Headers and important sections
    HEADER_PRIMARY = GRUVBOX_BLUE_DARK.lstrip("#")  # 458588
    HEADER_SUCCESS = GRUVBOX_GREEN_DARK.lstrip("#")  # 98971a
    HEADER_WARNING = GRUVBOX_YELLOW_DARK.lstrip("#")  # d79921
    HEADER_ERROR = GRUVBOX_RED_DARK.lstrip("#")  # cc241d
    HEADER_COST = GRUVBOX_ORANGE_DARK.lstrip("#")  # d65d0e

    # Text colors (for white text on colored backgrounds)
    TEXT_ON_DARK = GRUVBOX_FG.lstrip("#")  # ebdbb2

    # Background fills
    BG_TOTAL_ROW = GRUVBOX_BG_LIGHTER.lstrip("#")  # 504945
    BG_ALTERNATING = GRUVBOX_BG_LIGHT.lstrip("#")  # 3c3836

    # Cell colors
    CELL_CYAN = GRUVBOX_AQUA_DARK.lstrip("#")
    CELL_GREEN = GRUVBOX_GREEN_DARK.lstrip("#")
    CELL_YELLOW = GRUVBOX_YELLOW_DARK.lstrip("#")
    CELL_RED = GRUVBOX_RED_DARK.lstrip("#")
    CELL_BLUE = GRUVBOX_BLUE_DARK.lstrip("#")
    CELL_ORANGE = GRUVBOX_ORANGE_DARK.lstrip("#")

    # Background colors (without # prefix, for reporting module)
    BG0_HARD = "1d2021"
    BG0 = GRUVBOX_BG_DARK.lstrip("#")
    BG1 = GRUVBOX_BG_LIGHT.lstrip("#")
    BG2 = GRUVBOX_BG_LIGHTER.lstrip("#")
    BG3 = GRUVBOX_GRAY_DARK.lstrip("#")
    BG4 = "7c6f64"

    # Foreground colors (without # prefix, for reporting module)
    FG0 = "fbf1c7"
    FG1 = GRUVBOX_FG.lstrip("#")
    FG2 = GRUVBOX_FG_DIM.lstrip("#")
    FG3 = GRUVBOX_FG_DIMMER.lstrip("#")
    FG4 = "a89984"

    # Bright accent colors (without # prefix, for reporting module)
    RED = GRUVBOX_RED.lstrip("#")
    GREEN = GRUVBOX_GREEN.lstrip("#")
    YELLOW = GRUVBOX_YELLOW.lstrip("#")
    BLUE = GRUVBOX_BLUE.lstrip("#")
    PURPLE = GRUVBOX_PURPLE.lstrip("#")
    AQUA = GRUVBOX_AQUA.lstrip("#")
    ORANGE = GRUVBOX_ORANGE.lstrip("#")
    GRAY = GRUVBOX_GRAY.lstrip("#")

    # Neutral accent colors (without # prefix, for reporting module)
    RED_NEUTRAL = GRUVBOX_RED_DARK.lstrip("#")
    GREEN_NEUTRAL = GRUVBOX_GREEN_DARK.lstrip("#")
    YELLOW_NEUTRAL = GRUVBOX_YELLOW_DARK.lstrip("#")
    BLUE_NEUTRAL = GRUVBOX_BLUE_DARK.lstrip("#")
    PURPLE_NEUTRAL = GRUVBOX_PURPLE_DARK.lstrip("#")
    AQUA_NEUTRAL = GRUVBOX_AQUA_DARK.lstrip("#")
    ORANGE_NEUTRAL = GRUVBOX_ORANGE_DARK.lstrip("#")
