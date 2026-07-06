import sqlite3
import os
from datetime import datetime
from typing import List, Dict, Tuple

DB_FILE = "chat_history.db"


def init_db():
    """Create tables if they don't exist."""
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()

    # Sessions table — groups messages into conversations
    c.execute("""
        CREATE TABLE IF NOT EXISTS sessions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
    """)

    # Messages table — stores individual messages
    c.execute("""
        CREATE TABLE IF NOT EXISTS messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id INTEGER NOT NULL,
            sender TEXT NOT NULL,
            content TEXT NOT NULL,
            timestamp TEXT NOT NULL,
            FOREIGN KEY(session_id) REFERENCES sessions(id)
        )
    """)

    conn.commit()
    conn.close()


def create_session(title: str = None) -> int:
    """Create a new chat session and return its ID."""
    if not title:
        title = f"Chat {datetime.now().strftime('%Y-%m-%d %H:%M')}"

    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    now = datetime.now().isoformat()
    c.execute(
        "INSERT INTO sessions (title, created_at, updated_at) VALUES (?, ?, ?)",
        (title, now, now),
    )
    session_id = c.lastrowid
    conn.commit()
    conn.close()
    return session_id


def save_message(session_id: int, sender: str, content: str):
    """Save a message to the database."""
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    now = datetime.now().isoformat()
    c.execute(
        "INSERT INTO messages (session_id, sender, content, timestamp) VALUES (?, ?, ?, ?)",
        (session_id, sender, content, now),
    )
    # Update session's updated_at time
    c.execute(
        "UPDATE sessions SET updated_at = ? WHERE id = ?",
        (now, session_id),
    )
    conn.commit()
    conn.close()


def get_all_sessions() -> List[Dict]:
    """Get all chat sessions, most recent first."""
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute(
        "SELECT id, title, created_at, updated_at FROM sessions ORDER BY updated_at DESC"
    )
    rows = c.fetchall()
    conn.close()

    return [
        {
            "id": row[0],
            "title": row[1],
            "created_at": row[2],
            "updated_at": row[3],
        }
        for row in rows
    ]


def get_session_messages(session_id: int) -> List[Dict]:
    """Get all messages from a specific session."""
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute(
        "SELECT sender, content, timestamp FROM messages WHERE session_id = ? ORDER BY timestamp ASC",
        (session_id,),
    )
    rows = c.fetchall()
    conn.close()

    return [
        {"sender": row[0], "content": row[1], "timestamp": row[2]}
        for row in rows
    ]


def delete_session(session_id: int):
    """Delete a session and all its messages."""
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("DELETE FROM messages WHERE session_id = ?", (session_id,))
    c.execute("DELETE FROM sessions WHERE id = ?", (session_id,))
    conn.commit()
    conn.close()


def get_session_title(session_id: int) -> str:
    """Get the title of a session."""
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("SELECT title FROM sessions WHERE id = ?", (session_id,))
    row = c.fetchone()
    conn.close()
    return row[0] if row else "Unknown"