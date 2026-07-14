# Jikgu Customs Assistant (직구 관세 비서) MCP server
FROM python:3.11-slim

WORKDIR /app

# Dependencies first for layer caching
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Application code
COPY jikgu ./jikgu
COPY server.py .

EXPOSE 8000

# Streamable HTTP, stateless, bound to all interfaces for container use
CMD ["python", "server.py"]
