FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

COPY services/api/requirements.txt /tmp/api-requirements.txt
COPY services/ml/requirements.txt /tmp/ml-requirements.txt
COPY services/poke-mcp/requirements.txt /tmp/poke-mcp-requirements.txt
# Install api+ml deps first, then fastmcp (which upgrades httpx/fastapi to compatible versions)
RUN pip install --no-cache-dir -r /tmp/api-requirements.txt -r /tmp/ml-requirements.txt \
    && pip install --no-cache-dir -r /tmp/poke-mcp-requirements.txt

COPY . /app
ENV PYTHONPATH=/app/services/api:/app/services/ml:/app/services/poke-mcp

EXPOSE 8787

CMD ["python", "services/poke-mcp/server.py"]
