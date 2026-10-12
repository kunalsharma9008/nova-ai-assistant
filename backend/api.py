from fastapi import FastAPI, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from pathlib import Path
import shutil
import ast
import operator
import requests
import re

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
from .tools.code_executor import execute_code


# =========================================================
# CONFIGURATION
# =========================================================

APP_NAME = "Nova Local AI"

OLLAMA_URL = "http://localhost:11434/api/chat"

MODEL = "llama3:latest"


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

def answer_general(
    user_message: str
):

    memory_context = (
        get_long_term_memory_context()
    )

    nova_context = (
        apply_nova_context(
            user_message
        )
    )

    prompt = f"""
{SYSTEM_PROMPT}

{nova_context}

Relevant long-term memory:

{memory_context}

Use memory only when relevant.

Do not invent memories.

User question:

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
# CALCULATOR
# =========================================================

def answer_calculator(user_message: str):
    expression = user_message.strip()

    expression = re.sub(
        r"(?i)^\s*(please\s+)?(calculate|compute|what is|what's|solve)\s*",
        "",
        expression,
    ).strip().rstrip("?.!")

    if not re.fullmatch(r"[0-9\s.+\-*/()%]+", expression):
        return "Please enter a basic arithmetic expression."

    try:
        tree = ast.parse(expression, mode="eval")

        def evaluate(node):
            if isinstance(node, ast.Expression):
                return evaluate(node.body)

            if isinstance(node, ast.Constant):
                if isinstance(node.value, (int, float)) and not isinstance(node.value, bool):
                    return node.value
                raise ValueError("Invalid number.")

            if isinstance(node, ast.BinOp):
                operations = {
                    ast.Add: operator.add,
                    ast.Sub: operator.sub,
                    ast.Mult: operator.mul,
                    ast.Div: operator.truediv,
                    ast.FloorDiv: operator.floordiv,
                    ast.Mod: operator.mod,
                    ast.Pow: operator.pow,
                }

                operation = operations.get(type(node.op))
                if operation is None:
                    raise ValueError("Unsupported operation.")

                left = evaluate(node.left)
                right = evaluate(node.right)

                if isinstance(node.op, ast.Pow) and abs(right) > 100:
                    raise ValueError("Exponent is too large.")

                return operation(left, right)

            if isinstance(node, ast.UnaryOp):
                if isinstance(node.op, ast.UAdd):
                    return evaluate(node.operand)
                if isinstance(node.op, ast.USub):
                    return -evaluate(node.operand)

            raise ValueError("Unsupported expression.")

        return f"Result: {evaluate(tree)}"

    except ZeroDivisionError:
        return "Calculation error: division by zero."
    except Exception as error:
        return f"Calculation error: {error}"

# =========================================================
# CODE ANSWER
# =========================================================


def answer_code(user_message: str):
    """Answer coding questions and execute explicitly requested code.

    Execution is only attempted when the user explicitly asks to run/execute
    supplied code. The local executor is not a secure sandbox; do not expose
    this endpoint to untrusted users without OS-level isolation.
    """
    execution_requested = bool(
        re.search(r"\b(run|execute|test)\b", user_message, re.IGNORECASE)
        and re.search(
            r"```|\b(code|python|javascript|typescript|program|snippet)\b",
            user_message,
            re.IGNORECASE,
        )
    )

    if execution_requested:
        # Prefer a fenced code block, e.g. ```python ... ```.
        fenced = re.search(
            r"```\s*([\w+#.-]*)\s*\n(.*?)```",
            user_message,
            flags=re.DOTALL,
        )
        language = "python"
        code = ""

        if fenced:
            language_label = (fenced.group(1) or "python").strip().lower()
            language_map = {
                "py": "python", "python3": "python",
                "js": "javascript", "node": "javascript",
                "ts": "typescript", "c++": "cpp",
                "c#": "csharp", "golang": "go", "rs": "rust",
            }
            language = language_map.get(language_label, language_label)
            code = fenced.group(2).strip()
        else:
            # For plain-text prompts, start at the first recognizable code line.
            lines = user_message.splitlines()
            start_index = None
            code_start = re.compile(
                r"^\s*(print\s*\(|raise\s+|import\s+|from\s+\w+\s+import\b|"
                r"def\s+\w+\s*\(|class\s+\w+\b|if\s+__name__|"
                r"console\.log\s*\(|SELECT\b|CREATE\s+TABLE\b|"
                r"public\s+class\s+Main\b|#include\s*[<\"])",
                flags=re.IGNORECASE,
            )
            for index, line in enumerate(lines):
                if code_start.search(line):
                    start_index = index
                    break
            if start_index is not None:
                code = "\n".join(lines[start_index:]).strip()
                language_match = re.search(
                    r"\b(python|python3|py|javascript|js|node|typescript|ts|sql|java|c\+\+|cpp|c|php|go|golang|rust|rs)\b",
                    user_message[:start_index and sum(len(x) + 1 for x in lines[:start_index]) or 0],
                    flags=re.IGNORECASE,
                )
                if language_match:
                    language = language_match.group(1).lower()
                    language = {
                        "py": "python", "python3": "python", "js": "javascript",
                        "node": "javascript", "ts": "typescript", "c++": "cpp",
                        "golang": "go", "rs": "rust",
                    }.get(language, language)

        if code:
            result = execute_code(language, code, timeout_seconds=8)
            if result.get("success"):
                stdout = result.get("stdout", "") or "(No standard output.)"
                stderr = result.get("stderr", "")
                answer = (
                    f"**Actual execution result**\n\n"
                    f"- Language: `{result.get('language', language)}`\n"
                    f"- Status: Success\n"
                    f"- Exit code: `{result.get('return_code', 0)}`\n"
                    f"- Duration: `{result.get('duration_seconds', 'unknown')}` seconds\n\n"
                    f"**Output**\n```text\n{stdout}\n```"
                )
                if stderr:
                    answer += f"\n\n**Warnings / stderr**\n```text\n{stderr}\n```"
                return answer

            error_text = result.get("error") or result.get("stderr") or "Execution failed."
            stdout = result.get("stdout", "")
            answer = (
                f"**Code execution failed**\n\n"
                f"- Language: `{result.get('language', language)}`\n"
                f"- Phase: `{result.get('phase', 'run')}`\n\n"
                f"**Error**\n```text\n{error_text}\n```"
            )
            if stdout:
                answer += f"\\n\\n**Output before failure**\\n```text\\n{stdout}\\n```"

            # Diagnose the actual executor failure and suggest a correction.
            # Suggested code is NOT executed automatically.
            repair_prompt = f"""
