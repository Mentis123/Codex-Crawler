#!/bin/bash

# Create a directory for the export
mkdir -p codex_crawler_export

# Copy all Python files and directories
cp -r *.py codex_crawler_export/
cp -r agents codex_crawler_export/
cp -r utils codex_crawler_export/
cp -r .streamlit codex_crawler_export/ 2>/dev/null || echo "No .streamlit directory found"
cp -r data codex_crawler_export/ 2>/dev/null || echo "No data directory found"

# Copy README and any other documentation
cp README.md codex_crawler_export/

# Create a requirements list (since we can't modify requirements.txt directly)
echo "# Required packages for Codex Crawler
beautifulsoup4>=4.12.3
docx2txt>=0.8
llama-index-core>=0.12.12
llama-index>=0.12.12
llama-index-readers-web>=0.3.5
llama-index-embeddings-openai>=0.3.1
openai>=1.60.0
pandas>=2.2.3
psutil>=6.1.1
pypdf>=5.1.0
pytz>=2024.2
pyyaml>=6.0.2
reportlab>=4.2.5
requests>=2.32.3
serpapi>=0.1.5
streamlit>=1.41.1
trafilatura>=2.0.0
twilio>=9.4.5
openpyxl>=3.1.5" > codex_crawler_export/requirements.txt

# Create a .gitignore file
echo "# Byte-compiled / optimized / DLL files
__pycache__/
*.py[cod]
*$py.class

# Distribution / packaging
dist/
build/
*.egg-info/

# Virtual environments
venv/
env/
ENV/

# IDE files
.idea/
.vscode/

# Jupyter Notebook
.ipynb_checkpoints

# Local development settings
.env
.env.local

# Database files
*.db
*.sqlite3

# Logs
logs/
*.log

# Cache files
.cache/
.pytest_cache/

# Articles database
articles.db" > codex_crawler_export/.gitignore

echo "Export prepared in the codex_crawler_export directory"
echo "Files ready for GitHub upload:"
find codex_crawler_export -type f | sort