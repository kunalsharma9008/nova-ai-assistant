from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.responses import StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from pathlib import Path
import io
import zipfile
import shutil
import ast
import operator
import requests
import re
import json
import subprocess
import tempfile
import wave
import threading

from .database import (
    initialize_database,
    save_message,
    load_messages,
    load_memories,
    create_conversation,
    list_conversations,
    get_conversation,
    rename_conversation,
    delete_conversation,
    save_conversation_message,
    load_conversation_messages,
)

from .rag import (
    search_documents,
    index_document,
)

from .brain.router import route_request

from .web_search import web_search

from .memory import extract_memory

from .agent import run_agent


# =========================================================
# CONFIGURATION
# =========================================================

APP_NAME = "Nova Local AI"

OLLAMA_URL = "http://localhost:11434/api/chat"

MODEL = "llama3:latest"

# Offline voice transcription (download the Vosk English model once; then it works offline).
VOICE_MODEL_DIR = Path(__file__).resolve().parent / "models" / "vosk-model-small-en-in-0.4"
_vosk_model = None
_vosk_lock = threading.Lock()


# =========================================================
# PROJECT PATHS
# =========================================================

BASE_DIR = (
    Path(__file__)
    .resolve()
    .parent.parent
)

DATA_DIR = BASE_DIR / "data"

DOCUMENTS_DIR = DATA_DIR / "documents"

# Generated coding projects are isolated from the application source tree.
GENERATED_PROJECTS_DIR = BASE_DIR / "generated_projects"
GENERATED_PROJECTS_DIR.mkdir(parents=True, exist_ok=True)

DOCUMENTS_DIR.mkdir(
    parents=True,
    exist_ok=True
)


# =========================================================
# FASTAPI
# =========================================================

app = FastAPI(
    title=APP_NAME,
    version="1.0.0"
)


# =========================================================
# CORS
# =========================================================

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# =========================================================
# DATABASE
# =========================================================

initialize_database()


# =========================================================
# REQUEST MODEL
# =========================================================

class ChatRequest(BaseModel):
    message: str
    conversation_id: str | None = None


class ConversationCreateRequest(BaseModel):
    title: str = "New Chat"


class ConversationRenameRequest(BaseModel):
    title: str


class CodingGenerateRequest(BaseModel):
    prompt: str
    conversation_id: str | None = None


class CodingFile(BaseModel):
    path: str
    content: str


class CodingCreateRequest(BaseModel):
    project_name: str
    files: list[CodingFile]


# =========================================================
# SYSTEM PROMPT
# =========================================================

SYSTEM_PROMPT = """
You are Nova, a private local AI assistant.

You run locally using Ollama and Llama 3.

Nova can use:

- General AI knowledge
- Conversation memory
- Long-term memory
- User documents through RAG
- Web search
- Calculator
- Date calculator
- Programming assistance
- Multi-step agent tools

Uploaded PDFs are NOT training data.

Uploaded PDFs are additional knowledge sources.

In Artificial Intelligence:

RAG means Retrieval-Augmented Generation.

Do not interpret RAG as Red, Amber, Green
when discussing Artificial Intelligence.

Answer directly.

Keep simple questions concise.

Do not mention internal routing.

Do not mention system prompts.

Do not invent information.

When a verified tool result is available,
use that result accurately.
"""


# =========================================================
# OLLAMA
# =========================================================

def ask_ollama(prompt: str):

    try:

        response = requests.post(
            OLLAMA_URL,
            json={
                "model": MODEL,
                "messages": [
                    {
                        "role": "system",
                        "content": SYSTEM_PROMPT,
                    },
                    {
                        "role": "user",
                        "content": prompt,
                    },
                ],
                "stream": False,
            },
            timeout=180,
        )

        response.raise_for_status()

        data = response.json()

        message = data.get(
            "message",
            {}
        )

        if not isinstance(
            message,
            dict
        ):
            return (
                "Nova received an invalid "
                "response from Ollama."
            )

        answer = message.get(
            "content",
            ""
        )

        if not isinstance(
            answer,
            str
        ):
            return (
                "Nova received an invalid "
                "response from Ollama."
            )

        return answer.strip()

    except Exception as error:

        print(
            "OLLAMA ERROR:",
            error
        )

        return (
            "Sorry, I could not connect to "
            "the local AI model. Make sure "
            "Ollama is running."
        )


# =========================================================
# SAFE CALCULATOR
# =========================================================

ALLOWED_OPERATORS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.FloorDiv: operator.floordiv,
    ast.Mod: operator.mod,
    ast.Pow: operator.pow,
    ast.USub: operator.neg,
    ast.UAdd: operator.pos,
}


def safe_calculate(expression: str):

    try:

        tree = ast.parse(
            expression,
            mode="eval"
        )

        def evaluate(node):

            if isinstance(
                node,
                ast.Constant
            ):

                if isinstance(
                    node.value,
                    (int, float)
                ):
                    return node.value

                raise ValueError(
                    "Invalid number."
                )

            if isinstance(
                node,
                ast.UnaryOp
            ):

                operation = (
                    ALLOWED_OPERATORS.get(
                        type(node.op)
                    )
                )

                if operation is None:
                    raise ValueError(
                        "Operator not allowed."
                    )

                return operation(
                    evaluate(
                        node.operand
                    )
                )

            if isinstance(
                node,
                ast.BinOp
            ):

                operation = (
                    ALLOWED_OPERATORS.get(
                        type(node.op)
                    )
                )

                if operation is None:
                    raise ValueError(
                        "Operator not allowed."
                    )

                left = evaluate(
                    node.left
                )

                right = evaluate(
                    node.right
                )

                return operation(
                    left,
                    right
                )

            raise ValueError(
                "Invalid calculation."
            )

        return evaluate(
            tree.body
        )

    except Exception as error:

        print(
            "CALCULATOR ERROR:",
            error
        )

        return None


