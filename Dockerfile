FROM python:3.12-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    APP_ENV=production

WORKDIR /app

RUN addgroup --system app && adduser --system --ingroup app app

COPY requirements.txt ./
RUN pip install --upgrade pip && pip install -r requirements.txt

COPY src ./src
COPY run_api.py ./run_api.py
COPY run_pipeline.py ./run_pipeline.py
COPY data ./data
COPY models ./models
COPY outputs ./outputs

RUN chown -R app:app /app
USER app

EXPOSE 8001

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD-SHELL python -c "import os, urllib.request; port = os.getenv('PORT', '8001'); urllib.request.urlopen(f'http://127.0.0.1:{port}/api/v1/health/live', timeout=3)"

CMD ["sh", "-c", "python run_api.py --host 0.0.0.0 --port ${PORT:-8001}"]
