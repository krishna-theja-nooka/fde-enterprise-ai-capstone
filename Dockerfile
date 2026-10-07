FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 FLEET_DB_PATH=/app/runtime/fleet.db
WORKDIR /app
COPY requirements.lock pyproject.toml ./
RUN python -m pip install --no-cache-dir -r requirements.lock
COPY fleet ./fleet
RUN python -m pip install --no-cache-dir --no-deps . \
    && useradd --uid 10001 --create-home fleet \
    && mkdir -p /app/runtime && chown -R fleet:fleet /app/runtime
USER fleet
EXPOSE 8000
CMD ["python", "-m", "uvicorn", "fleet.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1", "--no-proxy-headers"]

