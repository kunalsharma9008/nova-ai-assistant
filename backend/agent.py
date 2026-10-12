import requests
import json
import re

from datetime import datetime, date

from .web_search import web_search
from .rag import search_documents


# =========================================================
# CONFIGURATION
# =========================================================

OLLAMA_URL = "http://localhost:11434/api/chat"
MODEL = "llama3:latest"


# =========================================================
# CURRENT DATE / TIME
# =========================================================

def get_current_datetime():

    now = datetime.now()

    return {
        "date": now.strftime("%Y-%m-%d"),
        "time": now.strftime("%H:%M:%S"),
        "display": now.strftime(
            "%d %B %Y, %I:%M %p"
        ),
    }


# =========================================================
# EXTRACT DATE FROM USER QUESTION
# =========================================================

def extract_start_date(text: str):

    patterns = [
        (
            r"\b(January|February|March|April|May|June|July|"
            r"August|September|October|November|December)"
            r"\s+(\d{1,2}),\s+(\d{4})\b",
            "%B %d %Y",
        ),
        (
            r"\b(January|February|March|April|May|June|July|"
            r"August|September|October|November|December)"
            r"\s+(\d{1,2})\s+(\d{4})\b",
            "%B %d %Y",
        ),
    ]

    for pattern, date_format in patterns:

        match = re.search(
            pattern,
            text,
            re.IGNORECASE
        )

        if match:

            try:

                parsed = datetime.strptime(
                    " ".join(match.groups()),
                    date_format
                )

                return parsed.strftime(
                    "%Y-%m-%d"
                )

            except ValueError:
                pass

    match = re.search(
        r"\b\d{4}-\d{2}-\d{2}\b",
        text
    )

    if match:

        try:

            parsed = datetime.strptime(
                match.group(0),
                "%Y-%m-%d"
            )

            return parsed.strftime(
                "%Y-%m-%d"
            )

        except ValueError:
            pass

    return None


# =========================================================
# DATE TASK DETECTION
# =========================================================

def detect_date_task(
    user_message: str
):

    text = user_message.lower()

    date_words = [
        "how long",
        "how many years",
        "how many months",
        "how many days",
        "years since",
        "months since",
        "days since",
        "since",
        "until",
        "duration",
        "for how long",
    ]

    contains_date_language = any(
        phrase in text
        for phrase in date_words
    )

    start_date = extract_start_date(
        user_message
    )

    if (
        contains_date_language
        and start_date
    ):

        current_date = (
            get_current_datetime()["date"]
        )

        print(
            "FAST DATE DETECTION ACTIVATED"
        )

        print(
            "START DATE:",
            start_date
        )

        print(
            "CURRENT DATE:",
            current_date
        )

        return {
            "start_date": start_date,
            "end_date": current_date,
        }

    return None


# =========================================================
# SAFE CALCULATOR
# =========================================================

def calculate(
    expression: str
):

    try:

        expression = (
            expression
            .replace(",", "")
            .replace("$", "")
            .strip()
        )

        allowed = set(
            "0123456789+-*/().% "
        )

        if not all(
            character in allowed
            for character in expression
        ):

            return {
                "success": False,
                "result": None,
                "error": (
                    "Invalid mathematical "
                    "expression."
                ),
            }

        expression = expression.replace(
            "%",
            "/100"
        )

        result = eval(
            expression,
            {
                "__builtins__": {}
            },
            {}
        )

        return {
            "success": True,
            "result": result,
        }

    except Exception as error:

        return {
            "success": False,
            "result": None,
            "error": str(error),
        }


# =========================================================
# DATE CALCULATOR
# =========================================================

