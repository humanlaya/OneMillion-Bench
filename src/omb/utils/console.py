"""
Rich console utilities for pretty printing and formatting.

Uses the Gruvbox color palette for consistent, beautiful terminal output.
"""

from typing import Any, Dict, Optional

from rich import box
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from .colors import RichColors

# Create global console instances
# stdout: for parseable output (tables, final results)
# stderr: for status, progress, decorative output, warnings, errors
console = Console()
err_console = Console(stderr=True)

# Quiet mode flag
_quiet = False


def set_quiet(quiet: bool) -> None:
    """Set quiet mode. When quiet, only errors and warnings are printed."""
    global _quiet
    _quiet = quiet


LOGO1 = r"""
 _____            ____
/\  __`\  /'\_/`\/\  _`\
\ \ \/\ \/\      \ \ \L\ \
 \ \ \ \ \ \ \__\ \ \  _ <'
  \ \ \_\ \ \ \_/\ \ \ \L\ \
   \ \_____\ \_\\ \_\ \____/
    \/_____/\/_/ \/_/\/___/
"""

LOGO2 = r"""
 _____                                 ___    ___
/\  __`\                  /'\_/`\  __ /\_ \  /\_ \    __
\ \ \/\ \    ___      __ /\      \/\_\\//\ \ \//\ \  /\_\    ___     ___
 \ \ \ \ \ /' _ `\  /'__`\ \ \__\ \/\ \ \ \ \  \ \ \ \/\ \  / __`\ /' _ `\
  \ \ \_\ \/\ \/\ \/\  __/\ \ \_/\ \ \ \ \_\ \_ \_\ \_\ \ \/\ \L\ \/\ \/\ \
   \ \_____\ \_\ \_\ \____\\ \_\\ \_\ \_\/\____\/\____\\ \_\ \____/\ \_\ \_\
    \/_____/\/_/\/_/\/____/ \/_/ \/_/\/_/\/____/\/____/ \/_/\/___/  \/_/\/_/


 ____                           __
/\  _`\                        /\ \
\ \ \L\ \     __    ___     ___\ \ \___
 \ \  _ <'  /'__`\/' _ `\  /'___\ \  _ `\
  \ \ \L\ \/\  __//\ \/\ \/\ \__/\ \ \ \ \
   \ \____/\ \____\ \_\ \_\ \____\\ \_\ \_\
    \/___/  \/____/\/_/\/_/\/____/ \/_/\/_/
"""


def print_logo(logo: str, color: str = None) -> None:
    """
    Print an ASCII art logo with color styling.

    Args:
        logo: ASCII art logo text
        color: Rich color string (defaults to Gruvbox orange)
    """
    if _quiet:
        return
    if color is None:
        color = RichColors.ORANGE

    # Create styled text for the entire logo
    logo_text = Text(logo, style=f"bold {color}")

    # Print with visual padding
    err_console.print()
    err_console.print(logo_text)
    err_console.print()


def print_header(title: str, subtitle: Optional[str] = None) -> None:
    """
    Print a fancy header with title and optional subtitle.

    Args:
        title: Main title text
        subtitle: Optional subtitle text
    """
    if _quiet:
        return
    text = Text(title, style=RichColors.HEADER)
    if subtitle:
        text.append("\n" + subtitle, style=RichColors.DIM)

    panel = Panel(
        text,
        box=box.DOUBLE,
        border_style=RichColors.HEADER_BORDER,
        padding=(1, 2),
    )
    err_console.print(panel)


def print_section(title: str, style: str = None) -> None:
    """
    Print a section header.

    Args:
        title: Section title
        style: Rich style string (defaults to Gruvbox orange)
    """
    if _quiet:
        return
    if style is None:
        style = RichColors.SECTION
    err_console.rule(f"[{style}]{title}[/{style}]", style=style)


