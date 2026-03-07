FROM python:3.11-slim

WORKDIR /app

# Copy source code
COPY src/ /app

# Install dependencies
RUN pip install --no-cache-dir \
    fastapi>=0.109.0 \
    uvicorn>=0.27.0 \
    pydantic>=2.6.0 \
    python-dotenv>=1.0.0 \
    requests>=2.31.0 \
    "langchain>=0.2.0,<0.3.0" \
    "langchain-openai>=0.1.0,<0.2.0" \
    click>=8.1.7

# Set environment variables
ENV PYTHONUNBUFFERED=1

# Expose port
EXPOSE 5000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:5000/health')" || exit 1

# Run the agent
CMD ["python", "__main__.py", "--host", "0.0.0.0", "--port", "5000"]
