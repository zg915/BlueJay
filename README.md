# BlueJay - Agentic Workflow System

A sophisticated, modular agent-driven workflow system for compliance and certification research, built with FastAPI, SQLAlchemy, and OpenAI's Agents SDK.

## 🚀 Overview

BlueJay is an intelligent system that automatically routes user queries to specialized workflow agents, providing comprehensive research and certification information. The system uses a triage agent to classify queries and hand off to appropriate workflow agents for detailed processing.

### Key Features

- **Intelligent Query Classification**: Automatic routing of queries to specialized agents
- **Multi-Source Research**: Parallel web search, RAG API integration, and database lookups
- **Real-time Streaming**: FastAPI-based streaming responses
- **Comprehensive Logging**: Detailed debugging and monitoring capabilities
- **Modular Architecture**: Easy to extend with new workflow agents
- **Database Integration**: Persistent storage with SQLAlchemy and PostgreSQL

## 🏗️ Architecture

### System Components

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   API Layer     │    │  Orchestration  │    │  Workflow       │
│   (FastAPI)     │───▶│   (Triage +     │───▶│   Agents        │
│                 │    │   Handoffs)     │    │                 │
└─────────────────┘    └─────────────────┘    └─────────────────┘
                                │
                                ▼
                       ┌─────────────────┐
                       │   OpenAI        │
                       │   Processing    │
                       └─────────────────┘
```

### Agent Hierarchy

1. **Triage Agent**: Classifies queries and routes to appropriate workflow
2. **Certification Workflow Agent**: Handles certification and compliance queries
3. **Research Workflow Agent**: Handles general research and information queries

### Data Flow

1. **User Input** → API Endpoint
2. **Pre-hooks** → Input validation, moderation, database storage
3. **Triage Agent** → Query classification and handoff
4. **Workflow Agent** → Specialized processing (certification/research)
5. **OpenAI Processing** → Result synthesis and deduplication
6. **Response** → Formatted output to user

## 🛠️ Technology Stack

- **Backend**: FastAPI, SQLAlchemy, PostgreSQL
- **AI/ML**: OpenAI GPT-4, OpenAI Agents SDK
- **Search**: Perplexity API, RAG API integration
- **Database**: PostgreSQL with async support
- **Logging**: Comprehensive debugging and monitoring
- **Testing**: pytest, async testing support

## 📋 Prerequisites

- Python 3.8+
- PostgreSQL 12+
- OpenAI API key
- Perplexity API key (optional)
- RAG API access (optional)

## 🚀 Installation

### 1. Clone the Repository

```bash
git clone <repository-url>
cd BlueJay
```

### 2. Create Virtual Environment

```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

### 3. Install Dependencies

```bash
pip install -r requirements.txt
```

### 4. Environment Configuration

Create a `.env` file in the root directory:

```env
# Database Configuration
DB_HOST=localhost
DB_PORT=5432
DB_NAME=tic_research
DB_USER=postgres
DB_PASSWORD=your_password

# OpenAI Configuration
OPENAI_API_KEY=your_openai_api_key

# Optional APIs
PERPLEXITY_API_KEY=your_perplexity_api_key
RAG_API_URL=your_rag_api_url
RAG_API_KEY=your_rag_api_key

# Server Configuration
HOST=0.0.0.0
PORT=8000
DEBUG=True
```

### 5. Database Setup

```bash
# Initialize database
python init_database.py

# Test database connection
python test_db_connection.py
```

### 6. Start the Server

```bash
# Development mode
uvicorn src.api.server:app --reload --host 0.0.0.0 --port 8000

# Production mode
uvicorn src.api.server:app --host 0.0.0.0 --port 8000
```

## 📚 API Documentation

### Base URL
```
http://localhost:8000
```

### Available Endpoints

#### 1. Health Check
```http
GET /health
```

#### 2. Create Session
```http
POST /sessions
Content-Type: application/json

{
  "user_id": "user123",
  "session_name": "My Session"
}
```

#### 3. Streaming Chat
```http
POST /chat/stream
Content-Type: application/json

{
  "user_id": "user123",
  "session_id": "session456",
  "message": "List all certifications required to export electronics from India to the US"
}
```

#### 4. Simple Chat
```http
POST /chat/simple
Content-Type: application/json

{
  "user_id": "user123",
  "session_id": "session456",
  "message": "What is ISO 9001 certification?"
}
```

#### 5. Get Session History
```http
GET /sessions/{session_id}/history
```

### Response Formats

#### Streaming Response
```json
{
  "status": "complete",
  "response": "Based on the search results, here are the required certifications..."
}
```

#### Simple Chat Response
```json
{
  "response": "ISO 9001 is a quality management system standard...",
  "question_type": "research",
  "enhanced_query": "ISO 9001 quality management system certification details"
}
```

