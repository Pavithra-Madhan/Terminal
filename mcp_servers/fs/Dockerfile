FROM python:3.11-slim

# Install sqlite3 and dependencies
RUN apt-get update && apt-get install -y sqlite3 libsqlite3-dev && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY server.py .
COPY system.db .
COPY memory.db .

RUN pip install --no-cache-dir fastapi uvicorn pydantic

# Verify databases exist and are valid
RUN sqlite3 /app/system.db "SELECT COUNT(*) FROM files;" && \
    sqlite3 /app/memory.db "SELECT COUNT(*) FROM user_preferences;" && \
    echo "Databases verified successfully"

CMD ["uvicorn", "server:app", "--host", "0.0.0.0", "--port", "8000"]