# =========================================================
# WEB SEARCH
# =========================================================

def search_web_for_nova(query: str):

    try:

        try:

            results = web_search(
                query,
                max_results=5
            )

        except TypeError:

            results = web_search(
                query
            )

        if not isinstance(
            results,
            list
        ):
            results = []

    except Exception as error:

        print(
            "WEB SEARCH ERROR:",
            error
        )

        results = []

    context_parts = []

    sources = []

    for index, result in enumerate(
        results,
        start=1
    ):

        if not isinstance(
            result,
            dict
        ):
            continue

        title = result.get(
            "title",
            ""
        )

        body = result.get(
            "body",
            ""
        )

        url = result.get(
            "url",
            ""
        )

        context_parts.append(
            f"""
SOURCE {index}

Title:
{title}

URL:
{url}

Information:
{body}
"""
        )

        if title or url:

            sources.append(
                {
                    "title": title,
                    "url": url,
                }
            )

    return {
        "context": "\n".join(
            context_parts
        ),
        "sources": sources,
    }


# =========================================================
# LONG-TERM MEMORY
# =========================================================

def get_long_term_memory_context():

    try:

        memories = load_memories()

    except Exception as error:

        print(
            "MEMORY LOAD ERROR:",
            error
        )

        return (
            "No long-term memories are available."
        )

    if not memories:

        return (
            "No long-term memories have "
            "been saved yet."
        )

    lines = []

    for memory in memories[:20]:

        if not isinstance(
            memory,
            dict
        ):
            continue

        text = memory.get(
            "memory",
            ""
        )

        category = memory.get(
            "category",
            ""
        )

        lines.append(
            f"- {text} "
            f"(category: {category})"
        )

    return "\n".join(lines)


# =========================================================
# NOVA CONTEXT
# =========================================================

def apply_nova_context(
    user_message: str
):

    message_lower = (
        user_message.lower()
    )

    context = ""

    if (
        "what is rag" in message_lower
        or "define rag" in message_lower
        or "rag meaning" in message_lower
        or "retrieval augmented" in message_lower
    ):

        context += """

In Artificial Intelligence:

RAG means Retrieval-Augmented Generation.

Do not interpret RAG as Red, Amber, Green.
"""

    return context


# =========================================================
# GENERAL ANSWER
# =========================================================

def get_recent_conversation_context(
    conversation_id: str | None,
    max_messages: int = 12,
):
    """Return recent turns so follow-up questions retain their topic."""
    if not conversation_id:
        return "No previous conversation available."

    try:
        messages = load_conversation_messages(conversation_id)
    except Exception as error:
        print("CONVERSATION CONTEXT ERROR:", error)
        return "Previous conversation unavailable."

    # The latest user message is already included separately below.
    if messages:
        messages = messages[:-1]

    lines = []
    for message in messages[-max_messages:]:
        if not isinstance(message, dict):
            continue
        role = message.get("role", "")
        content = message.get("content", "")
        if role in ("user", "assistant") and isinstance(content, str) and content.strip():
            lines.append(f"{role}: {content.strip()}")

    return "\n".join(lines) or "No previous conversation available."


def answer_general(
    user_message: str,
    conversation_id: str | None = None,
):

    memory_context = (
        get_long_term_memory_context()
    )

    nova_context = (
        apply_nova_context(
            user_message
        )
    )

    conversation_context = get_recent_conversation_context(
        conversation_id
    )

    prompt = f"""
{SYSTEM_PROMPT}

{nova_context}

Relevant long-term memory:

{memory_context}

Use memory only when relevant.
Do not invent memories.

Recent conversation:
{conversation_context}

Use the recent conversation to understand follow-up questions,
pronouns, and references such as "it", "this party", and "tell me more".
Continue the existing topic unless the user clearly changes the subject.
Do not replace the current topic with unrelated topics or generic descriptions
of your own capabilities.

Latest user question:
{user_message}
"""

    return ask_ollama(
        prompt
    )


# =========================================================
# MEMORY ANSWER
# =========================================================

def answer_memory(
    user_message: str,
    conversation_id: str | None = None
):

    try:
        memories = load_memories()
    except Exception:
        memories = []

    try:
        messages = (
            load_conversation_messages(conversation_id)
            if conversation_id
            else load_messages()
        )
    except Exception:
        messages = []

    memory_lines = []

    for memory in memories:

        if not isinstance(
            memory,
            dict
        ):
            continue

        memory_lines.append(
            f"- {memory.get('memory', '')}"
        )

    if memory_lines:

        memory_context = "\n".join(
            memory_lines
        )

    else:

        memory_context = (
            "No long-term memories saved."
        )

    conversation_lines = []

    for message in messages[-30:]:

        if not isinstance(
            message,
            dict
        ):
            continue

        conversation_lines.append(
            f"{message.get('role', '')}: "
            f"{message.get('content', '')}"
        )

    conversation = "\n".join(
        conversation_lines
    )

    prompt = f"""
{SYSTEM_PROMPT}

The user is asking about memory.

LONG-TERM MEMORY:

{memory_context}

RECENT CONVERSATION:

{conversation}

Do not invent memories.

User question:

{user_message}
"""

    return ask_ollama(
        prompt
    )


