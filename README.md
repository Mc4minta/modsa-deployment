# MOD-SA (KMUTT Student Affairs AI Assistant)

MOD-SA is an AI-powered chatbot designed to help new students at King Mongkut's University of Technology Thonburi (KMUTT) with student affairs questions. It uses **RAG (Retrieval-Augmented Generation)** to provide accurate, context-aware answers based on official university documents.

## 🛠️ Technology Stack

**Backend (API & RAG Pipeline):**
- **FastAPI**: High-performance Python web framework for the API.
- **LangChain**: Orchestrates the RAG pipeline (Retrieval, Prompting, LLM execution).
- **ChromaDB**: Local vector database for storing and searching document embeddings.
- **Ollama**: Local proxy for running LLMs (Language Models) and Embedding Models.
  - *Embedding Model:* `bge-m3:latest`
  - *LLM (Chat):* `minimax-m3:cloud` (or other compatible models like Llama 3.1)

**Frontend (Web Interface):**
- **React + Vite**: Fast, modern frontend library and build tool.
- **Vanilla CSS**: Custom styling with a modern glassmorphism design system.
- **Context API**: Handles language switching (English/Thai).

---

## 🚀 Getting Started (Run from Scratch)

Follow these steps to run the complete project on your local machine. You will need to open **two terminal windows**.

### Prerequisites
1. **Python 3.10+**: For running the backend.
2. **Node.js (v20.19+)**: For running the production-oriented frontend.
3. **Ollama**: Installed and running on your machine (for AI models).

### Step 1: Prepare the AI Models (Ollama)
Ensure Ollama is running, then download the necessary models:
```bash
ollama pull bge-m3:latest
# Note: minimax-m3:cloud is a custom proxy. If you don't have it, you can edit backend_new/.env 
# and change LLM_MODEL to a model you have locally, e.g.:
# ollama pull llama3.1:8b 
```

### Step 2: Start the Backend (Terminal 1)
The backend handles document indexing and answers questions on port `8000`.

```bash
cd backend_new

# 1. Create a virtual environment
python -m venv .venv

# 2. Install dependencies (using the virtual environment's pip)
# On Windows:
.venv\Scripts\python -m pip install -r requirements.txt
# On macOS/Linux:
# .venv/bin/python -m pip install -r requirements.txt

# 3. Setup environment variables
# On Windows:
copy .env.example .env
# On macOS/Linux:
# cp .env.example .env

# 4. Run the server
# On Windows:
.venv\Scripts\python -m uvicorn main:app --reload --host 127.0.0.1 --port 8000
# On macOS/Linux:
# .venv/bin/python -m uvicorn main:app --reload --host 127.0.0.1 --port 8000
```
*Note: On the first run, the backend will take a few moments to read the documents in `backend_old/chunks` and index them into ChromaDB.*

### Step 3: Start the Frontend (Terminal 2)
The frontend provides the premium chat interface for users on port `5173`.

```bash
cd frontend/1.2tongtong

# 1. Install dependencies
npm ci

# 2. Setup environment variables
# On Windows:
copy .env.example .env
# On macOS/Linux:
# cp .env.example .env

# 3. Start the development server
npm run dev
```

### Step 4: Use the Application
Open your web browser and navigate to: **http://localhost:5173**

---

## 📁 Project Structure

- `backend_new/`: FastAPI backend containing RAG logic, ChromaDB setup, and API endpoints.
- `frontend/1.1wolf/`: Preserved frontend imported from branch `wolf`.
- `frontend/1.2tongtong/`: Production-oriented React UI, tests, and deployment configuration.
- `backend_old/chunks/`: Prepared JSON document chunks used as the knowledge base for RAG.
- `docs/`: Architecture and development guides.
