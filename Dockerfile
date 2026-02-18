# Use official Python runtime as a parent image
FROM python:3.10

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Set work directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Install python dependencies
COPY requirements.txt .
RUN pip install --upgrade pip setuptools wheel
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY src/ ./src/
COPY portfolio.json .

# Expose port (Cloud Run defaults to 8080)
EXPOSE 8080

# Run the server
# We use 'src.server:app' because server.py is inside src/
# Adjust PYTHONPATH to include /app/src
ENV PYTHONPATH=/app/src

CMD ["uvicorn", "src.server:app", "--host", "0.0.0.0", "--port", "8080"]