def calculate_date_difference(
    start_date: str,
    end_date: str
):

    try:

        start = datetime.strptime(
            start_date,
            "%Y-%m-%d"
        ).date()

        end = datetime.strptime(
            end_date,
            "%Y-%m-%d"
        ).date()

        if start > end:

            return {
                "success": False,
                "error": (
                    "Start date is after "
                    "end date."
                ),
            }

        total_days = (
            end - start
        ).days

        years = (
            end.year -
            start.year
        )

        try:

            anniversary = date(
                end.year,
                start.month,
                start.day
            )

        except ValueError:

            anniversary = date(
                end.year,
                2,
                28
            )

        if anniversary > end:

            years -= 1

        try:

            anniversary = date(
                start.year + years,
                start.month,
                start.day
            )

        except ValueError:

            anniversary = date(
                start.year + years,
                2,
                28
            )

        temporary = anniversary

        months = 0

        while True:

            next_month = (
                temporary.month % 12
            ) + 1

            next_year = (
                temporary.year
                + (
                    1
                    if temporary.month == 12
                    else 0
                )
            )

            try:

                next_date = date(
                    next_year,
                    next_month,
                    temporary.day
                )

            except ValueError:

                break

            if next_date > end:

                break

            months += 1
            temporary = next_date

        days = (
            end - temporary
        ).days

        return {
            "success": True,
            "start_date": start.isoformat(),
            "end_date": end.isoformat(),
            "years": years,
            "months": months,
            "days": days,
            "total_days": total_days,
            "summary": (
                f"{years} years, "
                f"{months} months, "
                f"{days} days"
            ),
        }

    except Exception as error:

        return {
            "success": False,
            "error": str(error),
        }


# =========================================================
# WEB SEARCH TOOL
# =========================================================

def run_web_search(
    query: str
):

    results = web_search(
        query,
        max_results=5
    )

    return {
        "tool": "web_search",
        "query": query,
        "results": results,
    }


# =========================================================
# RAG SEARCH TOOL
# =========================================================

def run_rag_search(
    query: str
):

    try:

        results = search_documents(
            query,
            n_results=5
        )

        return {
            "tool": "rag_search",
            "query": query,
            "results": results,
        }

    except Exception as error:

        return {
            "tool": "rag_search",
            "query": query,
            "results": [],
            "error": str(error),
        }


# =========================================================
# CALCULATOR TOOL
# =========================================================

def run_calculator(
    expression: str
):

    print(
        "CALCULATOR EXPRESSION:",
        expression
    )

    result = calculate(
        expression
    )

    print(
        "CALCULATOR RESULT:",
        result
    )

    return {
        "tool": "calculator",
        "expression": expression,
        "result": result,
    }


# =========================================================
# DATE CALCULATOR TOOL
# =========================================================

def run_date_calculator(
    start_date: str,
    end_date: str
):

    result = calculate_date_difference(
        start_date,
        end_date
    )

    return {
        "tool": "date_calculator",
        "start_date": start_date,
        "end_date": end_date,
        "result": result,
    }


# =========================================================
# ASK OLLAMA
# =========================================================

def ask_agent_model(
    prompt: str
):

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
                            "agent planning system. "
                            "Return valid JSON only."
                        ),
                    },
                    {
                        "role": "user",
                        "content": prompt,
                    },
                ],
                "stream": False,
                "format": "json",
            },
            timeout=120,
        )

        response.raise_for_status()

        data = response.json()

        return data[
            "message"
        ][
            "content"
        ].strip()

    except Exception as error:

        print(
            "AGENT MODEL ERROR:",
            error
        )

        return ""


# =========================================================
# EXTRACT NUMBERS FROM WEB RESULTS
# =========================================================

def extract_numbers_from_web(
    web_results
):

    text_parts = []

    for result in web_results:

        title = result.get(
            "title",
            ""
        )

        body = result.get(
            "body",
            ""
        )

        text_parts.append(
            title + " " + body
        )

    combined_text = " ".join(
        text_parts
    )

    billion_matches = re.findall(
        r"(\d+(?:\.\d+)?)\s*billion",
        combined_text,
        re.IGNORECASE
    )

    million_matches = re.findall(
        r"(\d+(?:\.\d+)?)\s*million",
        combined_text,
        re.IGNORECASE
    )

    raw_number_matches = re.findall(
        r"\b\d{1,3}(?:,\d{3})+(?:\.\d+)?\b",
        combined_text
    )

    numbers = []

    for value in billion_matches:

        try:

            number = (
                float(value)
                * 1_000_000_000
            )

            numbers.append(
                int(number)
            )

        except ValueError:
            pass

    for value in million_matches:

        try:

            number = (
                float(value)
                * 1_000_000
            )

            numbers.append(
                int(number)
            )

        except ValueError:
            pass

    for value in raw_number_matches:

        try:

            number = int(
                value.replace(
                    ",",
                    ""
                )
            )

            numbers.append(
                number
            )

        except ValueError:
            pass

    cleaned = []

    for number in numbers:

        if number not in cleaned:

            cleaned.append(
                number
            )

    return cleaned


