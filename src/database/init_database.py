import sqlite3
from utils.envvars import EnvVars


def init_db():
    """Initialize database with required tables."""
    env_vars = EnvVars()
    conn = sqlite3.connect(env_vars.database_url)

    with open('schema.sql', 'r') as f:
        conn.executescript(f.read())
    conn.commit()
    conn.close()