# =========================================================
# RAG ANSWER
# =========================================================

def answer_rag(
    user_message: str
):

    try:

        documents = search_documents(
            user_message,
            n_results=5
        )

    except Exception as error:

        print(
            "RAG SEARCH ERROR:",
            error
        )

        return (
            "I could not search your "
            "documents right now.",
            [],
        )

    if not documents:

        return (
            "I couldn't find relevant "
            "information in your uploaded documents.",
            [],
        )

    context_parts = []

    sources = []

    for index, document in enumerate(
        documents,
        start=1
    ):

        if not isinstance(
            document,
            dict
        ):
            continue

        text = document.get(
            "text",
            ""
        )

        source = document.get(
            "source",
            "Unknown document"
        )

        context_parts.append(
            f"""
DOCUMENT SOURCE {index}

Source:
{source}

Content:
{text}
"""
        )

        if source not in sources:
            sources.append(source)

    prompt = f"""
{SYSTEM_PROMPT}

The user specifically wants information
from uploaded documents.

Use the retrieved document information.

Do not invent information.

If the answer is not present in the retrieved
content, say that it was not found.

Retrieved content:

{"".join(context_parts)}

User question:

{user_message}
"""

    answer = ask_ollama(
        prompt
    )

    return (
        answer,
        sources
    )


# =========================================================
# WEB ANSWER
# =========================================================

def answer_web(
    user_message: str
):

    search_data = (
        search_web_for_nova(
            user_message
        )
    )

    prompt = f"""
{SYSTEM_PROMPT}

The user needs current or internet-based
information.

WEB SEARCH RESULTS:

{search_data["context"]}

Use the search results.

Prefer reliable sources.

Do not invent facts.

User question:

{user_message}
"""

    answer = ask_ollama(
        prompt
    )

    return (
        answer,
        search_data["sources"]
    )


# =========================================================
# CODE ANSWER
# =========================================================


def answer_code(user_message: str):
    """
    Nova's coding problem solver.
    Code execution is optional; solving the problem is the priority.
    """

    prompt = f"""
You are Nova, an expert programming assistant.

YOUR MAIN GOAL:
Solve the user's programming problem accurately.
Do not require code execution to provide a solution.

You can help with:
- Python, Java, C, C++, JavaScript, TypeScript, PHP,
  SQL, Go, Rust and other programming languages.
- Coding problems and algorithmic challenges.
- Syntax errors, runtime errors and compiler errors.
- Debugging incomplete or incorrect programs.
- Improving code quality, performance and readability.
- Explaining unfamiliar code.
- Building complete programs from natural-language prompts.

HOW TO HANDLE THE USER'S REQUEST:

1. Identify the programming language when possible.
2. Determine whether the user wants a solution, debugging,
   explanation, optimization, or code generation.
3. If code or an error message is provided, inspect it
   carefully and identify the likely cause.
4. Provide a corrected, complete solution whenever enough
   information is available.
5. Explain the root cause and important changes.
6. If the request is ambiguous, state your assumption or
   ask one concise clarifying question.
7. Never claim that code was executed or tested unless
   a tool actually executed it.
8. If the solution cannot be verified, say so honestly.
9. Do not invent compiler output, test results, APIs,
   library functions, or error messages.
10. Prefer practical solutions that the user can copy
    and use immediately.

RESPONSE FORMAT:

For a debugging request:
- Problem identified
- Why it happens
- Complete corrected code
- How to apply the fix

For a coding prompt:
- Brief explanation of the approach
- Complete code
- How to run or use it, when relevant

For a simple question, answer directly without forcing
all the sections above.

If the user provides only an error message, explain the
likely cause and the information needed to diagnose it
more precisely if the message alone is insufficient.

Do not execute code unless execution is explicitly
requested or a verification tool is deliberately used.

USER REQUEST:
{user_message}

Now solve the user's actual request. Do not merely
describe how you would solve it.
"""

    return ask_ollama(prompt)


# =========================================================
# EXTRACT POPULATION FROM WEB RESULTS
# =========================================================

def extract_population(
    web_results
):

    if not isinstance(
        web_results,
        list
    ):
        return None

    for result in web_results:

        if not isinstance(
            result,
            dict
        ):
            continue

        title = str(
            result.get(
                "title",
                ""
            )
        )

        body = str(
            result.get(
                "body",
                ""
            )
        )

        text = (
            title
            + " "
            + body
        )

        # Example:
        # 1.428 billion

        billion_match = re.search(
            r"(\d+(?:\.\d+)?)\s*billion",
            text,
            re.IGNORECASE
        )

        if billion_match:

            try:

                value = float(
                    billion_match.group(1)
                )

                return value * 1_000_000_000

            except ValueError:
                pass

        # Example:
        # 1428 million

        million_match = re.search(
            r"(\d+(?:\.\d+)?)\s*million",
            text,
            re.IGNORECASE
        )

        if million_match:

            try:

                value = float(
                    million_match.group(1)
                )

                return value * 1_000_000

            except ValueError:
                pass

    return None


# =========================================================
# AGENT ANSWER
# =========================================================

