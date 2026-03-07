#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Rubrics-based Auto Grading Example

A simple example script demonstrating how to run rubrics-based evals.

Usage:
    python auto_grading.py                    # Process all files
    python auto_grading.py --test_path test_file.json     # Process single file
    python auto_grading.py --config custom.yaml  # Use custom config
"""

import argparse
from omb.orchestrator import main
from omb.config import get_config_manager
from omb.utils import print_info


def parse_args():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(description="Rubrics-based Auto Grading Evals")
    parser.add_argument("--test_path", "-f", help="Optional test file to process")
    parser.add_argument("--config", "-c", help="Custom configuration file (YAML)")
    parser.add_argument(
        "--list_models", action="store_true", help="List configured models"
    )
    parser.add_argument(
        "--validate_config", action="store_true", help="Validate configuration"
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Show test questions and model predictions (generator and judge)",
    )
    parser.add_argument(
        "--max_test_nums",
        type=int,
        help="Maximum number of test questions to process per generator model (selected sequentially)",
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Overwrite existing generation and grading results",
    )
    return parser.parse_args()


def list_models(config_file=None):
    """List configured models."""
    config_manager = get_config_manager(config_file)
    model_config = config_manager.get_model_config()

    print("Configured Models:")
    print(f"  Judge: {model_config.get('judge_model', 'Not configured')}")
    print(f"  Reference: {', '.join(model_config.get('reference_models', []))}")
    print(f"  Generation: {', '.join(model_config.get('models_to_generate', []))}")


def validate_config(config_file=None):
    """Validate configuration."""
    config_manager = get_config_manager(config_file)
    model_config = config_manager.get_model_config()

    if not model_config.get("judge_model"):
        print("Error: Judge model not configured")
        return False

    # print("Configuration validated successfully")
    return True


if __name__ == "__main__":
    args = parse_args()

    # Handle special modes
    if args.list_models:
        list_models(args.config)
        exit()

    if args.validate_config:
        exit(0 if validate_config(args.config) else 1)

    # Validate and run
    if not validate_config(args.config):
        print("Configuration validation failed")
        exit(1)

    try:
        # Display configuration info with rich formatting
        config_manager = get_config_manager(args.config)
        print_info(f"Using config: {config_manager.config_file}")

        if args.test_path:
            print_info(f"Processing: {args.test_path}")
        else:
            # Get default input directory from config
            file_config = config_manager.get_file_processing_config()
            input_dir = file_config.get(
                "input_directory", "datasets/ExpertBench-12.31/代码_Expertbench"
            )
            print_info(f"Processing: {input_dir}")

        main(args.config, args.test_path, args.debug, args.max_test_nums, args.overwrite)

    except KeyboardInterrupt:
        print("\nInterrupted by user")
    except Exception as e:
        print(f"\nExecution failed: {e}")
        raise
