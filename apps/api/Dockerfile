FROM python:3.13-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt \
    && groupadd --gid 10001 roadsignal \
    && useradd --uid 10001 --gid roadsignal --no-create-home --shell /usr/sbin/nologin roadsignal
COPY --chown=roadsignal:roadsignal . .
RUN sed -i 's/\r$//' scripts/start-api.sh && chmod 0555 scripts/start-api.sh
USER 10001:10001
EXPOSE 8000
CMD ["./scripts/start-api.sh"]