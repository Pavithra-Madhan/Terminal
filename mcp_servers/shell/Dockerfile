FROM python:3.12-slim
WORKDIR /app
# Install dependencies, including uvicorn[standard] for running FastAPI
RUN pip install --no-cache-dir fastapi uvicorn[standard] pydantic httpx
# Copy the specific server file
COPY server.py .
EXPOSE 8000
# CMD runs Uvicorn, binding the 'app' object in the 'server.py' file
CMD ["uvicorn", "server:app", "--host", "0.0.0.0", "--port", "8000"]