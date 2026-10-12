# Nova AI Assistant 🤖

**A local AI assistant for coding, learning, document understanding, and productivity.**

Nova is a personal AI assistant built with Python, FastAPI, Next.js, and Ollama. It aims to provide an interactive chat experience with local AI capabilities, memory, document retrieval, and productivity tools.

## ✨ Features

- **AI Chat:** Interact with an AI model through a web interface.
- **Local AI:** Use Ollama to run a supported language model locally.
- **Document Understanding:** Retrieve relevant information from supported documents using RAG.
- **Conversation Memory:** Store and retrieve conversation history.
- **Web Search:** Access web-search functionality through the backend.
- **Calculator:** Perform calculations using a dedicated tool.
- **Coding Assistance:** Get help with programming and code-related tasks.
- **Modern Interface:** Use a Next.js frontend to interact with Nova.

> Feature availability depends on the current implementation and configuration.

## 🛠️ Tech Stack

| Technology | Purpose |
|---|---|
| Python | Backend logic |
| FastAPI | Backend API |
| Ollama | Local AI model runtime |
| Next.js | Web interface |
| TypeScript | Frontend development |
| SQLite | Local database |
| RAG | Document retrieval |

## 📁 Project Structure

```text
Ai chatbot/
├── backend/
│   ├── agent.py
│   ├── api.py
│   ├── database.py
│   ├── main.py
│   ├── memory.py
│   ├── rag.py
│   ├── web_search.py
│   ├── brain/
│   └── tools/
├── frontend/
│   ├── app/
│   │   ├── api/
│   │   ├── globals.css
│   │   ├── layout.tsx
│   │   └── page.tsx
│   ├── package.json
│   └── package-lock.json
├── .gitignore
└── README.md
```

## ⚙️ Requirements

- Python
- Node.js and npm
- Git
- Ollama
- The language model configured by the backend

## 🚀 Getting Started

### 1. Clone the repository

```bash
git clone https://github.com/kunalsharma9008/nova-ai-assistant.git
cd nova-ai-assistant
```

### 2. Set up the Python backend

Create a virtual environment from the project root:

```bash
python -m venv .venv
```

Activate it in Windows PowerShell:

```powershell
.\.venv\Scripts\Activate.ps1
```

Install the backend dependencies using the project's dependency file, if one is provided. If no dependency file exists, install the required packages listed by the project before starting the backend.

### 3. Set up Ollama

Install Ollama and download the model required by your backend configuration.

For example, if your backend is configured to use `llama3:latest`:

```bash
ollama pull llama3:latest
```

### 4. Start the backend

From the project root, run:

```bash
python -m uvicorn backend.api:app --reload --host 0.0.0.0 --port 8000
```

This assumes `backend/api.py` exposes a FastAPI application named `app` and the required dependencies are installed.

### 5. Start the frontend

Open another terminal:

```bash
cd frontend
npm install
npm run dev
```

Open the frontend in your browser:

http://localhost:3000

## 🔐 Security

- Never commit API keys, passwords, or private credentials.
- Keep secrets in environment variables and exclude `.env` files from Git.
- Review uploaded documents and local database files before publishing.
- Review code-execution functionality carefully before exposing the application to other users.

## 🎯 Project Goal

Nova aims to bring AI chat, programming assistance, document retrieval, and productivity tools together in one application, with a focus on local AI capabilities.

## 👨‍💻 Author

**Kunal Sharma**

GitHub: [@kunalsharma9008](https://github.com/kunalsharma9008)

---

*Nova AI Assistant — built as a learning and development project.*