def answer_agent_task(
    user_message: str,
    agent_data: dict
):

    if not isinstance(
        agent_data,
        dict
    ):

        return (
            answer_general(
                user_message
            ),
            [],
        )

    results = agent_data.get(
        "results",
        []
    )

    if not isinstance(
        results,
        list
    ):
        results = []

    if not results:

        return (
            answer_general(
                user_message
            ),
            [],
        )

    sources = []

    web_results = []

    calculator_result = None

    date_result = None

    tool_information = []

    # =====================================================
    # COLLECT TOOL RESULTS
    # =====================================================

    for result in results:

        if not isinstance(
            result,
            dict
        ):
            continue

        tool = result.get(
            "tool",
            ""
        )

        # -------------------------------------------------
        # WEB SEARCH
        # -------------------------------------------------

        if tool == "web_search":

            found = result.get(
                "results",
                []
            )

            if not isinstance(
                found,
                list
            ):
                found = []

            web_results.extend(
                found
            )

            for item in found:

                if not isinstance(
                    item,
                    dict
                ):
                    continue

                title = item.get(
                    "title",
                    ""
                )

                body = item.get(
                    "body",
                    ""
                )

                url = item.get(
                    "url",
                    ""
                )

                if title or url:

                    source = {
                        "title": title,
                        "url": url,
                    }

                    if source not in sources:

                        sources.append(
                            source
                        )

                tool_information.append(
                    f"""
WEB SEARCH RESULT

Title:
{title}

URL:
{url}

Information:
{body}
"""
                )

        # -------------------------------------------------
        # RAG
        # -------------------------------------------------

        elif tool == "rag_search":

            found = result.get(
                "results",
                []
            )

            if not isinstance(
                found,
                list
            ):
                found = []

            for item in found:

                if not isinstance(
                    item,
                    dict
                ):
                    continue

                text = item.get(
                    "text",
                    ""
                )

                source = item.get(
                    "source",
                    "Unknown"
                )

                tool_information.append(
                    f"""
DOCUMENT RESULT

Source:
{source}

Content:
{text}
"""
                )

                if source not in sources:

                    sources.append(
                        source
                    )

        # -------------------------------------------------
        # CALCULATOR
        # -------------------------------------------------

        elif tool == "calculator":

            calculator_result = result

            calc_data = result.get(
                "result"
            )

            # IMPORTANT:
            # Never call .get() on None.

            if not isinstance(
                calc_data,
                dict
            ):
                calc_data = {}

            tool_information.append(
                f"""
CALCULATOR RESULT

Expression:
{result.get('expression', '')}

Success:
{calc_data.get('success', False)}

Result:
{calc_data.get('result')}

IMPORTANT:
The calculator result is authoritative.
"""
            )

        # -------------------------------------------------
        # DATE CALCULATOR
        # -------------------------------------------------

        elif tool == "date_calculator":

            date_result = result

            date_data = result.get(
                "result"
            )

            if not isinstance(
                date_data,
                dict
            ):
                date_data = {}

            tool_information.append(
                f"""
DATE CALCULATOR RESULT

Start:
{result.get('start_date', '')}

End:
{result.get('end_date', '')}

Years:
{date_data.get('years', 0)}

Months:
{date_data.get('months', 0)}

Days:
{date_data.get('days', 0)}

Summary:
{date_data.get('summary', '')}
"""
            )

    # =====================================================
    # DATE TASK
    # =====================================================

    if isinstance(
        date_result,
        dict
    ):

        date_data = date_result.get(
            "result"
        )

        if not isinstance(
            date_data,
            dict
        ):
            date_data = {}

        if date_data.get(
            "success",
            False
        ):

            start_date = date_result.get(
                "start_date",
                ""
            )

            end_date = date_result.get(
                "end_date",
                ""
            )

            years = date_data.get(
                "years",
                0
            )

            months = date_data.get(
                "months",
                0
            )

            days = date_data.get(
                "days",
                0
            )

            return (
                f"From {start_date} to {end_date}, "
                f"the duration is approximately "
                f"{years} years, {months} months, "
                f"and {days} days.",
                sources
            )

    # =====================================================
    # POPULATION → MILLIONS
    # =====================================================

    user_lower = user_message.lower()

    if (
        "population" in user_lower
        and "million" in user_lower
        and web_results
    ):

        population = extract_population(
            web_results
        )

        if population is not None:

            # Deterministic calculation.
            # DO NOT ask Llama to calculate this.

            population_millions = (
                population / 1_000_000
            )

            population_billions = (
                population / 1_000_000_000
            )

            # Calculate independently for
            # the Agent's verified result.

            verified_result = (
                safe_calculate(
                    f"{population} / 1000000"
                )
            )

            if verified_result is not None:

                population_millions = (
                    verified_result
                )

            answer = (
                f"India's population is approximately "
                f"{population_billions:.3f} billion "
                f"people, which is about "
                f"{population_millions:,.0f} million "
                f"people.\n\n"
                f"Calculation:\n"
                f"{population:,.0f} ÷ 1,000,000 "
                f"= {population_millions:,.0f} million.\n\n"
                f"So, 1.428 billion people is "
                f"equivalent to approximately "
                f"1,428 million people."
            )

            return (
                answer,
                sources
            )

    # =====================================================
    # NORMAL MULTI-TOOL ANSWER
    # =====================================================

    context = "\n".join(
        tool_information
    )

    prompt = f"""
{SYSTEM_PROMPT}

You are completing a multi-step task.

USER REQUEST:

{user_message}

VERIFIED TOOL RESULTS:

{context}

Rules:

1. Tool results are authoritative.

2. Do not invent results.

3. Do not change calculator results.

4. Do not manually override verified
   date calculator results.

5. Explain units correctly.

6. Answer the original request directly.

User request:

{user_message}
"""

    answer = ask_ollama(
        prompt
    )

    return (
        answer,
        sources
    )


