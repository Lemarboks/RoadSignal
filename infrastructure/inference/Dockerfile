FROM python:3.12-slim AS base
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 HF_HOME=/models HF_HUB_DISABLE_TELEMETRY=1 DO_NOT_TRACK=1
WORKDIR /service
RUN groupadd --gid 10001 inference && useradd --uid 10001 --gid inference --no-create-home inference \
    && mkdir /models && chown inference:inference /models
COPY requirements-base.txt .
RUN pip install --no-cache-dir -r requirements-base.txt
COPY server.py .

FROM base AS retrieval
RUN pip install --no-cache-dir torch==2.8.0 --index-url https://download.pytorch.org/whl/cpu \
    && pip install --no-cache-dir transformers==4.56.2
USER 10001:10001
EXPOSE 8080
CMD ["uvicorn", "server:app", "--host", "0.0.0.0", "--port", "8080", "--limit-concurrency", "8"]

FROM base AS voice
RUN pip install --no-cache-dir faster-whisper==1.2.1
USER 10001:10001
EXPOSE 8080
CMD ["uvicorn", "server:app", "--host", "0.0.0.0", "--port", "8080", "--limit-concurrency", "8"]
