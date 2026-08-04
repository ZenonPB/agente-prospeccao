# Workers Python — coleta/enriquecimento/scoring (item 3.4 da auditoria)
# Build context: raiz do repositório.
FROM python:3.12-slim

WORKDIR /app

COPY services/workers/requirements.txt /tmp/workers-requirements.txt
RUN pip install --no-cache-dir -r /tmp/workers-requirements.txt

COPY services/ /app/services/

WORKDIR /app/services/workers
ENV PYTHONPATH=/app/services/workers/src

# Serviço contínuo: roda enriquecimento+scoring de leads pendentes a cada
# WORKER_POLL_SECONDS (default 600s). O pipeline disparado pela API roda no
# processo da API; este worker cobre a operação standalone.
CMD ["sh", "-c", "while true; do python -m src.main; sleep ${WORKER_POLL_SECONDS:-600}; done"]