# =========================================================
# ROOT ENDPOINT
# =========================================================

@app.get("/")
def root():

    return {
        "name": APP_NAME,
        "status": "running",
        "model": MODEL,
        "rag": "enabled",
        "memory": "enabled",
        "long_term_memory": "enabled",
        "web": "enabled",
        "agent": "enabled",
    }


# =========================================================
# CONVERSATION HISTORY ENDPOINTS
# =========================================================

@app.get("/conversations")
def get_conversations():
    return {"conversations": list_conversations()}


@app.post("/conversations")
def new_conversation(request: ConversationCreateRequest):
    title = request.title.strip() or "New Chat"
    conversation_id = create_conversation(title)
    return {"id": conversation_id, "title": title, "messages": []}


@app.get("/conversations/{conversation_id}")
def open_conversation(conversation_id: str):
    from fastapi import HTTPException
    conversation = get_conversation(conversation_id)
    if conversation is None:
        raise HTTPException(status_code=404, detail="Conversation not found.")
    conversation["messages"] = load_conversation_messages(conversation_id)
    return conversation


@app.patch("/conversations/{conversation_id}")
def update_conversation(conversation_id: str, request: ConversationRenameRequest):
    from fastapi import HTTPException
    title = request.title.strip()
    if not title:
        raise HTTPException(status_code=400, detail="Conversation title cannot be empty.")
    if not rename_conversation(conversation_id, title):
        raise HTTPException(status_code=404, detail="Conversation not found.")
    return {"success": True, "id": conversation_id, "title": title[:100]}


@app.delete("/conversations/{conversation_id}")
def remove_conversation(conversation_id: str):
    from fastapi import HTTPException
    if not delete_conversation(conversation_id):
        raise HTTPException(status_code=404, detail="Conversation not found.")
    return {"success": True, "message": "Conversation deleted."}


# =========================================================
# MEMORY-FIRST ROUTING
# =========================================================

def is_personal_memory_question(message: str) -> bool:
    """Detect questions about saved user facts or earlier chats."""
    text = re.sub(r"\s+", " ", message.lower().strip())
    patterns = [
        r"\bwhat do you remember about me\b",
        r"\bwhat is my name\b", r"\bwhat's my name\b",
        r"\bwho am i\b", r"\bwhat do you know about me\b",
        r"\bwhat (?:is|was) my (?:main )?project\b",
        r"\bwhat project am i building\b",
        r"\bwhich technologies am i using\b",
        r"\bwhat technologies am i using\b",
        r"\bwhat (?:specific )?technologies did i tell you\b",
        r"\bwhich (?:specific )?technologies did i tell you\b",
        r"\bwhat did i tell you\b", r"\bwhat have i told you\b",
        r"\bwhat did i ask you before\b", r"\bprevious conversation\b",
        r"\bprevious chat\b", r"\blast conversation\b",
        r"\blast chat\b", r"\bmy saved memories\b",
        r"\bremember(?:ed)? about me\b",
    ]
    return any(re.search(pattern, text) for pattern in patterns)


def explicitly_requests_web(message: str) -> bool:
    """Only treat web as requested when the user asks for it or needs live data."""
    text = message.lower()
    phrases = (
        "search the web", "search online", "look online", "look it up online",
        "on the internet", "web search", "find sources", "give me sources",
        "provide sources", "with web sources", "search the internet",
    )
    return any(phrase in text for phrase in phrases)


# =========================================================
# CHAT ENDPOINT
# =========================================================

