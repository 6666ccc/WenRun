FROM python:3.13-slim
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1 HF_HOME=/app/data/huggingface
WORKDIR /app
COPY ai-python/requirements.lock ./
RUN pip install --no-cache-dir -r requirements.lock
COPY ai-python/app ./app
RUN useradd --uid 10001 --create-home app && mkdir -p /app/data && chown -R app:app /app
USER 10001
EXPOSE 8000
# One process owns the embedded Chroma index and lifecycle worker.
CMD ["python", "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1", "--timeout-graceful-shutdown", "30"]
HEALTHCHECK --interval=30s --timeout=8s --start-period=120s CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/ready', timeout=6)" || exit 1
