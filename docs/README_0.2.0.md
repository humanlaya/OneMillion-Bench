# Auto Grading System V2 - Refactored

A modular auto-grading system for evaluating large language model responses using configurable rubrics and multiple API providers.

## 🏗️ Architecture

The system has been refactored into a modular architecture with the following components:

```
evals/
├── config/                 # Configuration management
│   ├── __init__.py        # ConfigManager class
│   └── default.yaml       # Default configuration
├── api_clients/           # API client implementations
│   ├── __init__.py        # APIClientFactory
│   ├── base.py           # Base API client class
│   ├── openrouter.py     # OpenRouter API client
│   ├── qwen.py           # Qwen DeepSearch client
│   └── ling1t.py         # Ling-1T API client
├── cost_tracking/         # Token usage and cost calculation
│   └── __init__.py        # TokenTracker class
├── grading/              # Grading logic and prompt templates
│   ├── __init__.py        # Main grading functions
│   ├── prompts.py         # Prompt templates
│   └── parser.py          # Response parsing utilities
├── reporting/            # Excel report generation
│   └── __init__.py        # ExcelReportGenerator class
├── file_processing/      # JSON file operations
│   └── __init__.py        # FileProcessor class
└── orchestrator.py       # Main workflow orchestration
```

## 🚀 Quick Start

### 1. Installation

```bash
# Install dependencies
pip install -r requirements.txt

# Set up environment variables
export DASHSCOPE_API_KEY="your_dashscope_key"  # For Qwen models
```

### 2. Configuration

Copy and customize the configuration:

```bash
cp evals/config/default.yaml evals/config/my_config.yaml
# Edit my_config.yaml with your API keys and model preferences
```

### 3. Usage

```bash
# Process all files with default configuration
python auto_grading.py

# Process a single test file
python auto_grading.py test_file.json

# Use custom configuration
python auto_grading.py --config evals/config/my_config.yaml

# Validate configuration
python auto_grading.py --validate-config

# List configured models
python auto_grading.py --list-models
```

## ⚙️ Configuration

The system uses YAML configuration files in `evals/config/`. Key sections:

### API Configuration
```yaml
api:
  router:
    base_url: "https://openrouter.ai/api/v1/chat/completions"
    api_key: "your_openrouter_key"
  ling:
    base_url: "https://api.tbox.cn/api/llm/v1/chat/completions"
    api_key: "your_ling_key"
  proxy: null  # Optional proxy configuration
```

### Model Configuration
```yaml
models:
  teacher: "google/gemini-3-pro-preview"  # Model for grading
  reference_models:  # Models with existing human scores
    - "gpt5_high_search"
  models_to_generate:  # Models to generate responses for
    - "anthropic/claude-opus-4.5"
```

### Request Configuration
```yaml
request:
  temperature: 0.0
  max_tokens: 128000
  timeout: 600
  retry_times: 3
  retry_delay: 1
  max_concurrent: 50
  reasoning_effort: "low"
```

### Pricing Configuration
```yaml
pricing:
  "anthropic/claude-opus-4.5":
    input: 5.0    # USD per 1M tokens
    output: 25.0
  default:
    input: 10.0   # Default pricing for unknown models
    output: 30.0
```

## 🔧 Key Features

### Modular Architecture
- **Separation of Concerns**: Each module handles a specific responsibility
- **Easy Extension**: Add new API clients or grading strategies easily
- **Configuration Management**: Centralized YAML-based configuration
- **Type Safety**: Full type hints throughout the codebase

### API Client Support
- **OpenRouter**: Support for multiple LLM providers
- **Qwen DeepSearch**: Specialized research-oriented responses
- **Ling-1T**: Independent API endpoint support
- **Tool Integration**: GPT-5 with web search, Gemini with Google search

### Advanced Features
- **Concurrent Processing**: Configurable concurrency limits
- **Token Tracking**: Detailed cost analysis and reporting
- **Error Handling**: Robust retry mechanisms with exponential backoff
- **Progress Tracking**: Real-time progress reporting
- **Excel Reports**: Comprehensive result analysis

### Grading System
- **Flexible Rubrics**: Support for positive and negative scoring
- **Human Comparison**: Consistency analysis with human scores
- **JSON Parsing**: Robust parsing of LLM grading responses
- **Binary Scoring**: Clear hit/miss evaluation logic

## 📊 Output

The system generates:

1. **Updated JSON Files**: Results saved to timestamped output directory
2. **Excel Reports**:
   - Summary sheet with model scores and consistency rates
   - Cost analysis sheet with detailed token usage
3. **Console Logs**: Real-time progress and cost tracking
4. **Missing Model Reports**: Lists of incomplete evaluations

## 🔄 Migration from V1

The refactored system maintains backward compatibility with the original data format while providing:

- **Cleaner Code**: Better organization and maintainability
- **Enhanced Configuration**: YAML-based configuration management
- **Improved Error Handling**: More robust error recovery
- **Better Testing**: Modular components enable easier unit testing
- **Performance**: Optimized concurrent processing

## 🐛 Troubleshooting

### Configuration Issues
```bash
# Validate your configuration
python auto_grading.py --validate-config

# Check model configuration
python auto_grading.py --list-models
```

### API Errors
- Ensure API keys are correctly set in configuration
- Check network connectivity and proxy settings
- Verify model names match provider specifications

### Memory Issues
- Reduce `max_concurrent` in configuration
- Process files in smaller batches
- Monitor system resources during execution

## 🤝 Contributing

1. Follow the modular architecture patterns
2. Add type hints for all new functions
3. Update configuration schema when adding new features
4. Add comprehensive error handling
5. Update documentation and examples

## 📝 License

This project maintains the same license as the original auto_grading.py script.