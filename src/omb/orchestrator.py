#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Main orchestrator for rubric-based auto grading system."""

import asyncio
import json
import re
import ssl
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import aiohttp

from .config import Config, ConfigManager, get_config
from .processing import generate_model_response, grade_single_model
from .reporting import generate_excel_report, generate_json_report
from .tracking import TokenTracker
from .utils import (
    LOGO1,
    LOGO2,
    RichColors,
    console,
    create_config_table,
    create_cost_breakdown_table,
    create_metadata_table,
    create_performance_table,
    create_summary_table,
    err_console,
    print_error,
    print_header,
    print_info,
    print_logo,
    print_section,
    print_success,
    print_warning,
)


class ExitCode:
    """CLI exit codes following standard conventions."""

    SUCCESS = 0
    GENERAL_ERROR = 1
    CONFIG_ERROR = 2
    INPUT_ERROR = 3
    PARTIAL_FAILURE = 4
    INTERRUPTED = 130  # Standard SIGINT exit code


class Orchestrator:
    """Orchestrator for managing the grading workflow."""

    def __init__(self, config: Optional[Config] = None):
        """Initialize orchestrator.

        Args:
            config: Configuration object (uses default if None)
        """
        self.config = config or get_config()

        # Create ConfigManager for pricing
        if isinstance(self.config, ConfigManager):
            self.config_manager = self.config
        else:
            self.config_manager = ConfigManager()

        # Initialize TokenTracker
        self.token_tracker = TokenTracker(self.config_manager)

        self.generation_semaphore: Optional[asyncio.Semaphore] = None
        self.grading_semaphore: Optional[asyncio.Semaphore] = None
        self.file_data_map: Dict[Path, Dict[str, Any]] = {}

    def _get_prompt(self, data: Dict[str, Any]) -> str:
        """Get prompt from data, supporting both 'prompt' and 'Prompt'.

        Args:
            data: Dictionary containing task data

        Returns:
            The prompt string
        """
        return data.get("prompt") or data.get("Prompt", "")

    def scan_files(
        self, test_dir: Path, pattern: str = "*.json"
    ) -> List[Path]:
        """Scan directory for JSON files.

        Args:
            test_dir: Directory to scan
            pattern: File pattern to match

        Returns:
            List of JSON file paths
        """
        return sorted(test_dir.glob(pattern))

    def _is_legacy_format(self, data: Dict[str, Any], section: str) -> bool:
        """Check if a data section uses the legacy flat format (not nested by judge model).

        Args:
            data: File data dictionary
            section: Section name (e.g. 'rubric_auto_score')

        Returns:
            True if the section exists and uses legacy flat format
        """
        section_data = data.get(section, {})
        if not section_data:
            return False
        # New format: top-level keys are judge model names (contain '/').
        # Legacy format: top-level keys are score keys like 'rubric_1_response_1_auto_score'.
        first_key = next(iter(section_data), "")
        return first_key.startswith("rubric_")

    def _migrate_legacy_scores(self, data: Dict[str, Any]) -> None:
        """Migrate legacy flat score data to nested format under '_legacy' key.

        Args:
            data: File data dictionary (modified in place)
        """
        for section in ("rubric_auto_score", "rubric_auto_vs_human", "judge_cot"):
            if self._is_legacy_format(data, section):
                old_data = data[section]
                data[section] = {"_legacy": old_data}

    def _normalize_item(self, data: Dict[str, Any]) -> None:
        """Normalize field names for a single data item in-place."""
        if "Prompt" in data and "prompt" not in data:
            data["prompt"] = data["Prompt"]
        if "question" in data and "prompt" not in data:
            data["prompt"] = data["question"]
        if "Rubrics" in data and "rubrics" not in data:
            data["rubrics"] = data["Rubrics"]
        if "System_Prompt" in data and "system_prompt" not in data:
            data["system_prompt"] = data["System_Prompt"]
        self._migrate_legacy_scores(data)

    def load_file_data(self, json_files: List[Path]) -> List[Path]:
        """Load all JSON files into memory.

        If a file contains a JSON array, each element is expanded into a
        virtual path (e.g. test_0.json, test_1.json) so the rest of the
        pipeline can treat every item as an independent file.

        Args:
            json_files: List of JSON file paths

        Returns:
            Expanded list of paths (virtual paths for list-format files).
        """
        expanded: List[Path] = []
        for json_path in json_files:
            with open(json_path, "r", encoding="utf-8") as f:
                data = json.load(f)

            if isinstance(data, list):
                for idx, item in enumerate(data):
                    virtual_path = json_path.parent / f"{json_path.stem}_{idx}.json"
                    self._normalize_item(item)
                    self.file_data_map[virtual_path] = item
                    expanded.append(virtual_path)
            else:
                self._normalize_item(data)
                self.file_data_map[json_path] = data
                expanded.append(json_path)
        return expanded

    def collect_existing_grading_data(
        self, json_files: List[Path], overwrite: bool = False, grade_only: bool = False
    ) -> List[Dict[str, Any]]:
        """Collect existing models that need grading.

        Creates one grading task per (model_response, judge_model) pair.

        Args:
            json_files: List of JSON file paths
            overwrite: Overwrite existing results
            grade_only: Grade all existing responses regardless of model config

        Returns:
            List of grading task data
        """
        existing_grading_data = []

        for json_path in json_files:
            data = self.file_data_map[json_path]
            prompt = self._get_prompt(data)
            rubrics = data.get("rubrics", [])
            model_responses = data.get("model_response", {})
            rubric_auto_score = data.get("rubric_auto_score", {})

            if not rubrics:
                continue

            for response_key, response_data in model_responses.items():
                match = re.match(r"model_response_(\d+)", response_key)
                if not match:
                    continue

                model_idx = int(match.group(1))
                model_name = response_data.get("model_name", "")
                model_response_text = response_data.get("response_text", "")

                if not model_response_text or str(model_response_text).strip() == "N/A":
                    continue

                # In grade_only mode, grade all models with responses;
                # otherwise only grade models in reference or generator lists
                if not grade_only and (
                    model_name not in self.config.reference_models
                    and model_name not in self.config.generator_models
                ):
                    continue

                # Loop over each judge model (with repeated runs if configured)
                repeated_judge = self.config.repeated_judge
                for judge_model in self.config.judge_models:
                    effective_judges = (
                        [f"{judge_model}::run_{i}" for i in range(1, repeated_judge + 1)]
                        if repeated_judge > 1
                        else [judge_model]
                    )
                    for effective_judge in effective_judges:
                        needs_grading = False
                        if overwrite:
                            needs_grading = True
                        else:
                            # Check if scores exist for this judge model
                            judge_scores = rubric_auto_score.get(effective_judge, {})
                            for rubric in rubrics:
                                rubric_num = rubric["rubric_number"]
                                score_key = (
                                    f"rubric_{rubric_num}_response_{model_idx}_auto_score"
                                )
                                score = judge_scores.get(score_key)
                                if score is None or score == "NA":
                                    needs_grading = True
                                    break

                        if needs_grading:
                            human_scores_dict = self._extract_human_scores(
                                rubrics, model_idx
                            )

                            existing_grading_data.append(
                                {
                                    "file_path": json_path,
                                    "model_idx": model_idx,
                                    "model_name": model_name,
                                    "model_response_text": model_response_text,
                                    "prompt": prompt,
                                    "rubrics": rubrics,
                                    "human_scores_dict": human_scores_dict,
                                    "judge_model": effective_judge,
                                }
                            )

        return existing_grading_data

    def _extract_human_scores(
        self, rubrics: List[Dict[str, Any]], model_idx: int
    ) -> Dict[str, int]:
        """Extract human scores for a model.

        Args:
            rubrics: List of rubrics
            model_idx: Model index

        Returns:
            Dictionary of human scores
        """
        human_scores_dict = {}

        if not rubrics:
            return human_scores_dict

        # Check if first rubric has human scores
        first_rubric = rubrics[0]
        first_scores = first_rubric.get("scores", {})
        human_key = f"response_{model_idx}_human_score_1"

        if human_key not in first_scores:
            return human_scores_dict

        # Extract all human scores
        for rubric in rubrics:
            rubric_num = rubric["rubric_number"]
            rubric_scores = rubric.get("scores", {})
            if human_key in rubric_scores:
                human_scores_dict[f"rubric_{rubric_num}_human_score"] = rubric_scores[
                    human_key
                ]

        return human_scores_dict

    def collect_missing_models(
        self, json_files: List[Path], overwrite: bool = False
    ) -> List[Dict[str, Any]]:
        """Collect models that need response generation.

        With sample_k > 1, generates multiple independent responses per model.

        Args:
            json_files: List of JSON file paths
            overwrite: Overwrite existing results

        Returns:
            List of generation task data
        """
        fill_data = []
        sample_k = self.config.sample_k

        for json_path in json_files:
            data = self.file_data_map[json_path]
            prompt = self._get_prompt(data)
            model_responses = data.get("model_response", {})

            # Count existing valid responses per model
            existing_counts: Dict[str, int] = {}
            for v in model_responses.values():
                model_name = v.get("model_name", "")
                response_text = v.get("response_text", "")
                if model_name and response_text and str(response_text).strip() != "N/A":
                    existing_counts[model_name] = existing_counts.get(model_name, 0) + 1

            for model_name in self.config.generator_models:
                if overwrite:
                    needed = sample_k
                else:
                    needed = sample_k - existing_counts.get(model_name, 0)

                for _ in range(max(0, needed)):
                    fill_data.append(
                        {
                            "file_path": json_path,
                            "model_name": model_name,
                            "prompt": prompt,
                        }
                    )

        return fill_data

    def process_grading_result(self, result: Dict[str, Any], file_path: Path) -> None:
        """Process a single grading result and update file data.

        Stores results nested under the judge model name.

        Args:
            result: Grading result dictionary
            file_path: Path to the JSON file
        """
        data = self.file_data_map[file_path]
        rubrics = data.get("rubrics", [])
        model_idx = result["model_idx"]
        judge_model = result.get("judge_model", self.config.judge_model)

        if "rubric_auto_score" not in data:
            data["rubric_auto_score"] = {}
        if "rubric_auto_vs_human" not in data:
            data["rubric_auto_vs_human"] = {}
        if "judge_cot" not in data:
            data["judge_cot"] = {}

        # Ensure nested dict for this judge model
        if judge_model not in data["rubric_auto_score"]:
            data["rubric_auto_score"][judge_model] = {}
        if judge_model not in data["rubric_auto_vs_human"]:
            data["rubric_auto_vs_human"][judge_model] = {}
        if judge_model not in data["judge_cot"]:
            data["judge_cot"][judge_model] = {}

        for rubric in rubrics:
            rubric_num = rubric["rubric_number"]
            score_key = f"rubric_{rubric_num}_response_{model_idx}_auto_score"
            final_score = result["final_scores"].get(rubric_num, 0)
            data["rubric_auto_score"][judge_model][score_key] = final_score

            rubric_scores = rubric.get("scores", {})
            human_key = f"response_{model_idx}_human_score_1"
            raw_result = result["raw_results"].get(rubric_num, {})

            # Determine consistency
            model_consistency = raw_result.get("consistency", "").strip()
            if model_consistency:
                consistency = model_consistency
            elif human_key in rubric_scores:
                human_score = rubric_scores[human_key]
                consistency = (
                    "Consistent" if final_score == human_score else "Inconsistent"
                )
            else:
                consistency = "No human score"

            cot_key = f"rubric_{rubric_num}_response_{model_idx}_judge_cot"
            data["judge_cot"][judge_model][cot_key] = {
                "status": raw_result.get("status", "No"),
                "justification": raw_result.get("justification", ""),
                "consistency": consistency,
            }

            vs_key = f"rubric_{rubric_num}_response_{model_idx}_auto_vs_human"
            data["rubric_auto_vs_human"][judge_model][vs_key] = consistency

    def save_results(self, json_files: List[Path], result_dir: Path) -> None:
        """Save all results to output directory.

        Args:
            json_files: List of JSON file paths
            result_dir: Output directory
        """
        result_dir.mkdir(parents=True, exist_ok=True)

        for json_path in json_files:
            data = self.file_data_map[json_path]
            result_path = result_dir / json_path.name
            with open(result_path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=4)
            print_success(f"{json_path.stem}", prefix="  ✓")

    async def run(
        self,
        test_dir: Path,
        output_dir: Optional[Path] = None,
        test_file: Optional[Path] = None,
        limit: Optional[int] = None,
        overwrite: bool = False,
        grade_only: bool = False,
    ) -> None:
        """Run the complete grading workflow.

        Args:
            test_dir: Directory containing test files
            output_dir: Output directory (auto-generated if None)
            test_file: Single test file (for testing mode)
            limit: Maximum number of test questions to process (selected sequentially)
            overwrite: Overwrite existing generation and grading results
            grade_only: Only grade existing responses, skip generation
        """
        start_time = time.time()

        # Print header
        err_console.print()
        print_header(
            "Rubric-based Auto Grading System", "Concurrent Generation and Grading"
        )
        print_logo(LOGO1)

        config_data = {
            "Judge Models": "\n".join([f"• {m}" for m in self.config.judge_models]),
            "Generator Models": (
                "N/A (grade-only)"
                if grade_only
                else "\n".join([f"• {model}" for model in self.config.generator_models])
            ),
            "Reference Models": (
                "\n".join([f"• {model}" for model in self.config.reference_models])
                if self.config.reference_models
                else "None"
            ),
            "Max Tokens": (
                "per-model (auto-detected)"
                if self.config.model_metadata
                else str(self.config.max_tokens)
            ),
            "Generation Concurrency": self.config.max_generation_concurrency,
            "Grading Concurrency": self.config.max_grading_concurrency,
            "Overwrite": "Yes" if overwrite else "No",
            "Grade Only": "Yes" if grade_only else "No",
            "Sample K": self.config.sample_k,
        }
        if self.config.repeated_judge > 1:
            config_data["Repeated Judge"] = self.config.repeated_judge
        config_table = create_config_table(config_data)
        console.print(config_table)
        err_console.print()

        # Initialize concurrency controls
        self.generation_semaphore = asyncio.Semaphore(
            self.config.max_generation_concurrency
        )
        self.grading_semaphore = asyncio.Semaphore(self.config.max_grading_concurrency)

        # Scan files
        if test_file:
            json_files = [test_file] if test_file.exists() else []
            print_info(f"Test Mode: {test_file.name}")
        else:
            json_files = self.scan_files(test_dir)

        if not json_files:
            print_error("No files found")
            return

        # Load files (expands list-format JSON into individual items)
        json_files = self.load_file_data(json_files)

        if not json_files:
            print_error("No files found")
            return

        # Apply limit if specified
        if limit is not None and limit > 0:
            original_count = len(json_files)
            json_files = json_files[:limit]
            print_info(f"Found {original_count} questions (limit: {len(json_files)})")
        else:
            print_info(f"Found {len(json_files)} files to process")

        # Create output directory
        if output_dir is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_dir = Path(f"outputs/result_{timestamp}")

        print_info(f"Result Directory: {output_dir}")
        err_console.print()

        # Load and process files
        await self._run_workflow(
            json_files, output_dir, overwrite=overwrite, grade_only=grade_only
        )

        # Print final statistics
        self._print_statistics(json_files, start_time)

        # Print cost metrics
        self._print_cost_metrics()

        # Generate Excel report
        self._generate_report(json_files, output_dir)

    def _clear_generator_responses(self, json_files: List[Path]) -> None:
        """Remove existing model_response entries for generator models.

        Called before generation when --overwrite is used, so that
        collect_missing_models sees count=0 and generates k fresh tasks.

        Args:
            json_files: List of JSON file paths
        """
        generator_set = set(self.config.generator_models)
        for json_path in json_files:
            data = self.file_data_map[json_path]
            model_responses = data.get("model_response", {})
            keys_to_remove = [
                key
                for key, val in model_responses.items()
                if val.get("model_name", "") in generator_set
            ]
            for key in keys_to_remove:
                del model_responses[key]

    async def _run_workflow(
        self,
        json_files: List[Path],
        output_dir: Path,
        overwrite: bool = False,
        grade_only: bool = False,
    ) -> None:
        """Run the main workflow: scan, generate, grade, save.

        Args:
            json_files: List of JSON file paths
            output_dir: Output directory
            overwrite: Overwrite existing results
            grade_only: Only grade existing responses, skip generation
        """
        # Scan existing data
        print_section("Scanning Files: Collecting existing and missing models")

        # Clear existing generator responses when overwriting (before collecting tasks)
        if overwrite and not grade_only:
            self._clear_generator_responses(json_files)

        # Collect tasks
        existing_grading_data = self.collect_existing_grading_data(
            json_files, overwrite=overwrite, grade_only=grade_only
        )
        fill_data = (
            []
            if grade_only
            else self.collect_missing_models(json_files, overwrite=overwrite)
        )

        err_console.print()

        # Show grading tasks with breakdown
        total_tasks = 0
        if existing_grading_data:
            files_with_grading = set(d["file_path"] for d in existing_grading_data)
            num_files = len(files_with_grading)
            total_tasks = len(existing_grading_data)

            if num_files > 0 and total_tasks % num_files == 0:
                models_per_file = total_tasks // num_files
                print_success(
                    f"Consistency Check ({models_per_file}×{num_files}): {total_tasks}"
                )
            else:
                print_success(f"Consistency Check: {total_tasks}")
        else:
            print_success(f"Consistency Check: 0")

        # Show generation tasks with breakdown
        if fill_data:
            files_with_missing = set(d["file_path"] for d in fill_data)
            num_files = len(files_with_missing)
            total_tasks = len(fill_data)

            if num_files > 0 and total_tasks % num_files == 0:
                models_per_file = total_tasks // num_files
                print_success(
                    f"Generation ({models_per_file}×{num_files}): {total_tasks}"
                )
            else:
                print_success(f"Generation: {total_tasks}")
                print_success(f"Post Grading: {total_tasks}")
        else:
            print_success(f"Generation: 0")
            print_success(f"Post Grading: {total_tasks}")

        err_console.print()

        # Create SSL context
        ssl_context = ssl.create_default_context()
        ssl_context.check_hostname = False
        ssl_context.verify_mode = ssl.CERT_NONE
        connector = aiohttp.TCPConnector(ssl=ssl_context)

        async with aiohttp.ClientSession(connector=connector) as session:
            # Phase 1: Concurrent generation and grading
            await self._phase_concurrent_processing(
                session,
                existing_grading_data,
                fill_data,
                json_files,
                overwrite=overwrite,
            )

            # Phase 2: Retry failed generations
            # await self._phase_retry_failed(session, json_files)

        # Save results
        print_section("Saving Results")
        print_info("Saving results to result directory (original files unchanged)")
        err_console.print()
        self.save_results(json_files, output_dir)

    async def _phase_concurrent_processing(
        self,
        session: Any,
        existing_grading_data: List[Dict[str, Any]],
        fill_data: List[Dict[str, Any]],
        json_files: List[Path],
        overwrite: bool = False,
    ) -> None:
        """Phase 1: Concurrent generation and grading.

        Args:
            session: aiohttp ClientSession
            existing_grading_data: List of existing models to grade
            fill_data: List of missing generator models
            json_files: List of JSON file paths
            overwrite: Overwrite existing results
        """
        print_section(
            f"Phase 1+2 Concurrency: Generating {len(fill_data)} + Grading {len(existing_grading_data)}"
        )

        from rich.progress import (
            BarColumn,
            MofNCompleteColumn,
            Progress,
            SpinnerColumn,
            TextColumn,
            TimeElapsedColumn,
        )

        total_tasks = len(existing_grading_data) + len(fill_data)

        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(bar_width=40),
            MofNCompleteColumn(),
            TimeElapsedColumn(),
            console=err_console,
            refresh_per_second=256,
            speed_estimate_period=1,
            auto_refresh=True,
        ) as progress:
            gen_task_id = (
                progress.add_task(
                    f"[bold {RichColors.YELLOW}]Generating[/bold {RichColors.YELLOW}]",
                    total=len(fill_data),
                )
                if fill_data
                else None
            )
            grade_task_id = (
                progress.add_task(
                    f"[{RichColors.CYAN}]Grading[/{RichColors.CYAN}]",
                    total=len(existing_grading_data),
                )
                if existing_grading_data
                else None
            )

            all_tasks = []
            task_metadata = []

            # Create grading tasks
            for data_info in existing_grading_data:
                task = grade_single_model(
                    session,
                    data_info["prompt"],
                    data_info["model_name"],
                    data_info["model_response_text"],
                    data_info["rubrics"],
                    data_info["human_scores_dict"],
                    data_info["model_idx"],
                    data_info["file_path"].stem,
                    self.config,
                    self.grading_semaphore,
                    progress,
                    grade_task_id,
                    self.token_tracker,
                    judge_model=data_info.get("judge_model"),
                )
                all_tasks.append(task)
                task_metadata.append({"type": "grading", "data_info": data_info})

            # Create generation tasks
            for data_info in fill_data:
                task = generate_model_response(
                    session,
                    data_info["prompt"],
                    data_info["model_name"],
                    data_info["file_path"].stem,
                    self.config,
                    self.generation_semaphore,
                    progress,
                    gen_task_id,
                    self.token_tracker,
                )
                all_tasks.append(task)
                task_metadata.append({"type": "generate", "data_info": data_info})

            # Execute all tasks concurrently
            all_results = await asyncio.gather(*all_tasks, return_exceptions=True)

        err_console.print()
        completed = sum(
            1 for r in all_results if not isinstance(r, Exception) and r is not None
        )
        print_success(f"Phase 1+2 Completed: {completed}/{total_tasks} tasks finished")
        err_console.print()

        # Separate results
        existing_results = []
        fill_results = []
        fill_data_for_results = []

        for metadata, result in zip(task_metadata, all_results):
            if metadata["type"] == "grading":
                existing_results.append((metadata["data_info"], result))
            else:  # generate
                fill_results.append(result)
                fill_data_for_results.append(metadata["data_info"])

        # Process grading results
        if existing_results:
            print_info("Processing grading results...")
            for data_info, result in existing_results:
                if isinstance(result, Exception) or not result:
                    continue
                self.process_grading_result(result, data_info["file_path"])

        # Process generation results
        if fill_results:
            print_info("Processing generation results...")
            new_responses_map = {}

            for data_info, result in zip(fill_data_for_results, fill_results):
                if isinstance(result, dict) and result.get("response_text"):
                    file_path = data_info["file_path"]
                    data = self.file_data_map[file_path]

                    if "model_response" not in data:
                        data["model_response"] = {}
                    model_responses = data["model_response"]

                    # Always allocate a new index (overwrite clearing happens upfront)
                    next_idx = (
                        max(
                            [int(k.split("_")[-1]) for k in model_responses.keys()]
                            + [0]
                        )
                        + 1
                    )
                    new_key = f"model_response_{next_idx}"

                    # Add sample_index for traceability
                    model_name = result["model_name"]
                    existing_count = sum(
                        1
                        for v in model_responses.values()
                        if v.get("model_name") == model_name
                    )
                    result["sample_index"] = existing_count

                    model_responses[new_key] = result

                    if file_path not in new_responses_map:
                        new_responses_map[file_path] = []
                    new_responses_map[file_path].append((next_idx, result))

            if new_responses_map:
                print_success(
                    f"Filled missing models for {len(new_responses_map)} files"
                )
                await self._grade_new_models(session, new_responses_map)

    async def _grade_new_models(
        self,
        session: Any,
        new_responses_map: Dict[Path, List[Tuple[int, Dict[str, Any]]]],
    ) -> None:
        """Grade newly generated models.

        Args:
            session: aiohttp ClientSession
            new_responses_map: Map of file paths to new response data
        """
        err_console.print()
        print_section("Phase 3: Grading newly generated models")

        from rich.progress import (
            BarColumn,
            MofNCompleteColumn,
            Progress,
            SpinnerColumn,
            TextColumn,
            TimeElapsedColumn,
        )

        total_new_models = sum(
            len(responses) for responses in new_responses_map.values()
        )
        # Expand by repeated judge runs
        repeated_judge = self.config.repeated_judge
        if repeated_judge > 1:
            effective_judge_count = len(self.config.judge_models) * repeated_judge
        else:
            effective_judge_count = len(self.config.judge_models)
        total_new_models *= effective_judge_count

        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(bar_width=40),
            MofNCompleteColumn(),
            TimeElapsedColumn(),
            console=err_console,
            refresh_per_second=30,
        ) as progress:
            grade_task_id = progress.add_task(
                f"[{RichColors.CYAN}]Grading new[/{RichColors.CYAN}]",
                total=total_new_models,
            )

            new_grading_tasks = []

            for file_path, new_responses in new_responses_map.items():
                data = self.file_data_map[file_path]
                prompt = self._get_prompt(data)
                rubrics = data.get("rubrics", [])

                for model_idx, response_data in new_responses:
                    model_name = response_data["model_name"]
                    model_response_text = response_data["response_text"]

                    for judge_model in self.config.judge_models:
                        effective_judges = (
                            [f"{judge_model}::run_{i}" for i in range(1, repeated_judge + 1)]
                            if repeated_judge > 1
                            else [judge_model]
                        )
                        for effective_judge in effective_judges:
                            task = grade_single_model(
                                session,
                                prompt,
                                model_name,
                                model_response_text,
                                rubrics,
                                {},
                                model_idx,
                                file_path.stem,
                                self.config,
                                self.grading_semaphore,
                                progress,
                                grade_task_id,
                                self.token_tracker,
                                judge_model=effective_judge,
                            )

                            new_grading_tasks.append(
                                {
                                    "task": task,
                                    "file_path": file_path,
                                    "model_idx": model_idx,
                                }
                            )

            new_results = await asyncio.gather(
                *[t["task"] for t in new_grading_tasks], return_exceptions=True
            )

        # Update grading results
        for task_info, result in zip(new_grading_tasks, new_results):
            if isinstance(result, Exception) or not result:
                continue
            self.process_grading_result(result, task_info["file_path"])

        err_console.print()
        print_success("Phase 3 Completed: New model grading finished")
        err_console.print()

    async def _phase_retry_failed(self, session: Any, json_files: List[Path]) -> None:
        """Phase 2: Retry failed generations.

        Args:
            session: aiohttp ClientSession
            json_files: List of JSON file paths
        """
        # Global retry loop to ensure all models are generated
        max_global_retries = 20
        retry_count = 0
        last_missing_count = None

        while retry_count < max_global_retries:
            # Check for still-missing models (count-based for sample_k)
            sample_k = self.config.sample_k
            retry_fill_data = []
            for json_path in json_files:
                data = self.file_data_map[json_path]
                model_responses = data.get("model_response", {})
                existing_counts: Dict[str, int] = {}
                for v in model_responses.values():
                    mn = v.get("model_name", "")
                    rt = v.get("response_text", "")
                    if mn and rt and str(rt).strip() != "N/A":
                        existing_counts[mn] = existing_counts.get(mn, 0) + 1

                for model_name in self.config.generator_models:
                    deficit = sample_k - existing_counts.get(model_name, 0)
                    for _ in range(max(0, deficit)):
                        retry_fill_data.append(
                            {
                                "file_path": json_path,
                                "model_name": model_name,
                                "prompt": self._get_prompt(data),
                            }
                        )

            if not retry_fill_data:
                if retry_count > 0:
                    print_success("All models generated successfully after retries!")
                return

            # Check for progress to avoid infinite retries
            current_missing_count = len(retry_fill_data)
            if (
                last_missing_count is not None
                and current_missing_count >= last_missing_count
            ):
                print_warning(
                    f"Phase 4: No progress in reducing missing models (stuck at {current_missing_count}). "
                    "Stopping retries to avoid infinite loop."
                )
                break
            last_missing_count = current_missing_count

            retry_count += 1
            err_console.print()
            print_section(
                f"Phase 4 (Retry {retry_count}/{max_global_retries}): Retrying {len(retry_fill_data)} failed generation tasks"
            )

            from rich.progress import (
                BarColumn,
                MofNCompleteColumn,
                Progress,
                SpinnerColumn,
                TextColumn,
                TimeElapsedColumn,
            )

            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                BarColumn(bar_width=40),
                MofNCompleteColumn(),
                TimeElapsedColumn(),
                console=err_console,
                refresh_per_second=30,
            ) as progress:
                retry_gen_task_id = progress.add_task(
                    f"[{RichColors.YELLOW}]Retry gen[/{RichColors.YELLOW}]",
                    total=len(retry_fill_data),
                )

                retry_tasks = []
                for data_info in retry_fill_data:
                    task = generate_model_response(
                        session,
                        data_info["prompt"],
                        data_info["model_name"],
                        data_info["file_path"].stem,
                        self.config,
                        self.generation_semaphore,
                        progress,
                        retry_gen_task_id,
                        self.token_tracker,
                    )
                    retry_tasks.append(task)

                retry_results = await asyncio.gather(*retry_tasks)

            # Save retry results
            retry_responses_map = {}
            for data_info, result in zip(retry_fill_data, retry_results):
                if isinstance(result, dict) and result.get("response_text"):
                    file_path = data_info["file_path"]
                    data = self.file_data_map[file_path]

                    if "model_response" not in data:
                        data["model_response"] = {}
                    model_responses = data["model_response"]

                    next_idx = (
                        max(
                            [int(k.split("_")[-1]) for k in model_responses.keys()]
                            + [0]
                        )
                        + 1
                    )
                    new_key = f"model_response_{next_idx}"
                    model_responses[new_key] = result

                    if file_path not in retry_responses_map:
                        retry_responses_map[file_path] = []
                    retry_responses_map[file_path].append((next_idx, result))

            if retry_responses_map:
                err_console.print()
                print_success(
                    f"Phase 4 (Retry {retry_count}) Completed: Succeeded for {len(retry_responses_map)} files"
                )
                await self._grade_new_models(session, retry_responses_map)
            else:
                print_warning(
                    f"Phase 4 (Retry {retry_count}): No new responses generated."
                )

        print_warning(
            f"Max retries ({max_global_retries}) reached. Some models may still be missing."
        )

    def _print_statistics(self, json_files: List[Path], start_time: float) -> None:
        """Print final statistics.

        Args:
            json_files: List of JSON file paths
            start_time: Start time timestamp
        """
        # Check for still-missing models (count-based for sample_k support)
        sample_k = self.config.sample_k
        final_missing = []
        for json_path in json_files:
            data = self.file_data_map[json_path]
            model_responses = data.get("model_response", {})
            existing_counts: Dict[str, int] = {}
            for v in model_responses.values():
                mn = v.get("model_name", "")
                rt = v.get("response_text", "")
                if mn and rt and str(rt).strip() != "N/A":
                    existing_counts[mn] = existing_counts.get(mn, 0) + 1

            missing_models = [
                m
                for m in self.config.generator_models
                if existing_counts.get(m, 0) < sample_k
            ]

            if missing_models:
                final_missing.append(
                    {"file": json_path.name, "missing": missing_models}
                )

        elapsed_time = time.time() - start_time
        elapsed_minutes = int(elapsed_time // 60)
        elapsed_seconds = int(elapsed_time % 60)

        err_console.print()
        print_header("Processing Complete!", "All tasks finished successfully")

        summary_data = {
            "Processed Files": len(json_files),
            "Total Time": f"{elapsed_minutes}m {elapsed_seconds}s",
        }
        summary_table = create_summary_table(summary_data)
        console.print(summary_table)
        err_console.print()

        # Print performance table per judge model
        all_performance = self._calculate_performance_metrics(json_files)
        for judge_model_name, performance_data in all_performance.items():
            print_section(f"Performance: {judge_model_name}")
            performance_table = create_performance_table(performance_data)
            console.print(performance_table)
            err_console.print()

        # Print aggregate performance for repeated judge runs
        if self.config.repeated_judge > 1:
            aggregate = self._calculate_repeated_judge_aggregate(all_performance)
            for base_judge, agg_data in aggregate.items():
                print_section(f"Aggregate Performance: {base_judge} ({self.config.repeated_judge} runs)")
                performance_table = create_performance_table(agg_data)
                console.print(performance_table)
                err_console.print()

        if final_missing:
            print_warning(f"Still missing models for {len(final_missing)} files:")
            for item in final_missing:
                err_console.print(
                    f"  [{RichColors.YELLOW}]• {item['file']}: {', '.join(item['missing'])}[/{RichColors.YELLOW}]"
                )
        else:
            print_success("All models are complete for all files!", prefix="✓")

        err_console.print()

    def _get_active_judge_models(self, json_files: List[Path]) -> List[str]:
        """Get list of judge models that have scores in the data.

        Args:
            json_files: List of JSON file paths

        Returns:
            List of judge model names with data
        """
        active = set()
        for json_path in json_files:
            data = self.file_data_map[json_path]
            rubric_auto_score = data.get("rubric_auto_score", {})
            for key in rubric_auto_score:
                if key != "_legacy":
                    active.add(key)
        # Preserve config order, then add any extras found in data
        result = [m for m in self.config.judge_models if m in active]
        for m in sorted(active):
            if m not in result:
                result.append(m)
        return result if result else self.config.judge_models

    def _calculate_performance_metrics(
        self, json_files: List[Path]
    ) -> Dict[str, Dict[str, Any]]:
        """Calculate overall performance metrics organized by model, per judge model.

        Args:
            json_files: List of JSON file paths

        Returns:
            Dictionary keyed by judge model name, each value is a performance metrics dict
        """
        import re

        active_judges = self._get_active_judge_models(json_files)
        all_results = {}

        for judge_model_name in active_judges:
            # Collect all models and initialize tracking
            all_models = set()
            model_totals = {}
            model_consistency_stats = {}

            for json_path in json_files:
                data = self.file_data_map[json_path]
                model_responses = data.get("model_response", {})
                rubrics = data.get("rubrics", [])
                rubric_auto_score = data.get("rubric_auto_score", {}).get(
                    judge_model_name, {}
                )
                rubric_auto_vs_human = data.get("rubric_auto_vs_human", {}).get(
                    judge_model_name, {}
                )

                # Collect models and initialize tracking
                for response_data in model_responses.values():
                    model_name = response_data.get("model_name", "")
                    if model_name:
                        all_models.add(model_name)
                        if model_name not in model_totals:
                            model_totals[model_name] = {
                                "score": 0,
                                "max_score": 0,
                                "min_score": 0,
                                "count": 0,
                                "task_accuracies": [],
                            }
                        if model_name not in model_consistency_stats:
                            model_consistency_stats[model_name] = {
                                "matches": 0,
                                "total": 0,
                            }

                # Calculate scores and consistency for each model
                for response_key, response_data in model_responses.items():
                    model_name = response_data.get("model_name", "")
                    if not model_name:
                        continue

                    match = re.match(r"model_response_(\d+)", response_key)
                    if not match:
                        continue
                    model_idx = int(match.group(1))

                    # Calculate total score
                    total_score = 0
                    valid_rubrics = 0
                    for rubric in rubrics:
                        rubric_num = rubric["rubric_number"]
                        score_key = (
                            f"rubric_{rubric_num}_response_{model_idx}_auto_score"
                        )
                        score = rubric_auto_score.get(score_key, 0)
                        if score != "NA":
                            total_score += score
                            valid_rubrics += 1

                    if valid_rubrics > 0:
                        task_max_score = 0
                        task_min_score = 0
                        for rubric in rubrics:
                            rubric_weight = rubric.get("rubric_weight", 0)
                            if rubric_weight > 0:
                                task_max_score += rubric_weight
                            elif rubric_weight < 0:
                                task_min_score += rubric_weight

                        model_totals[model_name]["score"] += total_score
                        model_totals[model_name]["max_score"] += task_max_score
                        model_totals[model_name]["min_score"] += task_min_score
                        model_totals[model_name]["count"] += 1

                        if task_max_score > 0:
                            task_accuracy = total_score / task_max_score
                            model_totals[model_name]["task_accuracies"].append(
                                task_accuracy
                            )
                        elif task_max_score == 0 and task_min_score < 0:
                            task_accuracy = 1 - (total_score / task_min_score)
                            model_totals[model_name]["task_accuracies"].append(
                                task_accuracy
                            )

                    # Calculate consistency for this model
                    for rubric in rubrics:
                        rubric_num = rubric["rubric_number"]
                        vs_key = (
                            f"rubric_{rubric_num}_response_{model_idx}_auto_vs_human"
                        )
                        consistency = rubric_auto_vs_human.get(vs_key, "无人工评分")

                        if consistency not in ("无人工评分", "No human score"):
                            model_consistency_stats[model_name]["total"] += 1
                            if consistency in ("一致", "Consistent"):
                                model_consistency_stats[model_name]["matches"] += 1

            # Sort models list for consistent ordering
            models_list = sorted(all_models)

            # Prepare metrics dictionary with model values
            metrics = {}

            min_scores = {}
            for model_name in models_list:
                stats = model_totals[model_name]
                if stats["count"] > 0:
                    min_scores[model_name] = f"{stats['min_score']:.1f}"
                else:
                    min_scores[model_name] = "N/A"
            metrics["Lower"] = min_scores

            max_scores = {}
            for model_name in models_list:
                stats = model_totals[model_name]
                if stats["count"] > 0:
                    max_scores[model_name] = f"{stats['max_score']:.1f}"
                else:
                    max_scores[model_name] = "N/A"
            metrics["Upper"] = max_scores

            macro_averages = {}
            for model_name in models_list:
                stats = model_totals[model_name]
                if stats["count"] > 0 and stats["max_score"] > 0:
                    percentage = (stats["score"] / stats["max_score"]) * 100
                    macro_averages[model_name] = f"{percentage:.1f}%"
                else:
                    macro_averages[model_name] = "N/A"
            metrics["Macro Average (%)"] = macro_averages

            micro_averages = {}
            for model_name in models_list:
                stats = model_totals[model_name]
                task_accuracies = stats.get("task_accuracies", [])
                if len(task_accuracies) > 0:
                    avg_accuracy = sum(task_accuracies) / len(task_accuracies)
                    percentage = avg_accuracy * 100
                    micro_averages[model_name] = f"{percentage:.1f}%"
                else:
                    micro_averages[model_name] = "N/A"
            metrics["Micro Average (%)"] = micro_averages

            consistency_rates = {}
            for model_name in models_list:
                stats = model_consistency_stats[model_name]
                if stats["total"] > 0:
                    rate = (stats["matches"] / stats["total"]) * 100
                    consistency_rates[model_name] = f"{rate:.1f}%"
                else:
                    consistency_rates[model_name] = "N/A"
            metrics["Consistency Rate (%)"] = consistency_rates

            all_results[judge_model_name] = {
                "models": models_list,
                "metrics": metrics,
            }

        return all_results

    @staticmethod
    def _parse_judge_run_name(name: str):
        """Parse a judge model name that may contain ::run_N suffix.

        Returns:
            Tuple of (base_name, run_index_or_None)
        """
        if "::run_" in name:
            base, suffix = name.rsplit("::run_", 1)
            try:
                return base, int(suffix)
            except ValueError:
                return name, None
        return name, None

    def _calculate_repeated_judge_aggregate(
        self, all_performance: Dict[str, Dict[str, Any]]
    ) -> Dict[str, Dict[str, Any]]:
        """Calculate aggregate performance across repeated judge runs.

        Groups ::run_* judge entries by base name. For each metric and model,
        computes mean and std across runs.

        Args:
            all_performance: Per-judge performance data from _calculate_performance_metrics

        Returns:
            Dictionary keyed by base judge name with aggregated metrics
        """
        from collections import defaultdict

        # Group by base judge name
        groups: Dict[str, List[str]] = defaultdict(list)
        for judge_name in all_performance:
            base, run_idx = self._parse_judge_run_name(judge_name)
            if run_idx is not None:
                groups[base].append(judge_name)

        aggregate = {}
        for base_judge, run_names in groups.items():
            if len(run_names) < 2:
                continue

            # Get models list from first run
            first_data = all_performance[run_names[0]]
            models_list = first_data["models"]

            agg_metrics = {}
            for metric_name in ["Macro Average (%)", "Micro Average (%)", "Consistency Rate (%)"]:
                mean_vals = {}
                std_vals = {}
                for model_name in models_list:
                    values = []
                    for rn in run_names:
                        val_str = all_performance[rn]["metrics"].get(metric_name, {}).get(model_name, "N/A")
                        if val_str != "N/A":
                            try:
                                values.append(float(val_str.rstrip("%")))
                            except (ValueError, AttributeError):
                                pass
                    if values:
                        mean_val = sum(values) / len(values)
                        mean_vals[model_name] = f"{mean_val:.1f}%"
                        if len(values) > 1:
                            variance = sum((v - mean_val) ** 2 for v in values) / (len(values) - 1)
                            std_val = variance ** 0.5
                            std_vals[model_name] = f"±{std_val:.1f}%"
                        else:
                            std_vals[model_name] = "N/A"
                    else:
                        mean_vals[model_name] = "N/A"
                        std_vals[model_name] = "N/A"
                agg_metrics[f"{metric_name} Mean"] = mean_vals
                agg_metrics[f"{metric_name} Std"] = std_vals

            # Also aggregate Lower and Upper bounds (just take from first run - they're the same)
            for metric_name in ["Lower", "Upper"]:
                vals = {}
                for model_name in models_list:
                    vals[model_name] = first_data["metrics"].get(metric_name, {}).get(model_name, "N/A")
                agg_metrics[metric_name] = vals

            aggregate[base_judge] = {
                "models": models_list,
                "metrics": agg_metrics,
            }

        return aggregate

    def _print_cost_metrics(self) -> None:
        """Print final cost metrics."""
        # Get summary from token tracker
        summary = self.token_tracker.get_summary()

        # Calculate total cost and prepare data
        total_cost = summary["total_cost"]
        cost_breakdown = summary["cost_breakdown"]
        total_tokens_data = summary["total_tokens"]

        # Prepare total tokens dict in the format expected by create_cost_breakdown_table
        total_tokens = {
            "prompt_tokens": total_tokens_data["prompt"],
            "completion_tokens": total_tokens_data["completion"],
            "total_tokens": total_tokens_data["total"],
        }

        # Prepare cost breakdown in the format expected by create_cost_breakdown_table
        formatted_cost_breakdown = {}
        if cost_breakdown:
            for model_name, costs in cost_breakdown.items():
                formatted_cost_breakdown[model_name] = {
                    "prompt_tokens": summary["model_usage"][model_name]["prompt"],
                    "completion_tokens": summary["model_usage"][model_name][
                        "completion"
                    ],
                    "total_cost": costs["total_cost"],
                }

        # Show detailed cost breakdown
        if formatted_cost_breakdown:
            cost_table = create_cost_breakdown_table(
                formatted_cost_breakdown, total_tokens, total_cost
            )
            console.print(cost_table)
            err_console.print()

    def _generate_report(self, json_files: List[Path], output_dir: Path) -> None:
        """Generate Excel report.

        Args:
            json_files: List of JSON file paths
            output_dir: Output directory
        """
        print_section("Generating Excel Summary Report")

        excel_path = output_dir / "grading_results.xlsx"
        generate_excel_report(
            self.file_data_map, json_files, excel_path, self.token_tracker
        )

        err_console.print()
        print_success(f"Excel Saved: {excel_path}")
        err_console.print()

        # Generate JSON report
        print_section("Generating JSON Summary Report")

        json_path = output_dir / "grading_results.json"
        generate_json_report(
            self.file_data_map, json_files, json_path, self.token_tracker
        )

        err_console.print()
        print_success(f"JSON Saved: {json_path}")
        err_console.print()
        print_section("")


def _discover_leaf_dirs(root: Path, pattern: str = "*.json") -> List[Path]:
    """Discover leaf directories that contain matching test files.

    Args:
        root: Root directory to scan recursively
        pattern: Glob pattern for test files

    Returns:
        Sorted list of directories containing test files
    """
    leaf_dirs = set()
    for json_file in root.rglob(pattern):
        leaf_dirs.add(json_file.parent)
    return sorted(leaf_dirs)


async def _run_single_dir(
    config: "Config",
    test_dir: Path,
    output_dir: Path,
    limit: Optional[int],
    overwrite: bool,
    grade_only: bool,
    dir_label: str,
) -> Tuple[str, bool, str]:
    """Run orchestrator for a single directory.

    Args:
        config: Configuration object
        test_dir: Directory containing test files
        output_dir: Output directory for this subdirectory
        limit: Maximum number of test questions per directory
        overwrite: Overwrite existing results
        grade_only: Only grade existing responses
        dir_label: Human-readable label for this directory

    Returns:
        Tuple of (dir_label, success, message)
    """
    orchestrator = Orchestrator(config)
    try:
        await orchestrator.run(
            test_dir,
            output_dir=output_dir,
            limit=limit,
            overwrite=overwrite,
            grade_only=grade_only,
        )
        return (dir_label, True, "OK")
    except Exception as e:
        return (dir_label, False, str(e))


def main(
    config_path: Optional[str] = None,
    dataset: Optional[str] = None,
    debug: bool = False,
    limit: Optional[int] = None,
    overwrite: bool = False,
    grade_only: bool = False,
    enable_search: bool = False,
    recursive: bool = False,
    detect_metadata: bool = False,
    sample_k: Optional[int] = None,
    repeated_judge: Optional[int] = None,
    _from_cli: bool = False,
) -> int:
    """Main entry point for omb.

    Args:
        config_path: Path to custom config file
        dataset: Path to dataset directory or single JSON file
        debug: Enable debug mode
        limit: Maximum number of test questions to process (selected sequentially)
        overwrite: Reperform and overwrite existing generation and grading results
        grade_only: Only grade existing responses, skip generation
        enable_search: Enable web search augmentation for generator models
        recursive: Scan subdirectories recursively
        detect_metadata: Auto-detect model metadata from OpenRouter API
        sample_k: Number of independent responses per generator model (overrides config)
        repeated_judge: Number of repeated judge runs per (model_response, judge_model) pair
        _from_cli: Internal flag indicating call originates from CLI (skip argparse)

    Returns:
        Exit code (0 for success, 1 for failure)
    """
    import argparse
    import os

    from . import __version__

    # Parse command-line arguments only when invoked directly (not via CLI)
    if not _from_cli and config_path is None and dataset is None:
        parser = argparse.ArgumentParser(
            prog="omb",
            description="omb - rubric-based auto grading system for LLM evaluation",
            epilog=(
                "examples:\n"
                "  omb --dataset ./data\n"
                "  omb --dataset ./data --grade-only\n"
                "  omb --dataset ./data --recursive --limit 10\n"
                "  omb --dataset ./data --verbose"
            ),
            formatter_class=argparse.RawDescriptionHelpFormatter,
        )
        parser.add_argument(
            "--version",
            "-V",
            action="version",
            version=f"%(prog)s {__version__}",
        )
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
        args = parser.parse_args()

        config_path = args.config
        dataset = args.dataset
        debug = args.debug or args.verbose
        limit = args.limit
        enable_search = args.enable_search
        overwrite = args.overwrite
        grade_only = args.grade_only
        recursive = args.recursive
        detect_metadata = args.detect_metadata
        sample_k = args.sample_k
        repeated_judge = args.repeated_judge

        # Handle --no-color and NO_COLOR env var
        if args.no_color or os.environ.get("NO_COLOR"):
            console.no_color = True
            err_console.no_color = True

        # Handle --quiet
        if args.quiet:
            from .utils.console import set_quiet

            set_quiet(True)
    # Load configuration
    from .config import Config, set_config

    config = Config(Path(config_path) if config_path else None)

    # Set debug mode if enabled
    if debug:
        config.set("DEBUG", True)

    # Set enable_search if enabled
    if enable_search:
        config.set("ENABLE_SEARCH", True)
        # Update generator models to include -with-search suffix
        models = config.generator_models
        new_models = [f"{m}-with-search" for m in models]
        config.set("GENERATOR_MODELS", new_models)

        if debug:
            print_info(f"Search enabled. Models updated: {new_models}")

    set_config(config)

    # Apply sample_k CLI override
    if sample_k is not None:
        if sample_k < 1:
            print_error("--repeat-sample must be >= 1")
            return ExitCode.INPUT_ERROR
        config.set("SAMPLE_K", sample_k)

    # Apply repeated_judge CLI override
    if repeated_judge is not None:
        if repeated_judge < 1:
            print_error("--repeat-judge must be >= 1")
            return ExitCode.INPUT_ERROR
        config.set("REPEATED_JUDGE", repeated_judge)

    # Auto-detect model metadata from OpenRouter if requested
    if detect_metadata and config.generator_models:
        from .clients.metadata import detect_model_metadata

        # Strip -with-search suffix for metadata lookup
        raw_models = [m.replace("-with-search", "") for m in config.generator_models]
        # Also include judge models for completeness
        all_models = list(set(raw_models + config.judge_models))

        print_info("Detecting model metadata from OpenRouter API...")
        try:
            metadata = detect_model_metadata(config.router_api_key, all_models)
            config.set_model_metadata(metadata)

            # Print metadata table
            err_console.print()
            metadata_table = create_metadata_table(
                metadata, all_models, config.max_tokens
            )
            console.print(metadata_table)
            err_console.print()

            undetected = [m for m in all_models if m not in metadata]
            if undetected:
                print_warning(
                    f"Metadata not found for: {', '.join(undetected)} (will use MAX_TOKENS={config.max_tokens})"
                )
        except Exception as e:
            print_warning(
                f"Failed to detect model metadata: {e}. Falling back to MAX_TOKENS={config.max_tokens}"
            )

    if debug:
        print_info("Debug mode enabled")
        print_info(f"Config: {config_path}")
        print_info(f"Test path: {dataset}")

    # Determine test directory and file
    test_dir = None
    test_file = None

    if dataset:
        test_path_obj = Path(dataset)
        if test_path_obj.is_file():
            test_file = test_path_obj
            test_dir = test_path_obj.parent
        elif test_path_obj.is_dir():
            test_dir = test_path_obj
        else:
            print_error(f"Path does not exist: {dataset}")
            return ExitCode.INPUT_ERROR
    else:
        # Use default directory
        test_dir = Path("datasets/ExpertBench-12.31/代码_Expertbench")
        if not test_dir.exists():
            print_error(f"Default test directory not found: {test_dir}")
            return ExitCode.INPUT_ERROR

    # --- Recursive mode ---
    if recursive:
        if test_file:
            print_error("--recursive cannot be used with a single file path")
            return ExitCode.INPUT_ERROR

        leaf_dirs = _discover_leaf_dirs(test_dir)
        if not leaf_dirs:
            print_error(f"No subdirectories with test files found under: {test_dir}")
            return ExitCode.INPUT_ERROR

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        base_output = Path(f"outputs/result_{timestamp}")

        err_console.print()
        print_header(
            "Recursive Mode",
            f"Found {len(leaf_dirs)} leaf directories under {test_dir}",
        )
        for d in leaf_dirs:
            rel = d.relative_to(test_dir)
            print_info(f"  • {rel}")
        err_console.print()

        async def _run_all():
            tasks = []
            for leaf in leaf_dirs:
                rel = leaf.relative_to(test_dir)
                out = base_output / rel
                label = str(rel)
                tasks.append(
                    _run_single_dir(
                        config, leaf, out, limit, overwrite, grade_only, label
                    )
                )
            return await asyncio.gather(*tasks, return_exceptions=True)

        try:
            results = asyncio.run(_run_all())
        except KeyboardInterrupt:
            print_warning("Interrupted by user")
            return ExitCode.INTERRUPTED

        # Summarize
        err_console.print()
        print_header("Recursive Run Summary", f"Output: {base_output}")
        has_failure = False
        for r in results:
            if isinstance(r, Exception):
                print_error(f"  ✗ (exception): {r}")
                has_failure = True
            else:
                label, ok, msg = r
                if ok:
                    print_success(f"{label}", prefix="  ✓")
                else:
                    print_error(f"  ✗ {label}: {msg}")
                    has_failure = True

        err_console.print()
        return ExitCode.PARTIAL_FAILURE if has_failure else ExitCode.SUCCESS

    # --- Normal (non-recursive) mode ---
    orchestrator = Orchestrator(config)

    try:
        asyncio.run(
            orchestrator.run(
                test_dir,
                test_file=test_file,
                limit=limit,
                overwrite=overwrite,
                grade_only=grade_only,
            )
        )
        return ExitCode.SUCCESS
    except KeyboardInterrupt:
        print_warning("Interrupted by user")
        return ExitCode.INTERRUPTED
    except Exception as e:
        print_error(str(e))
        if debug:
            raise
        return ExitCode.GENERAL_ERROR
