import requests

from database import (
    initialize_database,
    save_message,
    load_messages,
    clear_messages
)

from rag import search_documents


# ============================================================
# SETTINGS
# ============================================================

OLLAMA_URL = "http://localhost:11434/api/chat"
MODEL = "llama3:latest"


# ============================================================
# DATABASE
# ============================================================

initialize_database()


# ============================================================
# LOAD MEMORY
# ============================================================

old_messages = load_messages()


# ============================================================
# NOVA SYSTEM MESSAGE
# ============================================================

system_message = {
    "role": "system",
    "content": """
You are Nova, a local AI assistant.

You have access to the user's local documents through RAG.

IMPORTANT RAG RULES:

1. When LOCAL DOCUMENT CONTEXT is provided, answer using
   ONLY the information contained in that context.

2. Do NOT add facts from your general knowledge when answering
   a question about the user's documents.

3. Do NOT add extra categories, examples, or information that
   are not present in the retrieved document context.

4. Do NOT expand a list from the document using your own
   knowledge.

5. If the answer is not present in the document context,
   say:

   "I couldn't find that information in your documents."

6. Never pretend that information came from a document if
   it was not present in the document.

7. Keep answers clear and concise.

8. When document context is used, mention the source document
   at the end of the answer.
"""
}


# ============================================================
# CONVERSATION
# ============================================================

messages = [system_message]

for message in old_messages:
    messages.append(message)


# ============================================================
# START NOVA
# ============================================================

print()
print("==============================")
print("       NOVA LOCAL AI")
print("==============================")
print(f"Model: {MODEL}")
print("Memory: PERSISTENT")
print("RAG: ENABLED")
print()
print("Type 'exit' to quit.")
print("Type 'clear' to delete memory.")
print("==============================")
print()


if old_messages:

    print(f"Loaded {len(old_messages)} previous messages.")
    print()


# ============================================================
# CHAT LOOP
# ============================================================

while True:

    user_input = input("You: ").strip()


    # --------------------------------------------------------
    # EXIT
    # --------------------------------------------------------

    if user_input.lower() == "exit":

        print("Nova: Goodbye!")
        break


    # --------------------------------------------------------
    # CLEAR MEMORY
    # --------------------------------------------------------

    if user_input.lower() == "clear":

        clear_messages()

        messages = [system_message]

        print("Nova: Memory cleared.")
        print()

        continue


    # --------------------------------------------------------
    # EMPTY INPUT
    # --------------------------------------------------------

    if not user_input:

        continue


    # --------------------------------------------------------
    # RAG SEARCH
    # --------------------------------------------------------

    try:

        rag_results = search_documents(
            user_input,
            n_results=3
        )

    except Exception as error:

        print()
        print("RAG Error:", error)
        print()

        rag_results = []


    # --------------------------------------------------------
    # CREATE DOCUMENT CONTEXT
    # --------------------------------------------------------

    document_context = ""

    if rag_results:

        document_context = "\n"

        for index, result in enumerate(
            rag_results,
            start=1
        ):

            document_context += f"""
DOCUMENT {index}
SOURCE: {result['source']}

{result['text']}

--------------------------------
"""


    # --------------------------------------------------------
    # CREATE PROMPT
    # --------------------------------------------------------

    if document_context:

        prompt = f"""
Answer the user's question using ONLY the local document
context below.

USER QUESTION:
{user_input}

LOCAL DOCUMENT CONTEXT:
{document_context}

STRICT RULES:

- Use only information from the document context.
- Do not add information from your general knowledge.
- Do not add extra categories.
- Do not add extra examples.
- Do not expand lists beyond what the document contains.
- If the answer is not contained in the context, say:

"I couldn't find that information in your documents."

At the end write:

Source: <document name>
"""

    else:

        prompt = user_input


    # --------------------------------------------------------
    # SAVE USER MESSAGE
    # --------------------------------------------------------

    save_message(
        "user",
        user_input
    )


    # --------------------------------------------------------
    # ADD USER MESSAGE
    # --------------------------------------------------------

    messages.append({
        "role": "user",
        "content": prompt
    })


    # --------------------------------------------------------
    # SEND TO OLLAMA
    # --------------------------------------------------------

    try:

        response = requests.post(
            OLLAMA_URL,
            json={
                "model": MODEL,
                "messages": messages,
                "stream": False
            },
            timeout=300
        )

        response.raise_for_status()

        data = response.json()

        assistant_response = data["message"]["content"]


    except requests.exceptions.ConnectionError:

        print()
        print("Nova: Cannot connect to Ollama.")
        print("Make sure Ollama is running.")
        print()

        messages.pop()

        continue


    except Exception as error:

        print()
        print("Nova: Error:", error)
        print()

        messages.pop()

        continue


    # --------------------------------------------------------
    # SAVE NOVA RESPONSE
    # --------------------------------------------------------

    save_message(
        "assistant",
        assistant_response
    )


    # --------------------------------------------------------
    # ADD NOVA RESPONSE TO MEMORY
    # --------------------------------------------------------

    messages.append({
        "role": "assistant",
        "content": assistant_response
    })


    # --------------------------------------------------------
    # DISPLAY RESPONSE
    # --------------------------------------------------------

    print()
    print("Nova:", assistant_response)
    print()