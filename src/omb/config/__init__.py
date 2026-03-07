#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Configuration management for omb."""

import os
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml


class Config:
    """Configuration manager for omb."""

    def __init__(self, config_path: Optional[Path] = None):
        """Initialize configuration.

        Args:
            config_path: Path to custom config file. If None, uses default config.
        """
        self._config: Dict[str, Any] = {}
        self._load_default_config()

        if config_path and config_path.exists():
            self._load_custom_config(config_path)

    def _load_default_config(self) -> None:
        """Load default configuration."""
        default_config_path = Path(__file__).parent / "default.yaml"
        if default_config_path.exists():
            with open(default_config_path, "r", encoding="utf-8") as f:
                self._config = yaml.safe_load(f) or {}

    def _load_custom_config(self, config_path: Path) -> None:
        """Load custom configuration and merge with defaults."""
        with open(config_path, "r", encoding="utf-8") as f:
            custom_config = yaml.safe_load(f) or {}
        self._config.update(custom_config)

    def get(self, key: str, default: Any = None) -> Any:
        """Get configuration value."""
        return self._config.get(key, default)

    def set(self, key: str, value: Any) -> None:
        """Set configuration value."""
        self._config[key] = value

    def __getitem__(self, key: str) -> Any:
        """Get configuration value using dict-like access."""
        return self._config[key]

    def __setitem__(self, key: str, value: Any) -> None:
        """Set configuration value using dict-like access."""
        self._config[key] = value

    @property
    def router_api_base(self) -> str:
        """Get OpenRouter API base URL."""
        return self.get(
            "ROUTER_API_BASE", "https://openrouter.ai/api/v1/chat/completions"
        )

    @property
    def router_api_key(self) -> str:
        """Get OpenRouter API key."""
        return os.getenv("OPENROUTER_API_KEY") or self.get("ROUTER_API_KEY", "")

    @property
    def judge_models(self) -> List[str]:
        """Get list of judge model names."""
        models = self.get("JUDGE_MODELS", None)
        if models and isinstance(models, list):
            return [m for m in models if m is not None]
        # Backward compat: fall back to single JUDGE_MODEL string
        single = self.get("JUDGE_MODEL", "google/gemini-3-pro-preview")
        return [single] if single else ["google/gemini-3-pro-preview"]

    @property
    def judge_model(self) -> str:
        """Get first judge model name (backward compat)."""
        return self.judge_models[0]

    @property
    def reference_models(self) -> List[str]:
        """Get list of reference models."""
        models = self.get("REFERENCE_MODELS", [])
        if models is None:
            return []
        return [m for m in models if m is not None]

    @property
    def generator_models(self) -> List[str]:
        """Get list of generator models."""
        return self.get("GENERATOR_MODELS", [])

    @property
    def ling_api_base(self) -> str:
        """Get Ling-1T API base URL."""
        return self.get(
            "LING_API_BASE", "https://api.tbox.cn/api/llm/v1/chat/completions"
        )

    @property
    def ling_api_key(self) -> str:
        """Get Ling-1T API key."""
        return os.getenv("LING_API_KEY") or self.get("LING_API_KEY", "")

    @property
    def volc_api_base(self) -> str:
        """Get VolcEngine API base URL."""
        return self.get("VOLC_API_BASE", "https://ark.cn-beijing.volces.com/api/v3")

    @property
    def volc_api_key(self) -> str:
        """Get VolcEngine API key."""
        return os.getenv("VOLC_API_KEY") or self.get("VOLC_API_KEY", "")

    @property
    def dashscope_api_base(self) -> str:
        """Get DashScope API base URL."""
        return self.get(
            "DASHSCOPE_API_BASE",
            "https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions",
        )

    @property
    def dashscope_api_key(self) -> str:
        """Get DashScope API key."""
        return os.getenv("DASHSCOPE_API_KEY") or self.get("DASHSCOPE_API_KEY", "")

    @property
    def hunyuan_api_base(self) -> str:
        """Get Hunyuan API base URL."""
        return self.get(
            "HUNYUAN_API_BASE",
            "https://api.hunyuan.cloud.tencent.com/v1/chat/completions",
        )

    @property
    def hunyuan_api_key(self) -> str:
        """Get Hunyuan API key."""
        return os.getenv("HUNYUAN_API_KEY") or self.get("HUNYUAN_API_KEY", "")

    @property
    def litellm_api_key(self) -> str:
        """Get LiteLLM API key."""
        return os.getenv("LITELLM_API_KEY") or self.get("LITELLM_API_KEY", "")

    @property
    def temperature(self) -> float:
        """Get temperature for API calls."""
        return self.get("TEMPERATURE", 0.0)

    @property
    def model_metadata(self) -> Dict[str, Dict[str, Any]]:
        """Get detected model metadata (context_length, max_completion_tokens)."""
        return self.get("MODEL_METADATA", {})

    def set_model_metadata(self, metadata: Dict[str, Dict[str, Any]]) -> None:
        """Store detected model metadata."""
        self.set("MODEL_METADATA", metadata)

    @property
    def max_tokens(self) -> int:
        """Get max tokens for API calls."""
        return self.get("MAX_TOKENS", 128000)

    def get_max_tokens_for_model(self, model_id: str) -> int:
        """Get max_tokens for a specific model.

        Uses detected metadata (max_completion_tokens) if available,
        otherwise falls back to the global MAX_TOKENS setting.

        Args:
            model_id: The model identifier

        Returns:
            max_tokens value for this model
        """
        metadata = self.model_metadata
        if metadata and model_id in metadata:
            max_comp = metadata[model_id].get("max_completion_tokens")
            if max_comp is not None:
                return max_comp
        return self.max_tokens

    @property
    def timeout(self) -> int:
        """Get timeout for API calls in seconds."""
        return self.get("TIMEOUT", 600)

    @property
    def retry_times(self) -> int:
        """Get number of retry attempts."""
        return self.get("RETRY_TIMES", 3)

    @property
    def retry_delay(self) -> int:
        """Get delay between retries in seconds."""
        return self.get("RETRY_DELAY", 1)

    @property
    def max_generation_concurrency(self) -> int:
        """Get maximum concurrent generation requests."""
        return self.get("MAX_GENERATION_CONCURRENCY", self.get("MAX_CONCURRENT", 64))

    @property
    def max_grading_concurrency(self) -> int:
        """Get maximum concurrent grading requests."""
        return self.get("MAX_GRADING_CONCURRENCY", self.get("MAX_CONCURRENT", 64))

    @property
    def reasoning_effort(self) -> Optional[str]:
        """Get reasoning effort level."""
        return self.get("REASONING_EFFORT", None)

    @property
    def proxy(self) -> Optional[str]:
        """Get proxy URL."""
        return self.get("PROXY", None)

    @property
    def debug(self) -> bool:
        """Get debug mode flag."""
        return self.get("DEBUG", False)

    @property
    def enable_search(self) -> bool:
        """Get enable search flag."""
        return self.get("ENABLE_SEARCH", False)

    @property
    def sample_k(self) -> int:
        """Get number of independent responses to sample per generator model."""
        return self.get("SAMPLE_K", 1)

    @property
    def repeated_judge(self) -> int:
        """Get number of repeated judge runs per (model_response, judge_model) pair."""
        return self.get("REPEATED_JUDGE", 1)

    @property
    def top_p(self) -> Optional[float]:
        """Get top_p (nucleus sampling) parameter."""
        return self.get("TOP_P", None)

    @property
    def top_k(self) -> Optional[int]:
        """Get top_k sampling parameter."""
        return self.get("TOP_K", None)

    @property
    def min_p(self) -> Optional[float]:
        """Get min_p (minimum probability) parameter."""
        return self.get("MIN_P", None)

    @property
    def frequency_penalty(self) -> Optional[float]:
        """Get frequency penalty parameter."""
        return self.get("FREQUENCY_PENALTY", None)

    @property
    def presence_penalty(self) -> Optional[float]:
        """Get presence penalty parameter."""
        return self.get("PRESENCE_PENALTY", None)

    @property
    def repetition_penalty(self) -> Optional[float]:
        """Get repetition penalty parameter."""
        return self.get("REPETITION_PENALTY", None)


