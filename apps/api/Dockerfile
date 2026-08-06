FROM python:3.12-slim

WORKDIR /app

COPY pyproject.toml ./
RUN pip install --no-cache-dir \
    "fastapi>=0.115,<1" \
    "uvicorn[standard]>=0.30,<1" \
    "pydantic>=2.7,<3" \
    "pydantic-settings>=2.3,<3"

COPY src ./src

EXPOSE 8000

CMD ["uvicorn", "main:app", "--app-dir", "src", "--host", "0.0.0.0", "--port", "8000"]
