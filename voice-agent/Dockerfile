FROM python:3.11-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY agent.py .

RUN useradd --create-home --uid 10001 agent
USER agent

CMD ["python", "agent.py", "start"]