# =========================================================
# CREATE CALCULATION FROM WEB RESULT
# =========================================================

def create_calculation_from_web(
    user_message: str,
    web_results
):

    numbers = extract_numbers_from_web(
        web_results
    )

    if not numbers:

        return None

    text = user_message.lower()

    # -----------------------------------------------------
    # Population in millions
    # -----------------------------------------------------

    if (
        "population per million"
        in text
        or "population in millions"
        in text
        or "population per 1 million"
        in text
    ):

        population = max(
            numbers
        )

        expression = (
            f"{population} / 1000000"
        )

        return {
            "expression": expression,
            "description": (
                "Convert population "
                "into millions."
            ),
        }

    # -----------------------------------------------------
    # Divide by million
    # -----------------------------------------------------

    if (
        "divide by million"
        in text
        or "divided by a million"
        in text
        or "divide by 1 million"
        in text
    ):

        population = max(
            numbers
        )

        expression = (
            f"{population} / 1000000"
        )

        return {
            "expression": expression,
            "description": (
                "Divide the retrieved "
                "number by one million."
            ),
        }

    # -----------------------------------------------------
    # Let Llama construct arithmetic
    # -----------------------------------------------------

    web_text = []

    for result in web_results:

        web_text.append(
            f"""
TITLE:
{result.get("title", "")}

INFORMATION:
{result.get("body", "")}
"""
        )

    prompt = f"""
The user asked:

{user_message}

Web search returned:

{"".join(web_text)}

Detected numeric values:

{numbers}

Determine whether a mathematical calculation
is required.

If a calculation is required, create a simple
valid arithmetic expression using ONLY numbers
from the retrieved information.

Return:

{{
    "needs_calculation": true,
    "expression": "123456 / 1000000"
}}

If calculation is not required:

{{
    "needs_calculation": false,
    "expression": ""
}}

Rules:

- Use only arithmetic.
- Do not write words in expression.
- Do not use commas.
- Do not use variables.
- Do not invent numbers.
- Do not use Python.
"""

    raw = ask_agent_model(
        prompt
    )

    if not raw:

        return None

    try:

        raw = (
            raw
            .replace(
                "```json",
                ""
            )
            .replace(
                "```",
                ""
            )
            .strip()
        )

        data = json.loads(
            raw
        )

        if not data.get(
            "needs_calculation",
            False
        ):

            return None

        expression = data.get(
            "expression",
            ""
        ).strip()

        if not expression:

            return None

        allowed = set(
            "0123456789+-*/(). "
        )

        if not all(
            character in allowed
            for character in expression
        ):

            print(
                "INVALID GENERATED EXPRESSION:",
                expression
            )

            return None

        return {
            "expression": expression,
            "description": (
                "Calculation generated from "
                "retrieved web information."
            ),
        }

    except Exception as error:

        print(
            "CALCULATION PLAN ERROR:",
            error
        )

        return None


# =========================================================
# CREATE INITIAL PLAN
# =========================================================

def create_plan(
    user_message: str
):

    current = get_current_datetime()

    # -----------------------------------------------------
    # Deterministic date task
    # -----------------------------------------------------

    date_task = detect_date_task(
        user_message
    )

    if date_task:

        return {
            "needs_tools": True,
            "steps": [
                {
                    "tool": "date_calculator",
                    "start_date": date_task[
                        "start_date"
                    ],
                    "end_date": date_task[
                        "end_date"
                    ],
                }
            ],
        }

    # -----------------------------------------------------
    # Llama planner
    # -----------------------------------------------------

    prompt = f"""
You are Nova's task planning engine.

CURRENT DATE:
{current["date"]}

CURRENT TIME:
{current["time"]}

Available tools:

1. web_search
2. rag_search
3. calculator
4. date_calculator

Use web_search for current information.

Use rag_search for user documents.

Use calculator for arithmetic.

Use date_calculator for date durations.

If the user asks for information that must
come from the web, use web_search.

If the user asks for a calculation involving
a value that must first be found on the web,
use web_search first.

Return ONLY valid JSON.

Example:

{{
    "needs_tools": true,
    "steps": [
        {{
            "tool": "web_search",
            "query": "India population"
        }}
    ]
}}

USER REQUEST:

{user_message}
"""

    raw = ask_agent_model(
        prompt
    )

    if not raw:

        return {
            "needs_tools": False,
            "steps": [],
        }

    try:

        raw = (
            raw
            .replace(
                "```json",
                ""
            )
            .replace(
                "```",
                ""
            )
            .strip()
        )

        plan = json.loads(
            raw
        )

        return plan

    except Exception as error:

        print(
            "PLAN PARSE ERROR:",
            error
        )

        return {
            "needs_tools": False,
            "steps": [],
        }