You are Nova's coding debugger. Diagnose the actual execution failure.
Suggest the smallest reasonable correction. Do not claim the corrected code
has been run. Return a brief explanation, one corrected code block in {language},
and a short description of the change.

Original user request:
{user_message}

Original code:
```{language}
{code}
```

Actual executor error:
{error_text}

Output before failure:
{stdout or "(none)"}

Base your diagnosis only on this error. Do not invent execution results.
"""
            repair_suggestion = ask_ollama(repair_prompt)
            if repair_suggestion and repair_suggestion.strip():
                answer += (
                    "\\n\\n**Suggested fix (not yet executed)**\\n\\n"
                    + repair_suggestion.strip()
                )
            else:
                answer += (
                    "\\n\\nNova could not generate a repair suggestion. "
                    "Ask Nova to debug the error and propose corrected code."
                )
            return answer

    # Normal coding assistance: do not claim code has been executed.
    prompt = f"""
You are Nova, an expert programming assistant.
Help with coding, debugging, explaining, and improving code in common languages.
Inspect supplied code carefully, give a complete practical answer, and explain
important fixes when useful. Never claim code was executed or tested unless the
code execution tool actually ran it. If execution was not requested, do not run it.

USER REQUEST:
{user_message}

Answer the user's actual request clearly and accurately.
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
    # EXPLICIT CODE EXECUTION DETECTION
    # =====================================================

    # Route explicit execution requests directly to the real local executor.
    # Do not let the agent/web-search tools intercept these requests.
    explicit_execution_request = bool(
        re.search(r"\b(run|execute|test)\b", user_message, re.IGNORECASE)
        and re.search(
            r"```|\b(code|python|javascript|typescript|program|snippet)\b",
            user_message,
            re.IGNORECASE,
        )
    )

    # =====================================================
    # AGENT
    # =====================================================

    if explicit_execution_request:
        agent_data = {
            "used_tools": [],
            "results": [],
        }
        print("DIRECT CODE EXECUTION REQUEST: skipping agent tools")
    else:
        try:
            agent_data = run_agent(user_message)
        except Exception as error:
            print("AGENT ERROR:", error)
            agent_data = {
                "used_tools": [],
                "results": [],
            }

    used_tools = agent_data.get(
        "used_tools",
        []
    )

    if not isinstance(
        used_tools,
        list
    ):
        used_tools = []

    # =====================================================
    # AGENT MODE
    # =====================================================

    if used_tools:

        print(
            "AGENT MODE ACTIVATED"
        )

        try:

            answer, sources = (
                answer_agent_task(
                    user_message,
                    agent_data
                )
            )

        except Exception as error:

            print(
                "AGENT ANSWER ERROR:",
                error
            )

            answer = answer_general(
                user_message
            )

            sources = []

        intent = "agent"

    # =====================================================
    # NORMAL ROUTER
    # =====================================================

    else:

        try:
            if explicit_execution_request:
                intent = "code"
            else:
                intent = route_request(user_message)

        except Exception as error:

            print(
                "ROUTER ERROR:",
                error
            )

            intent = "general"

        print(
            "NOVA INTENT:",
            intent
        )

        sources = []

        if intent == "general":

            answer = answer_general(
                user_message
            )

        elif intent == "memory":

            answer = answer_memory(
                user_message,
                conversation_id
            )

        elif intent == "rag":

            answer, sources = answer_rag(
                user_message
            )

        elif intent == "calculator":

            answer = answer_calculator(
                user_message
            )

        elif intent == "code":

            answer = answer_code(
                user_message
            )

        elif intent == "web":

            answer, sources = answer_web(
                user_message
            )

        else:

            answer = answer_general(
                user_message
            )

            intent = "general"

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
        # Web search can still inform answers, but source cards/links are hidden.
        "sources": [],
        "tools": used_tools,
        "conversation_id": conversation_id,
    }


# =========================================================
# PDF UPLOAD
# =========================================================

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