# System Architecture

This document describes the architecture of the **Rubric-based Auto Grading System** (ExpertBench). The system is designed to automate the evaluation of LLM responses against structured rubrics using a Judge LLM.

## Overview

The system operates as a CLI tool that:
1.  Scans a directory of test cases (JSON files containing prompts and rubrics).
2.  Generates responses from candidate models (if missing).
3.  Grades these responses using a "Judge" model against the defined rubrics.
4.  Aggregates results into updated JSON files and summary reports (Excel/JSON).

It relies heavily on asynchronous programming (`asyncio`) for concurrent processing of generation and grading tasks to maximize throughput.

## Class Diagram

The following diagram illustrates the key classes and modules in the system. The `GradingOrchestrator` is the central controller, managing configuration, state, and the execution workflow.

```mermaid
classDiagram
    class GradingOrchestrator {
        -Config config
        -TokenTracker token_tracker
        -Dict file_data_map
        -Semaphore semaphore
        +run(test_dir, output_dir, ...)
        -_run_workflow(json_files, ...)
        -scan_files(test_dir)
        -load_file_data(json_files)
        -collect_missing_models()
        -collect_existing_grading_data()
        -save_results()
    }

    class ConfigManager {
        +get_config()
        +get_model_config()
    }

    class TokenTracker {
        -Dict usage_stats
        +track_usage(model, prompt, completion)
        +get_summary()
    }

    class BaseLLMClient {
        <<Abstract>>
        -Config config
        -TokenTracker token_tracker
        +call(messages, model, ...)
        +update_token_usage()
    }

    class OpenRouterClient {
        +call()
    }

    class Ling1TClient {
        +call()
    }
    
    class QwenDeepResearchClient {
        +call()
    }

    %% Relationships
    GradingOrchestrator --> ConfigManager : uses
    GradingOrchestrator --> TokenTracker : owns
    
    BaseLLMClient <|-- OpenRouterClient
    BaseLLMClient <|-- Ling1TClient
    BaseLLMClient <|-- QwenDeepResearchClient

    %% Module Dependencies (Conceptual)
    GradingOrchestrator ..> ProcessingModule : calls functions
    GradingOrchestrator ..> ReportingModule : calls functions
    ProcessingModule ..> BaseLLMClient : instantiates

    note for ProcessingModule "Contains generic async functions:\n- generate_model_response\n- grade_single_model"
    note for ReportingModule "Contains reporting functions:\n- generate_excel_report\n- generate_json_report"
```

## Process Flow

The system follows a multi-phase workflow to ensure all models have responses and all responses are graded.

```mermaid
flowchart TD
    Start([Start CLI]) --> Init[Initialize Config & TokenTracker]
    Init --> Scan[Scan Directory for JSON Files]
    Scan --> Load[Load File Data into Memory]
    
    subgraph Planning [Task Planning]
        Load --> CheckGen[Identify Missing Generations]
        Load --> CheckGrade[Identify Ungraded Responses]
    end

    Planning --> Phase1[Phase 1: Concurrent Processing]

    subgraph Phase1 [Concurrent Generation & Grading]
        direction TB
        P1_Gen[Task: Generate Response]
        P1_Grade[Task: Grade Response]
        P1_Gen -- LLM Client --> P1_LLM((LLM API))
        P1_Grade -- Judge Client --> P1_Judge((Judge API))
    end

    Phase1 --> ProcessResults[Process & Store Results in Memory]
    
    ProcessResults --> CheckRetry{Failed Generations?}
    CheckRetry -- Yes --> Phase2[Phase 2: Retry Failed Tasks]
    Phase2 --> P2_Gen[Generate Retry] --> ProcessResults
    CheckRetry -- No --> CheckNew{New Responses Generated?}

    CheckNew -- Yes --> Phase3[Phase 3: Grade New Responses]
    Phase3 --> P3_Grade[Grade New Models] --> ProcessResults
    CheckNew -- No --> Save

    Save[Save Updated JSON Files] --> Report[Generate Excel & JSON Reports]
    Report --> End([End])

    style Phase1 fill:#f9f,stroke:#333,stroke-width:2px
    style Phase3 fill:#bbf,stroke:#333,stroke-width:2px
```

## Component Details

### 1. GradingOrchestrator
Located in `src/omb/orchestrator.py`. This class encapsulates the entire application logic. It maintains the state of all test files in `self.file_data_map`, which allows it to update results in-memory before writing them to disk.

### 2. Processing Module
Located in `src/omb/processing/`. Contains the core asynchronous functions:
*   `generate_model_response`: Handles prompting a generator model (e.g., via OpenRouter) to answer the question.
*   `grade_single_model`: Constructs a grading prompt containing the user query, model response, and rubric, then sends it to the Judge model to parse scores.

### 3. Clients
Located in `src/omb/clients/`. Abstracts the differences between various LLM providers. `BaseLLMClient` defines the interface, and subclasses handle specific API signatures (e.g., OpenRouter's OpenAI-compatible API, Ling1T's custom API).

### 4. Reporting
Located in `src/omb/reporting/`. Generates the final artifacts.
*   **Excel Report:** A comprehensive spreadsheet with color-coded scores, consistency checks, and cost breakdowns.
*   **JSON Report:** A machine-readable summary of the run.
