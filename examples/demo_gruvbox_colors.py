#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Demo script to showcase gruvbox medium color palette."""

import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from omb.utils import (
    colorize,
    colorize_bg,
    colorize_bold,
    print_error,
    print_header,
    print_info,
    print_progress,
    print_success,
    print_warning,
)
from omb.utils.colors import (
    GRUVBOX_AQUA,
    GRUVBOX_BLUE,
    GRUVBOX_FG1,
    GRUVBOX_FG2,
    GRUVBOX_GRAY,
    GRUVBOX_GREEN,
    GRUVBOX_ORANGE,
    GRUVBOX_PURPLE,
    GRUVBOX_RED,
    GRUVBOX_YELLOW,
)


def main():
    """Demonstrate gruvbox color palette."""
    print_header("Gruvbox Medium Color Palette Demo")

    # Basic log messages
    print("\n" + colorize_bold("Log Messages:", GRUVBOX_FG1))
    print_success("Operation completed successfully")
    print_info("Processing data...")
    print_warning("This is a warning message")
    print_error("An error occurred")

    # Progress messages
    print("\n" + colorize_bold("Progress Messages:", GRUVBOX_FG1))
    print_progress(1, 3, "✓", "task1.json", "gpt-4", "Score: 85")
    print_progress(2, 3, "✓", "task2.json", "claude-3", "Score: 92")
    print_progress(3, 3, "✗", "task3.json", "gemini", "Failed to parse")

    # Color palette showcase
    print("\n" + colorize_bold("Gruvbox Color Palette:", GRUVBOX_FG1))
    colors = [
        ("Red", GRUVBOX_RED),
        ("Green", GRUVBOX_GREEN),
        ("Yellow", GRUVBOX_YELLOW),
        ("Blue", GRUVBOX_BLUE),
        ("Purple", GRUVBOX_PURPLE),
        ("Aqua", GRUVBOX_AQUA),
        ("Orange", GRUVBOX_ORANGE),
        ("Gray", GRUVBOX_GRAY),
    ]

    for name, color in colors:
        print(f"  {colorize(name, color)}: {colorize_bold('Bold text', color)}")

    # Text styles
    print("\n" + colorize_bold("Text Styles:", GRUVBOX_FG1))
    print(f"  Normal: {colorize('This is normal text', GRUVBOX_FG2)}")
    print(f"  Bold: {colorize_bold('This is bold text', GRUVBOX_GREEN)}")
    print(f"  Muted: {colorize('This is muted text', GRUVBOX_GRAY)}")

    print("\n" + colorize("=" * 80, GRUVBOX_YELLOW))
    print(colorize_bold("Gruvbox Medium theme applied successfully!", GRUVBOX_GREEN))
    print(colorize("=" * 80, GRUVBOX_YELLOW))


if __name__ == "__main__":
    main()
