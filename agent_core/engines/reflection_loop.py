
import sqlite3

class ReflectionLoop:
    def __init__(self, db_path: str = "reflection.db"):
        self.db = sqlite3.connect(db_path)
        self.learning_rate = 0.1
        self.discount_factor = 0.9
        self._init_db()

    def _init_db(self):
        cursor = self.db.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS action_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                task_hash TEXT,
                action_taken TEXT,
                decision_state_hash TEXT,
                outcome REAL,
                reward_signal REAL
            )
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS decision_weights (
                state_hash TEXT,
                action TEXT,
                q_value REAL,
                PRIMARY KEY (state_hash, action)
            )
        """)
        self.db.commit()

    def log_action(self, task_hash, action, state_hash, outcome, uncertainty_penalty):
        reward = outcome - uncertainty_penalty
        cursor = self.db.cursor()
        cursor.execute(
            "INSERT INTO action_log (task_hash, action_taken, decision_state_hash, outcome, reward_signal) VALUES (?, ?, ?, ?, ?)",
            (task_hash, action, state_hash, outcome, reward)
        )
        self.db.commit()

    def get_best_action(self, state_hash, possible_actions):
        cursor = self.db.cursor()
        best_action, best_q = None, -float("inf")
        for action in possible_actions:
            cursor.execute("SELECT q_value FROM decision_weights WHERE state_hash=? AND action=?", (state_hash, action))
            result = cursor.fetchone()
            q = result[0] if result else 0.0
            if q > best_q:
                best_q = q
                best_action = action
        return best_action if best_action else (possible_actions[0] if possible_actions else None)

