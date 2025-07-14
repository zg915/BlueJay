# Agentic Workflow System

This project implements a modular, agent-driven workflow for compliance/certification research using OpenAI Agents SDK and FastAPI.

## Features
- Agentic triage and routing
- Modular function tools (RAG, context, parallel queries, etc.)
- Guardrails and moderation
- Async PostgreSQL database
- Human-in-the-loop fallback

## Project Structure
```
src/
  api/
    endpoints.py         # FastAPI endpoints
    server.py            # FastAPI app
  agent_system/
    agents.py            # Agent classes/logic
    tools.py             # Function tools
    orchestration.py     # Workflow orchestration
    guardrails.py        # Moderation/validation
  config/
    settings.py          # Config, env vars
    logging_config.py    # Logging
  database/
    models.py            # SQLAlchemy models
    services.py          # DB access functions
  memory/
    memory_service.py    # Context fetching/storing
```

## Setup Instructions

1. **Clone the repo and navigate to the project directory**
2. **Create and activate a virtual environment**
   ```bash
   python -m venv venv
   source venv/bin/activate  # or venv\Scripts\activate on Windows
   ```
3. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```
4. **Copy and configure environment variables**
   ```bash
   cp env_example.txt .env
   # Edit .env with your API keys and DB URL
   ```
5. **Run the API server**
   ```bash
   uvicorn src.api.server:app --reload
   ```

## Testing
```bash
pytest
```

## License
MIT 