def print_success(message: str, prefix: str = "✓") -> None:
    """
    Print a success message in green.

    Args:
        message: Success message
        prefix: Prefix character/emoji
    """
    if _quiet:
        return
    err_console.print(f"{prefix} [{RichColors.SUCCESS}]{message}[/{RichColors.SUCCESS}]")


def print_warning(message: str, prefix: str = "⚠️") -> None:
    """
    Print a warning message in yellow.

    Args:
        message: Warning message
        prefix: Prefix character/emoji
    """
    err_console.print(f"{prefix} [{RichColors.WARNING}]{message}[/{RichColors.WARNING}]")


def print_error(message: str, prefix: str = "❌") -> None:
    """
    Print an error message in red.

    Args:
        message: Error message
        prefix: Prefix character/emoji
    """
    err_console.print(f"{prefix} [{RichColors.ERROR}]{message}[/{RichColors.ERROR}]")


def print_info(message: str, prefix: str = "ℹ️") -> None:
    """
    Print an informational message in blue.

    Args:
        message: Info message
        prefix: Prefix character/emoji
    """
    if _quiet:
        return
    err_console.print(f"{prefix} [{RichColors.INFO}]{message}[/{RichColors.INFO}]")


def create_config_table(config_data: Dict[str, Any]) -> Table:
    """
    Create a configuration table.

    Args:
        config_data: Dictionary of configuration key-value pairs

    Returns:
        Rich Table object
    """
    table = Table(
        title="Configuration",
        box=box.ROUNDED,
        show_header=True,
        header_style=f"bold {RichColors.MAGENTA}",
        border_style=RichColors.HEADER_BORDER,
    )

    table.add_column("Setting", style=RichColors.CYAN, no_wrap=True)
    table.add_column("Assignment", style=RichColors.GREEN)

    for key, value in config_data.items():
        table.add_row(str(key), str(value))

    return table


def create_cost_breakdown_table(
    cost_breakdown: Dict[str, Dict[str, Any]],
    total_tokens: Dict[str, int],
    total_cost: float,
) -> Table:
    """
    Create a cost breakdown table.

    Args:
        cost_breakdown: Dictionary of model cost breakdowns
        total_tokens: Dictionary with total token counts
        total_cost: Total cost in USD

    Returns:
        Rich Table object
    """
    table = Table(
        title="💰 Model Cost Breakdown",
        box=box.ROUNDED,
        show_header=True,
        header_style=f"bold {RichColors.MAGENTA}",
        border_style=RichColors.HEADER_BORDER,
        show_footer=True,
    )

    table.add_column("Model Name", style=RichColors.CYAN, no_wrap=True, footer="[bold]Total[/bold]")
    table.add_column(
        "Input Tokens",
        justify="right",
        style=RichColors.GREEN,
        footer=f"[bold]{total_tokens['prompt_tokens']:,}[/bold]",
    )
    table.add_column(
        "Output Tokens",
        justify="right",
        style=RichColors.YELLOW,
        footer=f"[bold]{total_tokens['completion_tokens']:,}[/bold]",
    )
    table.add_column(
        "Cost (USD)",
        justify="right",
        style=RichColors.RED,
        footer=f"[bold]${total_cost:.4f}[/bold]",
    )

    for model_name, breakdown in sorted(cost_breakdown.items()):
        table.add_row(
            model_name,
            f"{breakdown['prompt_tokens']:,}",
            f"{breakdown['completion_tokens']:,}",
            f"${breakdown['total_cost']:.4f}",
        )

    return table


def create_summary_table(summary_data: Dict[str, Any]) -> Table:
    """
    Create a summary statistics table.

    Args:
        summary_data: Dictionary of summary statistics

    Returns:
        Rich Table object
    """
    table = Table(
        title="📊 Processing Summary",
        box=box.ROUNDED,
        show_header=False,
        border_style=RichColors.HEADER_BORDER,
        padding=(0, 2),
    )

    table.add_column("Metric", style=RichColors.CYAN, no_wrap=True)
    table.add_column("Assignment", style=f"bold {RichColors.GREEN}")

    for key, value in summary_data.items():
        table.add_row(key, str(value))

    return table


