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
- **Extensible:** Easily add new agents, tools, or data sources

---

## 🛠️ Technology Stack

- **Backend:** FastAPI, SQLAlchemy (async), PostgreSQL
- **AI/Agents:** OpenAI Agents SDK, GPT-4, Perplexity API
- **Streaming:** Server-Sent Events (SSE) via FastAPI StreamingResponse
- **Session Management:** Custom session manager with asyncio.Event for cancellation
- **Testing:** pytest

---

## 📦 Project Structure

```
BlueJay/
├── src/
│   ├── agent_system/          # Agent definitions, orchestration, session manager
│   ├── api/                   # FastAPI endpoints and server
│   ├── config/                # Prompts and output schemas
│   ├── database/              # Models and async services
│   ├── memory/                # Conversation memory/context
│   └── tests/                 # Test files
├── requirements.txt           # Python dependencies
├── README.md                  # This file
```

---

## ⚡ Quickstart

### 1. Clone & Setup
```sh
git clone <repository-url>
cd BlueJay
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### 2. Configure Environment
Create a `.env` file in the root:
```
DB_HOST=localhost
DB_PORT=5432
DB_NAME=tic_research
DB_USER=postgres
DB_PASSWORD=your_password
OPENAI_API_KEY=your_openai_api_key
PERPLEXITY_API_KEY=your_perplexity_api_key
```

### 3. Initialize Database
```sh
python init_database.py
```

### 4. Run the Server
```sh
uvicorn src.api.server:app --reload --host 0.0.0.0 --port 8000
```

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
- **Orchestrator:** Manages agent handoff, streaming, and cancellation.

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
  - `src/config/output_structure.py` — `Certifications_Structure` (Output schema)

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
  - Edit `src/config/prompts.py` and `src/config/output_structure.py`

---

## 🧰 Troubleshooting

- **Check logs** for errors and workflow traces
- **Verify environment variables** are set correctly
- **Test database connection** with `python test_db_connection.py`
- **Use `/health` endpoint** to verify server is running

---

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/your-feature`)
3. Commit your changes
4. Push to your branch
5. Open a Pull Request

---

## 📝 License

This project is licensed under the MIT License.

---

**BlueJay** — Real-time, agentic compliance research with streaming and cancellation. 