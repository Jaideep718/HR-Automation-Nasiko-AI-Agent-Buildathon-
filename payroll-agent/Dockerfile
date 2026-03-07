FROM python:3.11-slim

WORKDIR /app

# Install dependencies first (better layer caching)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy source code
COPY src/ /app

# Set environment variables
ENV PYTHONUNBUFFERED=1

# Expose port
EXPOSE 5003

# Run the agent
CMD ["python", "__main__.py", "--host", "0.0.0.0", "--port", "5003"]
