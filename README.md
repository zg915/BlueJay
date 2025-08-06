# BlueJay - Agentic Workflow System

A modular, agent-driven workflow system for compliance and certification research, featuring real-time streaming, robust cancellation, and extensible agent orchestration.

---

## 🚀 Overview

BlueJay is an intelligent backend system that routes user queries to specialized workflow agents for compliance, certification, and research tasks. It leverages OpenAI's Agents SDK, FastAPI, and async streaming to deliver real-time, structured results with support for user-initiated cancellation.

---

## 🏗️ Key Features

- **Agentic Orchestration:** Triage agent routes queries to specialized agents (Certification, Answer, etc.)
- **Real-Time Streaming:** Results are streamed to the client as soon as they are produced (certification-wise or message-wise)
- **User-Initiated Cancellation:** Users can cancel any in-progress workflow via a `/stop` endpoint
- **Session Management:** Each workflow session is tracked and can be cancelled or cleaned up
- **Parallel Search:** Multi-source research (web, RAG, DB) for comprehensive answers
- **Database Integration:** Async SQLAlchemy/PostgreSQL for persistent chat, session, and research data
- **Agent Tracing:** Comprehensive execution monitoring with Langfuse for debugging and optimization
- **Extensible:** Easily add new agents, tools, or data sources
- **Containerized:** Docker setup for consistent development and deployment environments

---

## 🛠️ Technology Stack

- **Backend:** FastAPI, SQLAlchemy (async), PostgreSQL
- **AI/Agents:** OpenAI Agents SDK, GPT-4, Perplexity API
- **Streaming:** Server-Sent Events (SSE) via FastAPI StreamingResponse
- **Session Management:** Custom session manager with asyncio.Event for cancellation
- **Containerization:** Docker & Docker Compose for development and deployment
- **Vector DB:** Weaviate for knowledge base operations
- **Observability:** Langfuse for agent execution tracing and monitoring

---

## 📦 Project Structure

```
BlueJay/
├── src/
│   ├── agent_system/          # Agent definitions, orchestration, session manager
│   │   ├── agents/           # Specialized agents (Certification, Answer, Flashcard, Triage)
│   │   ├── orchestration/    # Main orchestrator, operations, and streaming
│   │   │   ├── orchestration.py    # Main workflow orchestrator
│   │   │   ├── operations.py       # Business logic operations
│   │   │   └── streaming.py        # Streaming utilities
│   │   ├── tools/            # Function tools for agents
│   │   └── guardrails/       # Input validation and moderation
│   ├── api/                   # FastAPI endpoints and server
│   ├── config/                # Configuration modules
│   │   ├── langfuse_config.py      # Langfuse tracing setup
│   │   ├── prompts.py              # Agent prompts and instructions
│   │   └── schemas.py              # Output schemas and data models
│   └── services/              # Self-contained service modules (organized by data source)
│       ├── database_service.py     # Simplified database operations
│       ├── database_service_archive.py # Archived unused database functions
│       ├── perplexity_service.py   # Perplexity API integration
│       ├── knowledgebase_service.py # Knowledge base/Weaviate operations
│       └── models.py               # SQLAlchemy database models
├── requirements.txt           # Python dependencies
├── Dockerfile                 # Docker image definition
├── docker-compose.yml         # Docker Compose configuration
├── .dockerignore             # Docker build context exclusions
├── env_example.txt           # Environment variables template
└── README.md                 # This file
```

---

## ⚡ Quickstart

### 🐳 Docker Setup (Recommended)

**1. Clone & Configure Environment**
```sh
git clone <repository-url>
cd BlueJay

# Copy and configure environment variables
cp env_example.txt .env
# Edit .env with your AWS PostgreSQL, Weaviate, and API credentials
```

**2. Start with Docker Compose**
```sh
# Start BlueJay (connects to your existing AWS services)
docker-compose up

# Or run in background
docker-compose up -d

# View logs
docker-compose logs -f bluejay-app
```

**3. Access BlueJay**
- API: http://localhost:8000
- Health Check: http://localhost:8000/health
- API Docs: http://localhost:8000/docs