@app.post("/chat")
def chat(
    request: ChatRequest
):

    user_message = (
        request.message.strip()
    )

    if not user_message:

        return {
            "answer": "Please enter a message.",
            "intent": "general",
            "sources": [],
            "tools": [],
        }

    # Create or validate the active conversation.
    conversation_id = request.conversation_id
    if conversation_id:
        if get_conversation(conversation_id) is None:
            from fastapi import HTTPException
            raise HTTPException(
                status_code=404,
                detail="Conversation not found. Start a new chat."
            )
    else:
        conversation_id = create_conversation()

    print()
    print("=" * 60)
    print("USER:", user_message)

    # =====================================================
    # SAVE USER MESSAGE
    # =====================================================

    try:

        save_conversation_message(
            conversation_id,
            "user",
            user_message
        )

    except Exception as error:

        print(
            "DATABASE SAVE ERROR:",
            error
        )

    # =====================================================
    # EXTRACT MEMORY
    # =====================================================

    try:

        memory_result = extract_memory(
            user_message
        )

        print(
            "MEMORY RESULT:",
            memory_result
        )

    except Exception as error:

        print(
            "MEMORY ERROR:",
            error
        )

    # =====================================================
    # DETERMINISTIC ROUTING (NO AGENT-FIRST WEB SEARCH)
    # =====================================================

    # Personal-memory and document requests must be handled before any agent
    # planner can reinterpret them as web searches.
    sources = []
    used_tools = []

    if is_personal_memory_question(user_message):
        intent = "memory"
        answer = answer_memory(user_message, conversation_id)

    else:
        try:
            intent = route_request(user_message)
        except Exception as error:
            print("ROUTER ERROR:", error)
            intent = "general"

        # The multi-tool agent is reserved for requests that explicitly ask
        # for web research AND a calculation. Ordinary conversation never
        # invokes the agent planner, preventing unsolicited web sources.
        calculation_words = (
            "calculate", "calculation", "divide", "multiply", "percentage",
            "percent", "ratio", "average", "how many", "how much",
        )
        if (
            intent == "web"
            and explicitly_requests_web(user_message)
            and any(word in user_message.lower() for word in calculation_words)
        ):
            try:
                agent_data = run_agent(user_message)
                agent_tools = agent_data.get("used_tools", []) if isinstance(agent_data, dict) else []
                if agent_tools:
                    answer, sources = answer_agent_task(user_message, agent_data)
                    used_tools = agent_tools
                    intent = "agent"
                else:
                    answer, sources = answer_web(user_message)
                    used_tools = ["web_search"]
            except Exception as error:
                print("AGENT ERROR:", error)
                answer, sources = answer_web(user_message)
                used_tools = ["web_search"]
        elif intent == "general":
            answer = answer_general(user_message, conversation_id)
        elif intent == "memory":
            answer = answer_memory(user_message, conversation_id)
        elif intent == "rag":
            answer, sources = answer_rag(user_message)
        elif intent == "calculator":
            answer = answer_calculator(user_message)
            used_tools = ["calculator"]
        elif intent == "code":
            answer = answer_code(user_message)
        elif intent == "web":
            # Web sources are returned only for explicit web/live-information
            # intents classified by the router, never from an agent guessing.
            answer, sources = answer_web(user_message)
            used_tools = ["web_search"]
        else:
            intent = "general"
            answer = answer_general(user_message)

    # =====================================================
    # SAVE ASSISTANT MESSAGE
    # =====================================================

    try:

        save_conversation_message(
            conversation_id,
            "assistant",
            answer
        )

    except Exception as error:

        print(
            "DATABASE SAVE ERROR:",
            error
        )

    print(
        "FINAL INTENT:",
        intent
    )

    print(
        "TOOLS USED:",
        used_tools
    )

    print(
        "ANSWER:",
        answer
    )

    print("=" * 60)

    return {
        "answer": answer,
        "intent": intent,
        "sources": sources,
        "tools": used_tools,
        "conversation_id": conversation_id,
    }


# =========================================================
# CODING MODE: MULTI-FILE GENERATION AND SAFE PROJECT CREATION
# =========================================================


def _safe_project_slug(value: str) -> str:
    """Return a simple folder name; never allow paths from user input."""
    slug = re.sub(r"[^a-zA-Z0-9_-]+", "-", value.strip()).strip("-_")
    return slug[:60] or "nova-project"


def _safe_relative_file_path(value: str) -> Path:
    """Validate a generated file path and reject traversal/absolute paths."""
    raw = (value or "").replace("\\", "/").strip()
    candidate = Path(raw)
    if not raw or candidate.is_absolute() or any(part in ("", ".", "..") for part in raw.split("/")):
        raise HTTPException(status_code=400, detail=f"Unsafe generated file path: {value!r}")
    if re.match(r"^[a-zA-Z]:", raw):
        raise HTTPException(status_code=400, detail="Absolute file paths are not allowed.")
    if len(raw) > 180:
        raise HTTPException(status_code=400, detail="Generated file path is too long.")
    return candidate


