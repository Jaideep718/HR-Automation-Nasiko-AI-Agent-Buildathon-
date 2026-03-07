FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY offboarding-agent/src/ /app

ENV PYTHONUNBUFFERED=1

EXPOSE 5000

CMD ["python", "__main__.py", "--host", "0.0.0.0", "--port", "5000"]
