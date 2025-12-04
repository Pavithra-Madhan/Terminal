FROM python:3.12-slim
WORKDIR /app
COPY server.py .
RUN pip install --no-cache-dir fastapi uvicorn pydantic requests
EXPOSE 8000
CMD ["python", "server.py"]
