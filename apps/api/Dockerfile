# Build context is the REPO ROOT (see docker-compose.yml's `context: .` /
# `dockerfile: apps/api/Dockerfile`), not ./apps/api. This is required because main.py now
# depends on the shared, reusable src/ packages (src.supervisor, src.agents, src.domain,
# src.services) in addition to apps/api's own transport-layer code — Docker cannot COPY from
# outside its build context, so a single-directory context can no longer reach both trees.
#
# apps/api/src is copied to /app/app_src and made importable as bare modules (main, api,
# config, observability) via --app-dir, exactly as before. Repo-root src/ is copied to
# /app/src and made importable as `src.*` via PYTHONPATH=/app. The two never collide: one is
# imported bare, the other under the `src.` prefix.

FROM python:3.12-slim

WORKDIR /app

COPY apps/api/pyproject.toml ./
RUN pip install --no-cache-dir \
    "fastapi>=0.115,<1" \
    "uvicorn[standard]>=0.30,<1" \
    "pydantic>=2.7,<3" \
    "pydantic-settings>=2.3,<3"

COPY apps/api/src ./app_src
COPY src ./src

ENV PYTHONPATH=/app

EXPOSE 8000

CMD ["uvicorn", "main:app", "--app-dir", "app_src", "--host", "0.0.0.0", "--port", "8000"]
