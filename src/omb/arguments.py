"""CLI argument definitions for omb eval subcommand."""

import argparse


def add_argument(parser: argparse.ArgumentParser):
    """Add arguments for the eval subcommand."""
    parser.add_argument(
        "--dataset",
        dest="dataset",
        metavar="PATH",
        type=str,
        help="path to test directory or single JSON file",
    )
    parser.add_argument(
        "--config",
        metavar="FILE",
        type=str,
        help="path to YAML configuration file (default: built-in config)",
    )

    verbosity = parser.add_mutually_exclusive_group()
    verbosity.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="show detailed output including debug info",
    )
    verbosity.add_argument(
        "--quiet",
        "-q",
        action="store_true",
        help="suppress all output except errors and final results",
    )

    parser.add_argument(
        "--debug",
        action="store_true",
        help=argparse.SUPPRESS,
    )
    parser.add_argument(
        "--no-color",
        dest="no_color",
        action="store_true",
        help="disable colored output",
    )
    parser.add_argument(
        "--enable-search",
        dest="enable_search",
        action="store_true",
        help="enable web search augmentation for generator models",
    )
    parser.add_argument(
        "--limit",
        dest="limit",
        metavar="N",
        type=int,
        default=99999,
        help="limit number of test questions to process (default: all)",
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="re-run and overwrite existing generation and grading results",
    )
    parser.add_argument(
        "--grade-only",
        dest="grade_only",
        action="store_true",
        help="only grade existing responses, skip response generation",
    )
    parser.add_argument(
        "--recursive",
        action="store_true",
        help="scan subdirectories recursively, run each leaf concurrently",
    )
    parser.add_argument(
        "--detect-metadata",
        dest="detect_metadata",
        action="store_true",
        help="auto-detect model context_length and max_completion_tokens from OpenRouter API before generation",
    )
    parser.add_argument(
        "--repeat-sample",
        dest="sample_k",
        metavar="N",
        type=int,
        default=None,
        help="number of independent responses to sample per generator model per question (default: 1)",
    )
    parser.add_argument(
        "--repeat-judge",
        dest="repeated_judge",
        metavar="N",
        type=int,
        default=None,
        help="number of repeated judge runs per (model_response, judge_model) pair for variance analysis (default: 1)",
    )
