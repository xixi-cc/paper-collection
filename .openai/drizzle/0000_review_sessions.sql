CREATE TABLE IF NOT EXISTS review_sessions (
    session_id TEXT PRIMARY KEY,
    selected_ids TEXT NOT NULL DEFAULT '[]',
    current_page INTEGER NOT NULL DEFAULT 0,
    total_papers INTEGER NOT NULL DEFAULT 0,
    completed INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    completed_at TEXT
);

CREATE INDEX IF NOT EXISTS idx_review_sessions_completed_at
ON review_sessions(completed, completed_at);

PRAGMA optimize;
