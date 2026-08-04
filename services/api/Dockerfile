# API FastAPI — container de produção (item 3.4 da auditoria)
# Build context: raiz do repositório (services/ api e workers compartilham código).
FROM python:3.12-slim

# Dependências de sistema do WeasyPrint (Pango/GTK) para exportação de PDF.
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpango-1.0-0 \
    libpangoft2-1.0-0 \
    libpangocairo-1.0-0 \
    libgdk-pixbuf-2.0-0 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY services/api/requirements.txt /tmp/api-requirements.txt
RUN pip install --no-cache-dir -r /tmp/api-requirements.txt

# API + workers (a API reexporta models/services dos workers via sys.path).
COPY services/ /app/services/

WORKDIR /app/services/api
ENV PYTHONPATH=/app/services/api/src
EXPOSE 8000

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
