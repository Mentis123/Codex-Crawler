# Codex Crawler

An AI-powered news aggregation system that intelligently collects and analyzes AI-related news from multiple online sources.

## Features

- Automated AI news discovery and aggregation
- Intelligent content evaluation and ranking
- Business-focused article takeaways
- Multiple export formats (PDF, CSV, Excel)
- Modular agent-based architecture for easy customization

## Technology Stack

- Python 3.11
- Streamlit web interface
- LlamaIndex for document processing
- OpenAI (gpt-4o) for intelligent analysis
- SerpAPI for news gathering
- Trafilatura for web content extraction
- Pandas for data analysis

## Setup and Installation

1. Clone this repository
2. Install dependencies: `pip install -r requirements.txt`
3. Set required environment variables:
   - `OPENAI_API_KEY`: Your OpenAI API key
   - `SERPAPI_API_KEY`: Your SerpAPI key
4. Run the application: `streamlit run main.py`

The first run automatically generates a `config.default.json` file with the
baseline settings if it is missing. This file is ignored by Git.

If you need to restore the default configuration, run `python scripts/reset_config.py` from the repository root.

## Project Structure

- `agents/`: Modular agent components
  - `base_agent.py`: Foundation class for all agents
  - `crawler_agent.py`: Handles article discovery and extraction
  - `analyzer_agent.py`: Processes and validates article content
  - `report_agent.py`: Generates reports and exports
  - `orchestrator.py`: Coordinates the workflow
- `utils/`: Utility functions and helpers
- `main.py`: Main Streamlit application
- `main_agent_based.py`: New agent-based architecture implementation
## License

codex/create-tests-directory-and-add-unit-tests
MIT

## Testing

Run unit tests with `pytest`:

```bash
pip install -r requirements.txt
pip install pytest
pytest
```
