# FastAPI backend, deployed on Northflank (build context: backend/).

FROM python:3.11-slim

COPY --from=ghcr.io/astral-sh/uv:0.9.20 /uv /bin/uv
ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never \
    PYTHONUNBUFFERED=1

# Extra certificates for IFS servers that don't send their full chain.
# Linux doesn't fetch a missing intermediate the way Windows does, so it has
# to be in the system store. See certs/README.md.
RUN apt-get update \
 && apt-get install -y --no-install-recommends ca-certificates \
 && rm -rf /var/lib/apt/lists/*
COPY certs/*.crt /usr/local/share/ca-certificates/
RUN update-ca-certificates

WORKDIR /app
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project
COPY app ./app
COPY alembic.ini ./
COPY migrations ./migrations
# The IFS package customers download from the Approvals page.
COPY ifs_package ./ifs_package

RUN useradd --system --no-create-home app && mkdir /data && chown app /data
USER app

# SQLite lives in /data; mount a volume there. Set DATABASE_URL to use Postgres instead.
ENV PATH="/app/.venv/bin:$PATH" \
    DATABASE_URL=sqlite:////data/atronexus.db
EXPOSE 8000

# No --proxy-headers: the API is public, so X-Forwarded-For can't be trusted.
# The browser's IP arrives in X-Client-IP, which only counts with the
# internal key (app/internal.py).
CMD ["sh", "-c", "exec uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
