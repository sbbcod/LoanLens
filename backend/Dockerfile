# LoanLens API image. Built by GitHub Actions, pushed to GitHub Container Registry,
# run on Azure Container Apps.

FROM python:3.12-slim-bookworm

# Microsoft's ODBC driver, needed to talk to Azure SQL.
RUN apt-get update \
 && apt-get install -y --no-install-recommends curl gnupg ca-certificates \
 && curl -fsSL https://packages.microsoft.com/keys/microsoft.asc \
    | gpg --dearmor -o /usr/share/keyrings/microsoft-prod.gpg \
 && curl -fsSL https://packages.microsoft.com/config/debian/12/prod.list \
    -o /etc/apt/sources.list.d/mssql-release.list \
 && apt-get update \
 && ACCEPT_EULA=Y apt-get install -y --no-install-recommends msodbcsql18 unixodbc \
 && apt-get purge -y curl gnupg && apt-get autoremove -y \
 && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Dependencies first, so code changes don't reinstall them.
COPY pyproject.toml ./
RUN mkdir app && touch app/__init__.py \
 && pip install --no-cache-dir ".[azure]" \
 && rm -rf app

COPY app ./app
COPY data ./data
COPY scripts ./scripts

# Don't run as root.
RUN useradd --create-home loanlens && mkdir -p /app/.llm_cache && chown -R loanlens /app
USER loanlens

ENV PYTHONUNBUFFERED=1 \
    LLM_CACHE_DIR=/app/.llm_cache

EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers", "--forwarded-allow-ips=*"]
