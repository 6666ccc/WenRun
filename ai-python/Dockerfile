FROM python:3.11-slim
WORKDIR /app
COPY pyproject.toml requirements.txt ./
COPY app app
RUN pip install --no-cache-dir \
    "python-dotenv>=1.0.0" \
    "fastapi>=0.115.0" \
    "uvicorn[standard]>=0.32.0" \
    "httpx>=0.27.0" \
    "qdrant-client>=1.12.0" \
    "pypdf>=5.0.0" \
    "python-docx>=1.1.0" \
    "python-multipart>=0.0.9" \
    "loguru>=0.7.0"
EXPOSE 8000
CMD ["python", "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
