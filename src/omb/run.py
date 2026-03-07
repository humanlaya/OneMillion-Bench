"""Bridge between CLI args and orchestrator entry point."""

import os
import sys


def run_task(args):
    """Run the eval task by delegating to orchestrator.main with parsed args."""
    from omb.orchestrator import main
    from omb.utils import console, err_console

    # Handle --no-color
    if getattr(args, "no_color", False) or os.environ.get("NO_COLOR"):
        console.no_color = True
        err_console.no_color = True

    # Handle --quiet
    if getattr(args, "quiet", False):
        from omb.utils.console import set_quiet

        set_quiet(True)

    debug = getattr(args, "debug", False) or getattr(args, "verbose", False)

    exit_code = main(
        config_path=getattr(args, "config", None),
        dataset=getattr(args, "dataset", None),
        debug=debug,
        limit=getattr(args, "limit", None),
        overwrite=getattr(args, "overwrite", False),
        grade_only=getattr(args, "grade_only", False),
        enable_search=getattr(args, "enable_search", False),
        recursive=getattr(args, "recursive", False),
        detect_metadata=getattr(args, "detect_metadata", False),
        sample_k=getattr(args, "sample_k", None),
        repeated_judge=getattr(args, "repeated_judge", None),
        _from_cli=True,
    )

    sys.exit(exit_code)