**4. Stop Services**
```sh
docker-compose down
```

### 🐍 Local Python Setup (Alternative)

**1. Clone & Setup Virtual Environment**
```sh
git clone <repository-url>
cd BlueJay
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt
```

**2. Configure Environment**
```sh
cp env_example.txt .env
# Edit .env with your AWS database and API credentials
```

**3. Run the Server**
```sh
uvicorn src.api.server:app --reload --host 0.0.0.0 --port 8000
```

---

## 🔗 External Dependencies

### Weaviate Vector Database
BlueJay connects to an external Weaviate instance for knowledge base operations and compliance research.

**Required Environment Variables:**
```env
WEAVIATE_URL=https://your-weaviate-cluster.aws.com
WEAVIATE_API_KEY=your_api_key_here
```

**Schema Documentation:**
- **URL Whitelist Schema** - [url_whitelist.md](https://github.com/zg915/weaviate/blob/main/url_whitelist.md)  
  Trusted sources for compliance and certification information
- **Compliance Artifacts Schema** - [compliance_artifacts.md](https://github.com/zg915/weaviate/blob/main/compliance_artifacts.md)  
  Regulatory documents, standards, and certification requirements

### PostgreSQL Database
BlueJay requires a PostgreSQL database for session management and chat history.

**Required Environment Variables:**
```env
DB_HOST=your-aws-rds-endpoint
DB_PORT=5432
DB_NAME=tic_research
DB_USER=postgres
DB_PASSWORD=your_password
```

### Langfuse Observability (Optional)
BlueJay integrates with Langfuse for comprehensive agent execution tracing, providing insights into agent performance, token usage, and workflow debugging.

**Optional Environment Variables:**
```env
LANGFUSE_PUBLIC_KEY=pk-lf-your_public_key_here
LANGFUSE_SECRET_KEY=sk-lf-your_secret_key_here
LANGFUSE_HOST=https://cloud.langfuse.com
```

**Key Features:**
- **Agent Execution Tracing:** Monitor each agent's decision-making process
- **Token Usage Tracking:** Track API costs and optimize performance  
- **Workflow Debugging:** Visualize multi-agent interactions and handoffs
- **Performance Analytics:** Identify bottlenecks and optimization opportunities

---

## 🌐 API Usage

### **Streaming Chat**
**POST** `/ask/stream`
```json
{
  "session_id": "test-session-1",
  "content": "List all certifications required to export lip balm from India to USA"
}
```
- **Response:** Server-Sent Events (SSE), each event is a JSON object (certification, message, or status)

### **Cancel a Workflow**
**POST** `/stop`
```json
{
  "session_id": "test-session-1"
}
```
- **Effect:** Immediately cancels the workflow and streaming for the given session.

### **Other Endpoints**
- `/ask` — Non-streaming chat
- `/health` — Health check
- `/sessions` — Create session
- `/sessions/{session_id}/history` — Get session history

---

## 🧩 How Streaming & Cancellation Work

- **Session Manager:** Each streaming request creates a `WorkflowContext` (with an `asyncio.Event`) tracked by session ID.
- **Streaming:** The orchestrator yields results (certification-wise or message-wise) as soon as they are produced by the agent.
- **Cancellation:**
  - User calls `/stop` with the session ID.
  - The session manager sets the cancellation event.
  - The orchestrator detects this and stops streaming, yielding a cancellation message.
- **Client Disconnect:** If the client disconnects (browser reloads, etc.), the server cancels the streaming generator and cleans up the session.

---

## 🧠 Agentic Workflow

- **Triage Agent:** Classifies user queries and hands off to the appropriate specialized agent.
- **CertificationAgent:** Handles certification/compliance queries, streams each certification as soon as available.
- **AnswerAgent:** Handles general Q&A, streams formatted answers.
- **FlashcardAgent:** Generates structured flashcards for certifications.
- **Orchestrator:** Manages agent handoff, streaming, and cancellation.

## 🏛️ Architecture Overview

BlueJay follows a clean, modular architecture with clear separation of concerns:

### Services Layer (`src/services/`)
- **Self-contained modules** organized by data source (database, perplexity, knowledgebase)
- **Plain functions** for simplicity and testability  
- **No internal dependencies** - each service is the final destination for its functionality
- **Simplified and optimized** - unused functions archived, internal redirects eliminated
- **Direct implementations** - moved from wrapper pattern to actual functionality

### Operations Layer (`src/agent_system/orchestration/operations.py`)
- **Business logic functions** that orchestrate multiple service calls
- **Workflow coordination** for complex multi-step processes
- **Plain functions** that combine services to achieve business goals

### Orchestration Layer (`src/agent_system/orchestration/orchestration.py`)
- **Main workflow coordinator** that manages agent interactions
- **Streaming and session management**
- **Error handling and cancellation logic**

---

## 🔧 Recent Architecture Improvements

The BlueJay codebase has been significantly refactored to improve maintainability and eliminate complexity:

### Function Organization Refactoring
- **Eliminated `internal.py`** - Removed the redirect wrapper pattern that added unnecessary complexity
- **Services by Data Source** - Functions organized into `database_service.py`, `perplexity_service.py`, and `knowledgebase_service.py`
- **Self-Contained Services** - Each service contains full implementation with no further redirects
- **Database Simplification** - Reduced active database service by 48% (3,494 bytes vs 6,716 bytes archived)

### Cleanup and Optimization
- **Removed Obsolete Directories**: `src/knowledgebase/`, `src/memory/`, `src/database/`
- **Archived Unused Functions**: 64% of database functions moved to `database_service_archive.py`
- **Consolidated Models**: Moved `models.py` into services directory for better organization
- **Direct Function Calls**: Eliminated internal function redirects for better performance

### Observability and Monitoring (New in Traces Branch)
- **Langfuse Integration**: Added comprehensive agent execution tracing with automatic OpenAI Agents SDK instrumentation
- **Enhanced Configuration**: New `langfuse_config.py` module for centralized observability setup
- **Environment Support**: Docker Compose and environment template updated with tracing variables
- **Silent Operation**: Tracing runs in background without cluttering terminal output
- **Performance Optimization**: Fixed dependency issues and improved service reliability

### Benefits
- **Reduced Complexity**: Clear function ownership and no redirect chains
- **Better Maintainability**: Functions organized by their data source
- **Improved Performance**: Direct function calls without wrappers
- **Enhanced Debugging**: Full visibility into agent execution workflows
- **Easier Testing**: Self-contained services with clear boundaries

---

## 🔍 Detailed Workflow Descriptions

### 1. Triage Agent
- **Role:** First point of contact for all user queries.
- **Function:** Analyzes the user's message and determines which specialized agent (CertificationAgent or AnswerAgent) should handle the request.
- **Streaming:** Streams a handoff event indicating which agent will process the query.
- **Cancellation:** If cancelled during triage, the workflow stops before any specialized agent is invoked.
- **Key Code:**
  - `src/agent_system/orchestration.py` — `WorkflowOrchestrator.triage_agent` (Agent instantiation and handoff logic)
  - `src/config/prompts.py` — `TRIAGE_AGENT_INSTRUCTION` (Prompt for triage agent)

### 2. CertificationAgent
- **Role:** Handles all queries related to getting a comprehensive list of certifications, compliance, and regulatory requirements.
- **Function:**
  - Generates multiple targeted search queries based on the user's product and scenario.
  - Runs parallel domain and web searches for each query.
  - Aggregates, deduplicates, and normalizes certification results.
  - **Streaming:** As soon as each certification is parsed from the agent's output, it is streamed to the client as a separate event (certification-wise streaming).
  - **Cancellation:** If the user cancels, streaming stops immediately and a cancellation message is sent.
- **Key Code:**
  - `src/agent_system/agents/certification.py` — `CertificationAgent` class
  - `src/agent_system/orchestration.py` — Certification streaming logic in `handle_user_question` and `_extract_cert_objs`
  - `src/config/prompts.py` — `CERTIFICATION_AGENT_INSTRUCTION` (Prompt for certification agent)
  - `src/config/schemas.py` — `Flashcards_Structure` (Output schema)

### 3. AnswerAgent
- **Role:** Handles general compliance, regulatory, and informational queries.
- **Function:**
  - Uses compliance and web search tools to gather information.
  - Synthesizes a structured, formatted answer (Markdown, headings, summary, etc.).
  - **Streaming:** Streams the answer as soon as it is generated (can be chunked or as a single message, depending on agent output).
  - **Cancellation:** If the user cancels, streaming stops and a cancellation message is sent.
- **Key Code:**
  - `src/agent_system/agents/answer.py` — `AnswerAgent` class
  - `src/agent_system/orchestration.py` — Streaming logic in `handle_user_question`
  - `src/config/prompts.py` — `ANSWER_AGENT_INSTRUCTION` (Prompt for answer agent)

### 4. Orchestrator
- **Role:** Central router and workflow manager.
- **Function:**
  - Handles pre-processing (validation, moderation, context loading).
  - Runs the triage agent and manages handoff to specialized agents.
  - Manages streaming: yields each result (certification, message, or status) as soon as it is available.
  - Checks for cancellation before yielding each result, ensuring immediate stop if requested.
  - Handles client disconnects and session cleanup.
- **Key Code:**
  - `src/agent_system/orchestration.py` — `WorkflowOrchestrator` class, especially `handle_user_question`
  - `src/agent_system/session_manager.py` — `WorkflowSessionManager` and `WorkflowContext` (cancellation/session state)
  - `src/api/endpoints.py` — `chat_stream` (API streaming endpoint)
  - `src/api/server.py` — `/ask/stream` and `/stop` endpoints

---

## 📝 Extending BlueJay

- **Add a new agent:**
  - Create a new agent class in `src/agent_system/agents/`
  - Register it in the orchestrator
  - Add handoff logic in the triage agent
- **Add new tools/data sources:**
  - Implement in `src/agent_system/tools/`
  - Register with agents as needed
- **Customize prompts/output:**
  - Edit `src/config/prompts.py` and `src/config/schemas.py`

---

## 🧰 Troubleshooting

### Docker Issues
- **Logs not showing:** Check `docker-compose logs -f bluejay-app`
- **Port conflicts:** Change port in docker-compose.yml (e.g., `"8001:8000"`)
- **Environment variables:** Verify `.env` file exists and has correct AWS credentials
- **Database connection:** Ensure AWS PostgreSQL allows connections from your IP

### General Issues  
- **Health check:** Visit http://localhost:8000/health
- **API documentation:** Check http://localhost:8000/docs for interactive API docs
- **Rebuild image:** Run `docker-compose up --build` to rebuild after dependency changes

### Development Commands
```sh
# Rebuild Docker image
docker-compose build --no-cache

# View container logs  
docker-compose logs -f

# Access container shell
docker-compose exec bluejay-app bash

# Stop and remove containers
docker-compose down --volumes
```

---

## 📋 Recent Updates

### v0.0.1 - Agent Observability Implementation (August 2025)

**Branch**: `traces` (merged from `compliance-artifact`)

**Technical Changes**:
- **Added Langfuse tracing integration** (`src/config/langfuse_config.py`)
  - OpenAI Agents SDK instrumentation with `logfire.instrument_openai_agents()`
  - Async-compatible tracing with `nest_asyncio.apply()`
  - Silent operation mode (console output disabled)
- **Updated dependencies** (`requirements.txt`)
  - `langfuse` - Agent execution tracing
  - `logfire` - OpenTelemetry instrumentation 
  - `nest_asyncio` - Async compatibility
  - `protobuf>=5.29.0,<6.0.0` - Protocol buffer support
- **Enhanced Docker configuration** (`docker-compose.yml`)
  - Added Langfuse environment variables
  - Optional tracing configuration
- **Service reliability improvements**
  - Fixed dependency resolution issues in orchestration layer
  - Optimized Perplexity service imports

**Environment Variables** (Optional):
```
LANGFUSE_PUBLIC_KEY, LANGFUSE_SECRET_KEY, LANGFUSE_HOST
```

**Backward Compatibility**: Full - existing deployments unaffected without Langfuse credentials.

---

**BlueJay** — Real-time, agentic compliance research with streaming and cancellation. 