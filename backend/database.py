
import sqlite3
import uuid
from pathlib import Path


# =========================================================
# PATHS
# =========================================================

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
DB_PATH = DATA_DIR / "nova.db"


# =========================================================
# DATABASE INITIALIZATION
# =========================================================

def initialize_database():
    DATA_DIR.mkdir(parents=True, exist_ok=True)

    with sqlite3.connect(DB_PATH) as connection:
        cursor = connection.cursor()

        # -------------------------------------------------
        # Conversation messages
        # -------------------------------------------------

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # -------------------------------------------------
        # Long-term memories
        # -------------------------------------------------

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS memories (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                memory TEXT NOT NULL,
                category TEXT DEFAULT 'general',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # -------------------------------------------------
        # Saved conversations
        # -------------------------------------------------

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS conversations (
                id TEXT PRIMARY KEY,
                title TEXT NOT NULL DEFAULT 'New Chat',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # -------------------------------------------------
        # Migrate existing messages table safely
        # -------------------------------------------------

        cursor.execute("PRAGMA table_info(messages)")
        columns = [column[1] for column in cursor.fetchall()]

        if "conversation_id" not in columns:
            cursor.execute("""
                ALTER TABLE messages
                ADD COLUMN conversation_id TEXT
            """)

        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_messages_conversation
            ON messages(conversation_id, id)
        """)


# =========================================================
# EXISTING CHAT MEMORY FUNCTIONS
# =========================================================

def save_message(role, content):
    """Save a legacy/global chat message."""
    with sqlite3.connect(DB_PATH) as connection:
        connection.execute(
            """
            INSERT INTO messages (role, content)
            VALUES (?, ?)
            """,
            (role, content)
        )


def load_messages():
    """Load legacy/global messages."""
    with sqlite3.connect(DB_PATH) as connection:
        rows = connection.execute("""
            SELECT role, content
            FROM messages
            ORDER BY id ASC
        """).fetchall()

    return [
        {
            "role": role,
            "content": content
        }
        for role, content in rows
    ]


def clear_messages():
    """Clear all messages. Use carefully."""
    with sqlite3.connect(DB_PATH) as connection:
        connection.execute("DELETE FROM messages")


# =========================================================
# SAVED CONVERSATIONS
# =========================================================

def create_conversation(title="New Chat"):
    """Create a separate conversation and return its ID."""
    conversation_id = str(uuid.uuid4())

    with sqlite3.connect(DB_PATH) as connection:
        connection.execute(
            """
            INSERT INTO conversations (id, title)
            VALUES (?, ?)
            """,
            (conversation_id, title)
        )

    return conversation_id


def list_conversations():
    """Return conversations, newest activity first."""
    with sqlite3.connect(DB_PATH) as connection:
        connection.row_factory = sqlite3.Row

        rows = connection.execute("""
            SELECT id, title, created_at, updated_at
            FROM conversations
            ORDER BY updated_at DESC, created_at DESC
        """).fetchall()

    return [dict(row) for row in rows]


def get_conversation(conversation_id):
    """Return one conversation, or None if it doesn't exist."""
    with sqlite3.connect(DB_PATH) as connection:
        connection.row_factory = sqlite3.Row

        row = connection.execute(
            """
            SELECT id, title, created_at, updated_at
            FROM conversations
            WHERE id = ?
            """,
            (conversation_id,)
        ).fetchone()

    return dict(row) if row else None


def rename_conversation(conversation_id, title):
    """Rename a conversation."""
    title = title.strip()

    if not title:
        return False

    with sqlite3.connect(DB_PATH) as connection:
        cursor = connection.execute(
            """
            UPDATE conversations
            SET title = ?, updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (title, conversation_id)
        )

    return cursor.rowcount > 0


def delete_conversation(conversation_id):
    """Delete a conversation and only its associated messages."""
    with sqlite3.connect(DB_PATH) as connection:
        cursor = connection.execute(
            """
            DELETE FROM conversations
            WHERE id = ?
            """,
            (conversation_id,)
        )

        if cursor.rowcount == 0:
            return False

        connection.execute(
            """
            DELETE FROM messages
            WHERE conversation_id = ?
            """,
            (conversation_id,)
        )

    return True


def save_conversation_message(conversation_id, role, content):
    """Save a message under its conversation."""
    with sqlite3.connect(DB_PATH) as connection:
        cursor = connection.execute(
            """
            INSERT INTO messages (conversation_id, role, content)
            SELECT id, ?, ?
            FROM conversations
            WHERE id = ?
            """,
            (role, content, conversation_id)
        )

        if cursor.rowcount == 0:
            raise ValueError("Conversation not found.")

        # Use the first user message as the default chat title.
        if role == "user":
            connection.execute(
                """
                UPDATE conversations
                SET title = CASE
                    WHEN title = 'New Chat' THEN ?
                    ELSE title
                END,
                updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (content.strip()[:50] or "New Chat", conversation_id)
            )
        else:
            connection.execute(
                """
                UPDATE conversations
                SET updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (conversation_id,)
            )


def load_conversation_messages(conversation_id):
    """Load messages belonging to one conversation only."""
    with sqlite3.connect(DB_PATH) as connection:
        connection.row_factory = sqlite3.Row

        rows = connection.execute(
            """
            SELECT role, content, created_at
            FROM messages
            WHERE conversation_id = ?
            ORDER BY id ASC
            """,
            (conversation_id,)
        ).fetchall()

    return [dict(row) for row in rows]


# =========================================================
# LONG-TERM MEMORY
# =========================================================

def save_memory(memory, category="general"):
    memory = memory.strip()

    if not memory:
        return

    with sqlite3.connect(DB_PATH) as connection:
        cursor = connection.cursor()

        # Avoid storing exact duplicate memories.
        cursor.execute(
            """
            SELECT id
            FROM memories
            WHERE memory = ?
            """,
            (memory,)
        )

        existing = cursor.fetchone()

        if existing:
            cursor.execute(
                """
                UPDATE memories
                SET updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (existing[0],)
            )
        else:
            cursor.execute(
                """
                INSERT INTO memories (memory, category)
                VALUES (?, ?)
                """,
                (memory, category)
            )


def load_memories():
    with sqlite3.connect(DB_PATH) as connection:
        rows = connection.execute("""
            SELECT id, memory, category
            FROM memories
            ORDER BY updated_at DESC
        """).fetchall()

    return [
        {
            "id": row[0],
            "memory": row[1],
            "category": row[2]
        }
        for row in rows
    ]


def delete_memory(memory_id):
    with sqlite3.connect(DB_PATH) as connection:
        connection.execute(
            """
            DELETE FROM memories
            WHERE id = ?
            """,
            (memory_id,)
        )


def clear_memories():
    with sqlite3.connect(DB_PATH) as connection:
        connection.execute("DELETE FROM memories")


# =========================================================
# SEARCH MEMORIES
# =========================================================

def search_memories(query, limit=10):
    with sqlite3.connect(DB_PATH) as connection:
        rows = connection.execute(
            """
            SELECT id, memory, category
            FROM memories
            WHERE memory LIKE ?
            ORDER BY updated_at DESC
            LIMIT ?
            """,
            (f"%{query}%", limit)
        ).fetchall()

    return [
        {
            "id": row[0],
            "memory": row[1],
            "category": row[2]
        }
        for row in rows
    ]