def create_performance_table(performance_data: Dict[str, Any]) -> Table:
    """
    Create an overall performance statistics table with models as columns.

    Args:
        performance_data: Dictionary containing:
            - 'models': List of model names
            - 'metrics': Dict mapping metric names to dict of model_name: value

    Returns:
        Rich Table object
    """
    table = Table(
        title="🎯 Overall Performance",
        box=box.DOUBLE,
        show_header=True,
        header_style=f"bold {RichColors.MAGENTA}",
        border_style=RichColors.HEADER_BORDER,
        padding=(0, 1),
    )

    models = performance_data.get("models", [])
    metrics = performance_data.get("metrics", {})

    # First column for metric names
    table.add_column("Metric", style=RichColors.CYAN, no_wrap=True, width=25)

    # Add columns for each model
    for model in models:
        table.add_column(model, style=f"bold {RichColors.GREEN}", justify="right", width=15)

    # Add rows for each metric
    for metric_name, model_values in metrics.items():
        row_data = [metric_name]

        for model in models:
            value = model_values.get(model, "N/A")

            # Apply color formatting based on metric type
            if isinstance(value, str) and "%" in value:
                try:
                    rate = float(value.rstrip("%"))
                    if "Consistency" in metric_name:
                        if rate >= 80:
                            formatted_value = f"[{RichColors.GREEN}]{value}[/{RichColors.GREEN}]"
                        elif rate >= 60:
                            formatted_value = f"[{RichColors.YELLOW}]{value}[/{RichColors.YELLOW}]"
                        else:
                            formatted_value = f"[{RichColors.RED}]{value}[/{RichColors.RED}]"
                    elif "Average" in metric_name or "Score" in metric_name:
                        formatted_value = f"[{RichColors.AQUA}]{value}[/{RichColors.AQUA}]"
                    else:
                        formatted_value = value
                except (ValueError, AttributeError):
                    formatted_value = str(value)
            else:
                formatted_value = str(value)

            row_data.append(formatted_value)

        table.add_row(*row_data)

    return table


def create_metadata_table(
    metadata: Dict[str, Dict[str, Any]],
    all_models: list,
    fallback_max_tokens: int,
) -> Table:
    """Create a Rich table displaying detected model metadata.

    Args:
        metadata: Dict mapping model_id to {context_length, max_completion_tokens}
        all_models: All model IDs that were queried
        fallback_max_tokens: The global MAX_TOKENS fallback value

    Returns:
        Rich Table object
    """
    table = Table(
        title="🔍 Detected Model Metadata",
        box=box.ROUNDED,
        show_header=True,
        header_style=f"bold {RichColors.MAGENTA}",
        border_style=RichColors.HEADER_BORDER,
        title_style=f"bold {RichColors.ORANGE}",
    )

    table.add_column("#", style=RichColors.DIM, justify="right", width=4)
    table.add_column("Model", style=RichColors.CYAN, no_wrap=True)
    table.add_column("Context Length", style=RichColors.GREEN, justify="right")
    table.add_column("Max Completion Tokens", style=RichColors.YELLOW, justify="right")
    table.add_column("Status", style=RichColors.DIM, justify="center")

    for idx, model_id in enumerate(sorted(all_models), 1):
        if model_id in metadata:
            info = metadata[model_id]
            ctx = info.get("context_length")
            mct = info.get("max_completion_tokens")
            ctx_str = f"{ctx:,}" if ctx is not None else "N/A"
            mct_str = f"{mct:,}" if mct is not None else f"{fallback_max_tokens:,} (fallback)"
            status = f"[{RichColors.GREEN}]✓[/{RichColors.GREEN}]"
        else:
            ctx_str = "N/A"
            mct_str = f"{fallback_max_tokens:,} (fallback)"
            status = f"[{RichColors.YELLOW}]✗[/{RichColors.YELLOW}]"

        table.add_row(str(idx), model_id, ctx_str, mct_str, status)

    return table


