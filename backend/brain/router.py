import requests
import json
import re

OLLAMA_URL = "http://localhost:11434/api/chat"
MODEL = "llama3:latest"


# =========================================================
# FAST WEB DETECTION
# =========================================================

def should_use_web(user_input: str) -> bool:
    """
    Detect questions that clearly require current/live
    internet information.

    This runs BEFORE the Llama router.
    """

    text = user_input.lower().strip()

    web_patterns = [
        # Current / latest information
        r"\bcurrent\b",
        r"\bcurrently\b",
        r"\bright now\b",
        r"\bnow\b",
        r"\btoday\b",
        r"\btonight\b",
        r"\byesterday\b",
        r"\btomorrow\b",
        r"\blatest\b",
        r"\brecent\b",
        r"\brecently\b",
        r"\bthis week\b",
        r"\bthis month\b",
        r"\bthis year\b",

        # News
        r"\bnews\b",
        r"\blatest news\b",
        r"\btoday's news\b",

        # Live information
        r"\blive\b",
        r"\blive score\b",
        r"\bscore\b",
        r"\bscores\b",
        r"\bstandings\b",
        r"\bschedule\b",

        # Prices / market information
        r"\bcurrent price\b",
        r"\bprice today\b",
        r"\bprice of\b",
        r"\bstock price\b",
        r"\bshare price\b",
        r"\bbitcoin price\b",
        r"\bcryptocurrency price\b",
        r"\bexchange rate\b",

        # Weather
        r"\bweather\b",
        r"\btemperature today\b",
        r"\bforecast\b",

        # Current office holders / events
        r"\bwho is the current\b",
        r"\bwho is currently\b",
        r"\bcurrent prime minister\b",
        r"\bcurrent president\b",
        r"\bcurrent chief minister\b",
        r"\bcurrent ceo\b",

        # Time-sensitive versions / releases
        r"\blatest version\b",
        r"\bcurrent version\b",
        r"\bnew version\b",
        r"\brecent release\b",
        r"\blatest release\b",

        # Explicit web requests
        r"\bsearch the web\b",
        r"\bsearch online\b",
        r"\blook online\b",
        r"\blook it up\b",
        r"\bon the internet\b",
        r"\bonline\b",
    ]

    for pattern in web_patterns:

        if re.search(pattern, text):

            print(
                f"FAST WEB DETECTION: matched {pattern}"
            )

            return True

    return False


# =========================================================
# AI BRAIN ROUTER
# =========================================================

def route_request(user_input: str) -> str:

    # -----------------------------------------------------
    # STEP 1
    # Fast web detection
    # -----------------------------------------------------

    if should_use_web(user_input):

        print(
            "BRAIN INTENT: web (fast detection)"
        )

        return "web"

    # -----------------------------------------------------
    # STEP 2
    # Ask Llama to classify everything else
    # -----------------------------------------------------

    prompt = f"""
You are the AI decision-making brain of Nova.

Your job is to decide HOW Nova should answer the user's
request.

You must NOT answer the question.

Choose exactly ONE intent:

general
memory
rag
calculator
code
web

RULES:

1. GENERAL

Use general for normal knowledge, explanations,
concepts, definitions, education, science, technology,
history, mathematics explanations, and ordinary questions.

Examples:

"What is PCA?"
"What is machine learning?"
"Explain cloud computing."
"What is RAG?"
"What is virtualization?"

IMPORTANT:

"What is RAG?" = general

Do not choose RAG merely because the word "RAG" appears.

---------------------------------------------------------

2. MEMORY

Use memory when the user asks about previous conversations,
previous messages, stored memories, or things Nova remembers.

Examples:

"What did I ask you before?"
"What do you remember about me?"
"What was my previous question?"

---------------------------------------------------------

3. RAG

Use rag ONLY when the user specifically asks for information
from their uploaded documents, PDFs, notes, or indexed files.

Examples:

"According to my notes, what is PCA?"
"What does my PDF say about machine learning?"
"What are the types mentioned in my document?"
"What is the secret code in the document?"

Important:

"What is RAG?" = general

"What is RAG according to my PDF?" = rag

"What are the types of machine learning according to my notes?"
= rag

---------------------------------------------------------

4. CALCULATOR

Use calculator when the main task is a mathematical calculation.

Examples:

"25 * 48"
"Calculate 1250 / 25"
"What is 15% of 800?"
"1250 + 450"

---------------------------------------------------------

5. CODE

Use code when the user wants programming code, debugging,
writing a program, fixing code, or solving a programming problem.

Examples:

"Write Python code for a calculator."
"Fix this Java code."
"Create a Python API."
"Why is my React code not working?"

---------------------------------------------------------

6. WEB

Use web when the user explicitly asks for internet information
OR when the answer clearly depends on current/live information.

Examples:

"Search the web for Python 3.14."
"Find information about OpenAI."
"Look this up online."

Current-information examples:

"Who is the current Prime Minister of India?"
"What is the latest version of Python?"
"What happened today?"
"What is the current price of Bitcoin?"
"What are today's AI news?"
"What is today's weather?"

However, common current words are normally handled by
Nova's fast web detector before reaching this classifier.

---------------------------------------------------------

IMPORTANT PRIORITY

If the user asks about their own PDF, notes, or documents,
choose RAG even if the question also contains general
knowledge terms.

Example:

"What are the types of machine learning according to my notes?"
= rag

Do NOT choose web for questions about the user's documents.

GENERAL is the default if there is no clear reason to use
another intent.

If unsure, choose general.

Return ONLY valid JSON.

Example:

{{
    "intent": "general"
}}

USER REQUEST:

{user_input}
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
                            "You are Nova's internal "
                            "AI decision-making brain."
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
            "BRAIN RAW RESPONSE:",
            content
        )

        # Remove accidental markdown
        content = (
            content
            .replace("```json", "")
            .replace("```", "")
            .strip()
        )

        result = json.loads(content)

        intent = result.get(
            "intent",
            "general"
        )

        valid_intents = [
            "general",
            "memory",
            "rag",
            "calculator",
            "code",
            "web"
        ]

        if intent not in valid_intents:

            print(
                "INVALID INTENT:",
                intent
            )

            return "general"

        print(
            "BRAIN INTENT:",
            intent
        )

        return intent

    except Exception as error:

        print(
            "BRAIN ERROR:",
            error
        )

        return "general"