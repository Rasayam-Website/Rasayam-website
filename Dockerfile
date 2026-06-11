# ── Stage 1: build dependencies ──────────────────────────────────────────────
FROM python:3.12-slim AS builder

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends gcc libpq-dev \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --upgrade pip \
    && pip install --prefix=/install -r requirements.txt


# ── Stage 2: runtime image ────────────────────────────────────────────────────
FROM python:3.12-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PORT=8000 \
    PYTHONPATH=/app

WORKDIR /app

# Runtime libs only (no gcc)
RUN apt-get update \
    && apt-get install -y --no-install-recommends libpq5 \
    && rm -rf /var/lib/apt/lists/*

# Copy installed packages from builder
COPY --from=builder /install /usr/local

# Non-root user for security
RUN addgroup --system app && adduser --system --ingroup app app

COPY --chown=app:app . .

USER app

EXPOSE 8000

# entrypoint.sh is the single source of truth for startup logic
ENTRYPOINT ["sh", "entrypoint.sh"]