def print_debug_question(file_name: str, prompt: str, model_name: str = None) -> None:
    """
    Print a formatted question for debug mode with Gruvbox styling.

    Args:
        file_name: Name of the file being processed
        prompt: The question/prompt text
        model_name: Optional model name for context
    """
    err_console.print()
    err_console.rule(
        f"[{RichColors.ORANGE}]🔍 DEBUG: Question[/{RichColors.ORANGE}]",
        style=RichColors.ORANGE,
    )
    err_console.print()

    # File info
    err_console.print(
        f"[{RichColors.MAGENTA}]📄 Question:[/{RichColors.MAGENTA}] [{RichColors.YELLOW}]{file_name}[/{RichColors.YELLOW}]"
    )

    # Model info (if provided)
    if model_name:
        err_console.print(
            f"[{RichColors.MAGENTA}]🤖 Agent:[/{RichColors.MAGENTA}] [{RichColors.YELLOW}]{model_name}[/{RichColors.YELLOW}]"
        )

    err_console.print()

    # Question content in a panel
    question_panel = Panel(
        Text(prompt, style=RichColors.CYAN),
        title=f"[{RichColors.ORANGE}]Question Prompt[/{RichColors.ORANGE}]",
        border_style=RichColors.ORANGE,
        box=box.ROUNDED,
        padding=(1, 2),
    )
    err_console.print(question_panel)
    err_console.print()


def print_debug_response(
    file_name: str,
    response: str,
    model_name: str,
    response_type: str = "Generation",
    token_usage: Optional[Dict[str, int]] = None,
) -> None:
    """
    Print a formatted response for debug mode with Gruvbox styling.

    Args:
        file_name: Name of the file being processed
        response: The response text
        model_name: Model name that generated the response
        response_type: Type of response (e.g., "Generation", "Grading")
        token_usage: Optional dict with 'prompt_tokens', 'completion_tokens', 'total_tokens'
    """
    err_console.print()
    err_console.rule(
        f"[{RichColors.GREEN}]✨ DEBUG: {response_type} Response[/{RichColors.GREEN}]",
        style=RichColors.GREEN,
    )
    err_console.print()

    # File and model info
    err_console.print(
        f"[{RichColors.MAGENTA}]📄 Question:[/{RichColors.MAGENTA}] [{RichColors.YELLOW}]{file_name}[/{RichColors.YELLOW}]"
    )
    err_console.print(
        f"[{RichColors.MAGENTA}]🤖 Agent:[/{RichColors.MAGENTA}] [{RichColors.YELLOW}]{model_name}[/{RichColors.YELLOW}]"
    )

    # Display token counts if available, otherwise fall back to character/word counts
    if token_usage:
        prompt_tokens = token_usage.get("prompt_tokens", 0)
        completion_tokens = token_usage.get("completion_tokens", 0)
        total_tokens = token_usage.get("total_tokens", prompt_tokens + completion_tokens)
        err_console.print(
            f"[{RichColors.MAGENTA}]📊 Tokens:[/{RichColors.MAGENTA}] "
            f"[{RichColors.CYAN}]Input: {prompt_tokens:,} | "
            f"Output: {completion_tokens:,} | "
            f"Total: {total_tokens:,}[/{RichColors.CYAN}]"
        )
    else:
        # Fallback to character and word count
        err_console.print(
            f"[{RichColors.MAGENTA}]📊 Length:[/{RichColors.MAGENTA}] [{RichColors.CYAN}]{len(response)} chars, {len(response.split())} words[/{RichColors.CYAN}]"
        )

    err_console.print()

    # Response content in a panel
    response_panel = Panel(
        Text(response, style=RichColors.GREEN),
        title=f"[{RichColors.GREEN}]{response_type}[/{RichColors.GREEN}]",
        border_style=RichColors.GREEN,
        box=box.ROUNDED,
        padding=(1, 2),
    )
    err_console.print(response_panel)
    err_console.print()
