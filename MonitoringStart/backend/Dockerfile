# Stage 1: Build Environment (using a full python image)
FROM python:3.12-slim AS builder

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Install dependencies (Gunicorn is now required for production)
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Stage 2: Final Production Image (using a minimal runtime)
FROM python:3.12-slim

# Set the working directory
WORKDIR /app

# Copy only the necessary runtime files from the builder stage
COPY --from=builder /usr/local/lib/python3.12/site-packages /usr/local/lib/python3.12/site-packages
COPY --from=builder /usr/local/bin/gunicorn /usr/local/bin/gunicorn

# Copy application code
COPY ./backend/main.py .
COPY ./backend/api/ ./api/

# Expose the default container port
EXPOSE 8000

# Production Start Command: Use Gunicorn to manage Uvicorn workers
# -k uvicorn.workers.UvicornWorker: Specifies Uvicorn for ASGI compatibility
# -w 4: Starts 4 worker processes (adjust based on CPU cores, 2x + 1 is a common rule)
# main:app: Points to the FastAPI application instance
CMD ["gunicorn", "-k", "uvicorn.workers.UvicornWorker", "-w", "4", "main:app", "--bind", "0.0.0.0:8000"]