# =========================================================
# EXECUTE TOOL
# =========================================================

def execute_tool(
    step: dict
):

    tool = step.get(
        "tool"
    )

    if tool == "web_search":

        return run_web_search(
            step.get(
                "query",
                ""
            )
        )

    if tool == "rag_search":

        return run_rag_search(
            step.get(
                "query",
                ""
            )
        )

    if tool == "calculator":

        return run_calculator(
            step.get(
                "expression",
                ""
            )
        )

    if tool == "date_calculator":

        current_date = (
            get_current_datetime()["date"]
        )

        end_date = step.get(
            "end_date"
        )

        if not end_date:

            end_date = current_date

        return run_date_calculator(
            step.get(
                "start_date"
            ),
            end_date
        )

    return {
        "tool": tool,
        "success": False,
        "error": "Unknown tool.",
    }


# =========================================================
# RUN AGENT
# =========================================================

def run_agent(
    user_message: str
):

    print()
    print(
        "================ AGENT ================"
    )

    current = get_current_datetime()

    print(
        "CURRENT DATE:",
        current["date"]
    )

    print(
        "CURRENT TIME:",
        current["time"]
    )

    print(
        "AGENT REQUEST:",
        user_message
    )

    # -----------------------------------------------------
    # Initial plan
    # -----------------------------------------------------

    plan = create_plan(
        user_message
    )

    print(
        "AGENT PLAN:",
        plan
    )

    if not plan.get(
        "needs_tools",
        False
    ):

        print(
            "AGENT: No tools required"
        )

        return {
            "used_tools": [],
            "results": [],
        }

    results = []

    # -----------------------------------------------------
    # Execute initial tools
    # -----------------------------------------------------

    steps = plan.get(
        "steps",
        []
    )

    for index, step in enumerate(
        steps[:5],
        start=1
    ):

        print(
            f"AGENT STEP {index}:",
            step
        )

        result = execute_tool(
            step
        )

        results.append(
            result
        )

        print(
            f"AGENT RESULT {index}:",
            result
        )

    # =====================================================
    # SEQUENTIAL WEB → CALCULATOR
    # =====================================================

    web_results = []

    for result in results:

        if result.get(
            "tool"
        ) == "web_search":

            web_results.extend(
                result.get(
                    "results",
                    []
                )
            )

    if web_results:

        calculation_words = [
            "calculate",
            "calculation",
            "divide",
            "multiply",
            "percentage",
            "percent",
            "per million",
            "per billion",
            "average",
            "difference",
            "ratio",
            "how many",
            "how much",
        ]

        user_lower = (
            user_message.lower()
        )

        needs_calculation = any(
            word in user_lower
            for word in calculation_words
        )

        calculator_already_used = any(
            result.get("tool")
            in [
                "calculator",
                "date_calculator",
            ]
            for result in results
        )

        if (
            needs_calculation
            and not calculator_already_used
        ):

            print(
                "SEQUENTIAL AGENT:"
                " WEB SEARCH → CALCULATOR"
            )

            calculation_plan = (
                create_calculation_from_web(
                    user_message,
                    web_results
                )
            )

            if calculation_plan:

                expression = (
                    calculation_plan[
                        "expression"
                    ]
                )

                print(
                    "GENERATED CALCULATION:",
                    expression
                )

                calculator_result = (
                    run_calculator(
                        expression
                    )
                )

                results.append(
                    calculator_result
                )

            else:

                print(
                    "No safe calculation "
                    "could be generated."
                )

    # =====================================================
    # COLLECT USED TOOLS
    # =====================================================

    used_tools = []

    for result in results:

        tool = result.get(
            "tool"
        )

        if (
            tool
            and tool not in used_tools
        ):

            used_tools.append(
                tool
            )

    print(
        "AGENT TOOLS:",
        used_tools
    )

    print(
        "========================================"
    )

    return {
        "used_tools": used_tools,
        "results": results,
    }