# Global config instance
_config: Optional[Config] = None


def get_config() -> Config:
    """Get global config instance."""
    global _config
    if _config is None:
        _config = Config()
    return _config


def set_config(config: Config) -> None:
    """Set global config instance."""
    global _config
    _config = config


class ConfigManager(Config):
    """Extended configuration manager with pricing information."""

    def get_model_pricing(self) -> Dict[str, Dict[str, float]]:
        """Get model pricing configuration.

        Returns:
            Dictionary mapping model names to pricing info (input/output per 1M tokens)
        """
        return self.get("MODEL_PRICING", {})

    def get_default_pricing(self) -> Dict[str, float]:
        """Get default pricing for unknown models.

        Returns:
            Default pricing dictionary with input/output rates
        """
        return self.get("DEFAULT_PRICING", {"input": 0.0, "output": 0.0})

    def get_model_config(self) -> Dict[str, Any]:
        """Get model configuration.

        Returns:
            Dictionary with model settings
        """
        return {
            "judge_model": self.judge_model,
            "judge_models": self.judge_models,
            "reference_models": self.reference_models,
            "generator_models": self.generator_models,
        }

    def get_file_processing_config(self) -> Dict[str, Any]:
        """Get file processing configuration.

        Returns:
            Dictionary with file processing settings
        """
        return {
            "input_directory": self.get(
                "INPUT_DIRECTORY", "datasets/ExpertBench-12.31/代码_Expertbench"
            ),
            "output_directory": self.get("OUTPUT_DIRECTORY", "outputs"),
            "file_pattern": self.get("FILE_PATTERN", "SQL_Item_*.json"),
        }


# Global ConfigManager instance
_config_manager: Optional[ConfigManager] = None


def get_config_manager(config_path: Optional[Path] = None) -> ConfigManager:
    """Get global ConfigManager instance.

    Args:
        config_path: Optional path to config file

    Returns:
        ConfigManager instance
    """
    global _config_manager
    if _config_manager is None:
        _config_manager = ConfigManager(config_path)
    return _config_manager


def set_config_manager(config_manager: ConfigManager) -> None:
    """Set global ConfigManager instance.

    Args:
        config_manager: ConfigManager to set as global
    """
    global _config_manager
    _config_manager = config_manager