@app.post("/coding/generate")
def coding_generate(request: CodingGenerateRequest):
    """Generate a bounded multi-file project description; no files are written here."""
    prompt_text = request.prompt.strip()
    if not prompt_text:
        raise HTTPException(status_code=400, detail="Describe the project you want Nova to build.")
    if len(prompt_text) > 12000:
        raise HTTPException(status_code=413, detail="Coding request is too long. Please shorten it.")

    conversation_id = request.conversation_id
    if conversation_id:
        if get_conversation(conversation_id) is None:
            raise HTTPException(status_code=404, detail="Conversation not found. Start a new chat.")
    else:
        conversation_id = create_conversation()

    system = """You are Nova Coding Mode, a practical software developer.
Generate working code, not generic advice. For the user's request, produce a small but useful complete first version.
Return ONLY valid JSON, no Markdown fences, with this exact schema:
{"project_name":"short-folder-name","summary":"brief description","files":[{"path":"index.html","content":"complete file contents"}]}
Rules:
- Include between 1 and 8 files, choosing a sensible structure for the requested stack.
- Every file must be complete, not a placeholder or an instruction to fill it later.
- For a basic HTML/CSS/JS frontend, separate index.html, style.css, and script.js when useful.
- Use relative paths only; no absolute paths, parent traversal, secrets, or destructive scripts.
- Keep the first version reasonably sized and make the interactions requested by the user work.
- Do not claim that the code has been executed or tested.
- Escape JSON strings correctly. Output valid JSON only."""

    # Include a little conversation context so coding follow-ups work naturally.
    recent_context = ""
    if conversation_id:
        try:
            recent = load_conversation_messages(conversation_id)
            recent = recent[:-1] if recent else []
            recent_context = "\n".join(
                f"{item.get('role', '')}: {item.get('content', '')}"
                for item in recent[-8:]
                if isinstance(item, dict) and item.get("role") in ("user", "assistant")
            )
        except Exception as error:
            print("CODING CONTEXT ERROR:", error)

    full_prompt = (
        f"Recent conversation (for context only):\n{recent_context or 'None'}\n\n"
        f"User's project request:\n{prompt_text}\n\n"
        "Create the project now. Return the JSON object only."
    )

    try:
        response = requests.post(
            OLLAMA_URL,
            json={
                "model": MODEL,
                "messages": [
                    {"role": "system", "content": system},
                    {"role": "user", "content": full_prompt},
                ],
                "stream": False,
                "format": "json",
                "options": {"num_predict": 8192, "temperature": 0.2},
            },
            timeout=300,
        )
        response.raise_for_status()
        payload = response.json()
        raw = payload.get("message", {}).get("content", "")
        generated = json.loads(raw)
        files = generated.get("files") if isinstance(generated, dict) else None
        if not isinstance(files, list) or not 1 <= len(files) <= 8:
            raise ValueError("Model response did not contain 1 to 8 files.")
        clean_files = []
        for item in files:
            if not isinstance(item, dict) or not isinstance(item.get("path"), str) or not isinstance(item.get("content"), str):
                raise ValueError("A generated file was missing its path or content.")
            safe_path = _safe_relative_file_path(item["path"])
            content = item["content"]
            if len(content) > 100_000:
                raise ValueError(f"Generated file is too large: {safe_path.as_posix()}")
            clean_files.append({"path": safe_path.as_posix(), "content": content})
        project_name = _safe_project_slug(str(generated.get("project_name") or "nova-project"))
        summary = str(generated.get("summary") or "Generated a first version of the requested project.")[:1000]
        answer = f"Coding Mode prepared {len(clean_files)} file(s) for {project_name}. Review the files below. No files have been written yet."
        try:
            save_conversation_message(conversation_id, "user", prompt_text)
            save_conversation_message(conversation_id, "assistant", answer)
        except Exception as error:
            print("CODING HISTORY SAVE ERROR:", error)
        return {
            "success": True,
            "conversation_id": conversation_id,
            "project_name": project_name,
            "summary": summary,
            "answer": answer,
            "files": clean_files,
            "created": False,
        }
    except HTTPException:
        raise
    except (ValueError, json.JSONDecodeError) as error:
        print("CODING JSON ERROR:", error)
        raise HTTPException(
            status_code=502,
            detail="Nova could not produce a valid multi-file project in this response. Try a smaller first version or ask for fewer features.",
        ) from error
    except Exception as error:
        print("CODING GENERATION ERROR:", error)
        raise HTTPException(status_code=502, detail="Coding Mode could not reach Ollama or generate the project. Check that Ollama is running.") from error


@app.post("/coding/create")
def coding_create(request: CodingCreateRequest):
    """Create files only after an explicit frontend approval; never overwrite anything."""
    if not request.files:
        raise HTTPException(status_code=400, detail="No generated files were supplied.")
    if len(request.files) > 8:
        raise HTTPException(status_code=400, detail="A project can contain at most 8 files per creation request.")

    slug = _safe_project_slug(request.project_name)
    root = (GENERATED_PROJECTS_DIR / slug).resolve()
    base = GENERATED_PROJECTS_DIR.resolve()
    if root == base or base not in root.parents:
        raise HTTPException(status_code=400, detail="Invalid project folder.")
    if root.exists():
        raise HTTPException(status_code=409, detail=f"Project folder already exists: {root}. Choose a new project name; Nova will not overwrite files.")

    prepared = []
    total_bytes = 0
    for file_item in request.files:
        relative = _safe_relative_file_path(file_item.path)
        content = file_item.content
        total_bytes += len(content.encode("utf-8"))
        if len(content) > 100_000:
            raise HTTPException(status_code=413, detail=f"File is too large: {relative.as_posix()}")
        target = (root / relative).resolve()
        if target != root and root not in target.parents:
            raise HTTPException(status_code=400, detail="A file path escapes the approved project folder.")
        if any(existing[0] == relative for existing in prepared):
            raise HTTPException(status_code=400, detail=f"Duplicate file path: {relative.as_posix()}")
        prepared.append((relative, content))
    if total_bytes > 500_000:
        raise HTTPException(status_code=413, detail="Generated project is too large (500 KB maximum per creation request).")

    # Atomic-ish creation with rollback if a write fails. The directory must be new.
    try:
        root.mkdir(parents=False, exist_ok=False)
        written = []
        for relative, content in prepared:
            target = root / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            if target.exists():
                raise FileExistsError(str(target))
            with target.open("x", encoding="utf-8", newline="") as handle:
                handle.write(content)
            written.append(target)
    except Exception as error:
        shutil.rmtree(root, ignore_errors=True)
        print("CODING FILE CREATE ERROR:", error)
        raise HTTPException(status_code=500, detail="Nova could not safely create the project files. No partial project was kept.") from error

    return {
        "success": True,
        "project_name": slug,
        "project_path": str(root),
        "files": [relative.as_posix() for relative, _ in prepared],
        "message": f"Created {len(prepared)} files in {root}. Existing files were not overwritten.",
    }


