
CREATE TABLE IF NOT EXISTS action_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
    task_hash TEXT,
    action_taken TEXT,
    decision_state_hash TEXT,
    outcome REAL,
    reward_signal REAL
);

CREATE TABLE IF NOT EXISTS decision_weights (
    state_hash TEXT PRIMARY KEY,
    action TEXT,
    q_value REAL,
    last_updated DATETIME DEFAULT CURRENT_TIMESTAMP
);

