import requests
import json
import re

from .database import save_memory


# =========================================================
# CONFIGURATION
# =========================================================

OLLAMA_URL = "http://localhost:11434/api/chat"

MODEL = "llama3:latest"


# =========================================================
# MEMORY BRAIN
# =========================================================

def extract_memory(user_message: str):
    """
    Ask Llama whether the user's message contains
    information that Nova should remember long-term.

    Returns:
        {
            "should_remember": True/False,
            "memory": "...",
            "category": "..."
        }
    """

    # Deterministically save clear, stable facts that are commonly used
    # to test cross-chat memory. This avoids relying on the local model to
    # decide whether an explicit name/project statement is worth saving.
    text = user_message.strip()
    saved = []

    name_match = re.search(
        r"\bmy name is\s+([A-Za-z][A-Za-z .'-]{0,59}?)(?=\s*(?:,|\.|;| and I am|$))",
        text,
        re.IGNORECASE,
    )
    if name_match:
        name = name_match.group(1).strip().rstrip(" .,")
        if name:
            fact = f"The user's name is {name}."
            save_memory(fact, "general")
            saved.append(fact)

    project_match = re.search(
        r"\bI am building\s+(.+?)(?=[.!?]|$)",
        text,
        re.IGNORECASE,
    )
    if project_match:
        project_fact = "The user is building " + project_match.group(1).strip().rstrip(" ,") + "."
        # Keep this concise and avoid saving a statement that is just a question.
        if len(project_fact) <= 300:
            save_memory(project_fact, "project")
            saved.append(project_fact)

    if saved:
        # Also retain any useful technology/project detail from the same
        # explicit statement so it is available in future chats.
        technology_match = re.search(
            r"\busing\s+(.+?)(?=[.!?]|$)",
            text,
            re.IGNORECASE,
        )
        if technology_match and project_match:
            technology_fact = (
                "The user's project technologies are "
                + technology_match.group(1).strip().rstrip(" ,")
                + "."
            )
            if len(technology_fact) <= 300:
                save_memory(technology_fact, "technical")
                saved.append(technology_fact)

        return {
            "should_remember": True,
            "memory": " ".join(saved),
            "category": "project" if project_match else "general",
        }

    prompt = f"""
You are Nova's long-term memory manager.

Your job is NOT to answer the user's message.

Your job is to decide whether the user has provided
useful information that Nova should remember for future
conversations.

Remember information such as:

- Explicit requests to remember something
- User preferences
- Long-term projects
- Important goals
- Stable working preferences
- Important personal workflow information
- Technical project decisions
- Things the user says Nova should remember

DO NOT remember:

- Ordinary questions
- Temporary calculations
- Normal greetings
- One-time requests
- Information that is only relevant to the current question
- Passwords
- API keys
- Authentication tokens
- Highly sensitive information

If the user explicitly says:
"remember this"
"remember that"
"don't forget"
"keep this in memory"

then normally save the useful information.

Return ONLY valid JSON.

If there is nothing worth remembering:

{{
    "should_remember": false,
    "memory": "",
    "category": "general"
}}

If there is something worth remembering:

{{
    "should_remember": true,
    "memory": "Short clear statement of the information",
    "category": "preference"
}}

Allowed categories:

preference
project
goal
workflow
technical
general

Examples:

User:
"Remember that my main project is Nova Local AI."

Return:
{{
    "should_remember": true,
    "memory": "The user's main project is Nova Local AI.",
    "category": "project"
}}

User:
"I prefer Python for backend development."

Return:
{{
    "should_remember": true,
    "memory": "The user prefers Python for backend development.",
    "category": "preference"
}}

User:
"What is RAG?"

Return:
{{
    "should_remember": false,
    "memory": "",
    "category": "general"
}}

User:
"Calculate 25 * 48."

Return:
{{
    "should_remember": false,
    "memory": "",
    "category": "general"
}}

USER MESSAGE:

{user_message}
"""

    try:

        response = requests.post(
            OLLAMA_URL,
            json={
                "model": MODEL,
                "messages": [
                    {
                        "role": "system",
                        "content": (
                            "You are Nova's "
                            "long-term memory manager."
                        )
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                "stream": False,
                "format": "json"
            },
            timeout=120
        )

        response.raise_for_status()

        data = response.json()

        content = data["message"]["content"].strip()

        print(
            "MEMORY RAW RESPONSE:",
            content
        )

        content = (
            content
            .replace("```json", "")
            .replace("```", "")
            .strip()
        )

        result = json.loads(content)

        should_remember = result.get(
            "should_remember",
            False
        )

        memory = result.get(
            "memory",
            ""
        ).strip()

        category = result.get(
            "category",
            "general"
        )

        allowed_categories = [
            "preference",
            "project",
            "goal",
            "workflow",
            "technical",
            "general"
        ]

        if category not in allowed_categories:

            category = "general"

        if (
            should_remember
            and memory
        ):

            save_memory(
                memory,
                category
            )

            print(
                "MEMORY SAVED:",
                memory
            )

            return {
                "should_remember": True,
                "memory": memory,
                "category": category
            }

        print(
            "MEMORY: Nothing to save"
        )

        return {
            "should_remember": False,
            "memory": "",
            "category": "general"
        }

    except Exception as error:

        print(
            "MEMORY ERROR:",
            error
        )

        return {
            "should_remember": False,
            "memory": "",
            "category": "general"
        }