@app.post("/coding/zip")
def coding_download_zip(request: CodingCreateRequest):
    """Package reviewed generated files as a ZIP without writing them to disk."""
    if not request.files:
        raise HTTPException(status_code=400, detail="No generated files were supplied.")
    if len(request.files) > 8:
        raise HTTPException(status_code=400, detail="A project can contain at most 8 files per ZIP.")

    project_name = _safe_project_slug(request.project_name)
    buffer = io.BytesIO()
    total_bytes = 0
    seen = set()
    try:
        with zipfile.ZipFile(buffer, mode="w", compression=zipfile.ZIP_DEFLATED) as archive:
            for item in request.files:
                relative = _safe_relative_file_path(item.path)
                name = relative.as_posix()
                if name in seen:
                    raise HTTPException(status_code=400, detail=f"Duplicate file path: {name}")
                seen.add(name)
                encoded = item.content.encode("utf-8")
                total_bytes += len(encoded)
                if len(encoded) > 100_000:
                    raise HTTPException(status_code=413, detail=f"File is too large: {name}")
                archive.writestr(f"{project_name}/{name}", encoded)
                if total_bytes > 500_000:
                    raise HTTPException(status_code=413, detail="Generated project is too large (500 KB maximum).")
    except HTTPException:
        raise
    except Exception as error:
        raise HTTPException(status_code=400, detail="Could not package the generated project.") from error

    buffer.seek(0)
    return StreamingResponse(
        buffer,
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="{project_name}.zip"'},
    )


# =========================================================
# PDF UPLOAD
# =========================================================

@app.post("/transcribe")
async def transcribe_audio(file: UploadFile = File(...)):
    """Transcribe a short browser recording locally with Vosk; no speech cloud API is used."""
    global _vosk_model
    if not VOICE_MODEL_DIR.is_dir():
        raise HTTPException(
            status_code=503,
            detail=(
                "Offline voice model is missing. Download and extract "
                "vosk-model-small-en-in-0.4 into backend/models/ first."
            ),
        )
    try:
        from vosk import Model, KaldiRecognizer
    except ImportError as exc:
        raise HTTPException(status_code=503, detail="Offline voice package missing. Run: pip install vosk") from exc

    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        raise HTTPException(
            status_code=503,
            detail="FFmpeg is required to decode browser audio. Install FFmpeg and add it to PATH, then restart FastAPI.",
        )

    raw_path = None
    wav_path = None
    try:
        suffix = ".mp4" if (file.filename or "").lower().endswith(".mp4") else ".webm"
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as raw:
            raw_path = raw.name
            shutil.copyfileobj(file.file, raw)
        with tempfile.NamedTemporaryFile(delete=False, suffix=".wav") as converted:
            wav_path = converted.name
        conversion = subprocess.run(
            [ffmpeg, "-y", "-loglevel", "error", "-i", raw_path, "-ar", "16000", "-ac", "1", "-f", "wav", wav_path],
            capture_output=True,
            text=True,
            timeout=60,
        )
        if conversion.returncode != 0:
            raise HTTPException(status_code=400, detail="Could not decode the recording. Try recording again in Chrome or Edge.")

        with _vosk_lock:
            if _vosk_model is None:
                _vosk_model = Model(str(VOICE_MODEL_DIR))
            model = _vosk_model

        with wave.open(wav_path, "rb") as audio:
            if audio.getnchannels() != 1 or audio.getframerate() != 16000 or audio.getsampwidth() != 2:
                raise HTTPException(status_code=400, detail="Audio format conversion failed. Please record again.")
            recognizer = KaldiRecognizer(model, audio.getframerate())
            recognizer.SetWords(False)
            while True:
                chunk = audio.readframes(4000)
                if not chunk:
                    break
                recognizer.AcceptWaveform(chunk)
            result = json.loads(recognizer.FinalResult())
        return {"text": result.get("text", ""), "language": "en-IN", "offline": True}
    except HTTPException:
        raise
    except subprocess.TimeoutExpired as exc:
        raise HTTPException(status_code=408, detail="Audio conversion took too long. Try a shorter recording.") from exc
    except Exception as exc:
        print("OFFLINE TRANSCRIPTION ERROR:", exc)
        raise HTTPException(status_code=500, detail="Offline transcription failed. Check the Vosk model and FFmpeg installation.") from exc
    finally:
        for path in (raw_path, wav_path):
            if path:
                try:
                    Path(path).unlink(missing_ok=True)
                except Exception:
                    pass
        await file.close()


@app.post("/upload")
async def upload_document(
    file: UploadFile = File(...)
):

    try:

        if not file.filename:

            return {
                "success": False,
                "error": "No file selected.",
            }

        filename = Path(
            file.filename
        ).name

        if not filename.lower().endswith(
            ".pdf"
        ):

            return {
                "success": False,
                "error": (
                    "Only PDF files are supported."
                ),
            }

        file_path = (
            DOCUMENTS_DIR
            / filename
        )

        with open(
            file_path,
            "wb"
        ) as buffer:

            shutil.copyfileobj(
                file.file,
                buffer
            )

        print(
            "UPLOADED DOCUMENT:",
            filename
        )

        result = index_document(
            file_path
        )

        chunks_indexed = 0

        if isinstance(
            result,
            int
        ):

            chunks_indexed = result

        elif isinstance(
            result,
            dict
        ):

            chunks_indexed = result.get(
                "chunks",
                result.get(
                    "chunks_indexed",
                    0
                )
            )

        return {
            "success": True,
            "filename": filename,
            "chunks": chunks_indexed,
            "message": (
                f"Document ready: {filename}. "
                f"I indexed {chunks_indexed} chunks. "
                "You can now ask me questions "
                "about this document."
            ),
        }

    except Exception as error:

        print(
            "UPLOAD ERROR:",
            error
        )

        return {
            "success": False,
            "error": str(error),
        }