## 🔧 Configuration

### Agent Configuration

The system uses several configuration files:

- `src/config/prompts.py`: Agent prompts and instructions
- `src/agent_system/agents.py`: Workflow agent definitions
- `src/agent_system/orchestration.py`: Main orchestration logic

### Database Models

Key database models in `src/database/models.py`:

- `ChatMessage`: Stores user messages and responses
- `Session`: Manages user sessions
- `ResearchRequest`: Tracks research requests
- `Summary`: Stores conversation summaries

## 🧪 Testing

### Run Tests
```bash
# Run all tests
pytest

# Run specific test file
pytest tests/test_api_endpoints.py

# Run with coverage
pytest --cov=src
```

### Test Database Connection
```bash
python test_db_connection.py
```

## 📊 Monitoring and Logging

The system includes comprehensive logging:

- **Request/Response Logging**: All API calls are logged
- **Agent Execution Logging**: Detailed agent workflow tracking
- **Error Logging**: Full stack traces for debugging
- **Performance Logging**: Timing information for parallel operations

### Log Levels
- `DEBUG`: Detailed debugging information
- `INFO`: General operational information
- `WARNING`: Warning messages
- `ERROR`: Error messages with stack traces

## 🔄 Workflow Examples

### Certification Query Example

**Input**: "List all certifications required to export electronics from India to the US"

**Flow**:
1. Triage Agent classifies as "certification"
2. Uses `transfer_to_certification_workflow` handoff
3. Certification Workflow Agent executes:
   - Generates multiple search queries
   - Performs parallel web searches
   - Searches RAG API for domain-specific information
   - Queries internal database
   - Combines and deduplicates results
4. OpenAI processes results for final synthesis
5. Returns structured certification list

### Research Query Example

**Input**: "What is the difference between ISO 9001 and ISO 14001?"

**Flow**:
1. Triage Agent classifies as "research"
2. Uses `transfer_to_research_workflow` handoff
3. Research Workflow Agent executes:
   - Performs comprehensive web research
   - Gathers information from multiple sources
   - Synthesizes detailed comparison
4. Returns comprehensive research response

## 🚀 Deployment

### Docker Deployment

```dockerfile
FROM python:3.9-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . .
EXPOSE 8000

CMD ["uvicorn", "src.api.server:app", "--host", "0.0.0.0", "--port", "8000"]
```

### Environment Variables for Production

```env
# Production Database
DB_HOST=your_production_db_host
DB_PORT=5432
DB_NAME=tic_research_prod
DB_USER=your_db_user
DB_PASSWORD=your_secure_password

# Production OpenAI
OPENAI_API_KEY=your_production_openai_key

# Security
SECRET_KEY=your_secret_key
DEBUG=False
```

## 🔧 Development

### Project Structure

```
BlueJay/
├── src/
│   ├── agent_system/          # Agent definitions and orchestration
│   ├── api/                   # FastAPI endpoints and server
│   ├── config/                # Configuration and prompts
│   ├── database/              # Database models and services
│   ├── memory/                # Memory and context management
│   └── services/              # External service integrations
├── tests/                     # Test files
├── requirements.txt           # Python dependencies
├── init_database.py          # Database initialization
├── test_db_connection.py     # Database connection test
└── README.md                 # This file
```

### Adding New Workflow Agents

1. Create new agent class in `src/agent_system/agents.py`
2. Add handoff configuration in `src/agent_system/orchestration.py`
3. Update triage agent prompt in `src/config/prompts.py`
4. Add corresponding workflow method in orchestrator

### Extending the System

- **New Data Sources**: Add to `src/agent_system/tools.py`
- **New Agent Types**: Extend base Agent class
- **New API Endpoints**: Add to `src/api/endpoints.py`
- **New Database Models**: Add to `src/database/models.py`

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## 📝 License

This project is licensed under the MIT License - see the LICENSE file for details.

## 🆘 Support

For support and questions:

1. Check the logs for detailed error information
2. Review the API documentation at `/docs` when server is running
3. Test database connection with `python test_db_connection.py`
4. Verify environment variables are correctly set

## 🔮 Roadmap

- [ ] Add more specialized workflow agents
- [ ] Implement caching for improved performance
- [ ] Add user authentication and authorization
- [ ] Create web-based admin interface
- [ ] Add support for file uploads and document processing
- [ ] Implement real-time collaboration features
- [ ] Add analytics and usage tracking
- [ ] Create mobile API endpoints

## 📄 Changelog

### v1.0.0
- Initial release with triage agent and workflow system
- FastAPI-based API with streaming support
- PostgreSQL integration with async support
- OpenAI Agents SDK integration
- Comprehensive logging and debugging

---

**BlueJay** - Intelligent Agentic Workflow System for Compliance Research 