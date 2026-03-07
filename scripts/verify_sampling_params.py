#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Verify sampling parameters configuration."""

from pathlib import Path
import sys

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.omb.config import ConfigManager


def verify_sampling_parameters():
    """Verify that sampling parameters are properly configured."""
    print("=" * 60)
    print("Sampling Parameters Configuration Verification")
    print("=" * 60)

    # Load default config
    config = ConfigManager()

    print("\n📋 Current Configuration:")
    print(f"  TEMPERATURE: {config.temperature}")
    print(f"  MAX_TOKENS: {config.max_tokens}")
    print(f"  TOP_P: {config.top_p}")
    print(f"  TOP_K: {config.top_k}")
    print(f"  MIN_P: {config.min_p}")
    print(f"  FREQUENCY_PENALTY: {config.frequency_penalty}")
    print(f"  PRESENCE_PENALTY: {config.presence_penalty}")
    print(f"  REPETITION_PENALTY: {config.repetition_penalty}")

    print("\n✅ Configuration Properties:")
    properties = [
        'top_p', 'top_k', 'min_p',
        'frequency_penalty', 'presence_penalty', 'repetition_penalty'
    ]

    for prop in properties:
        value = getattr(config, prop)
        status = "✓ Configured" if value is not None else "○ Disabled (null)"
        print(f"  {prop:20s}: {status}")

    print("\n📝 Usage Example:")
    print("  To enable sampling parameters, edit config/default.yaml:")
    print("  ")
    print("  TOP_P: 0.9")
    print("  TOP_K: 40")
    print("  FREQUENCY_PENALTY: 0.5")
    print("  PRESENCE_PENALTY: 0.5")

    print("\n" + "=" * 60)
    print("Verification Complete!")
    print("=" * 60)


if __name__ == "__main__":
    verify_sampling_parameters()
