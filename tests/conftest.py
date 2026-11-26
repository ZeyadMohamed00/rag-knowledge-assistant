import os
import tempfile

import pgserver  # embedded real PostgreSQL 16 + pgvector for tests

srv = pgserver.get_server(tempfile.mkdtemp())
os.environ["DATABASE_URL"] = srv.get_uri().replace("postgresql://", "postgresql+psycopg2://", 1)
os.environ.pop("OPENAI_API_KEY", None)
