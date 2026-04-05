project=$1
cd "/Users/sirisurab/projects/dapi_poc/$project"

# Planner artifacts
rm -f TaskIndex.md
rm -rf tasks/

# Coder artifacts
rm -rf "${project}_pipeline/"
rm -rf tests/
rm -f eval_results.md
rm -f requirements.txt
rm -f README.md
rm -f Makefile
rm -f pytest.ini
rm -f mypy.ini
rm -f .mypy.ini
rm -f setup.cfg
rm -f pyproject.toml
rm -f .gitignore

# Deepagents runtime artifacts
rm -rf large_tool_results/
rm -rf conversation_history/

# Logs and cache
rm -rf logs/
find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null
find . -name "*.pyc" -delete 2>/dev/null

# Data pipeline outputs (preserve data/external)
rm -rf data/raw/* data/interim/* data/processed/*

# Editable install metadata
rm -rf "${project}_pipeline.egg-info"
