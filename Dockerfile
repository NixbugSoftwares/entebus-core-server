# Build dependencies
FROM python:alpine AS builder

# Install build dependencies
RUN apk add --no-cache \
    build-base \
    libpq-dev \
    libffi-dev \
    openssl-dev \
    proj-dev \
    geos-dev \
    rust \
    cargo

# Set work directory
WORKDIR /code

# Install dependencies
COPY requirements.txt .
RUN pip install --prefix=/code/deps --no-cache-dir -r requirements.txt

# Final slim image
FROM python:alpine
RUN apk add --no-cache \
    libpq \
    libffi \
    openssl \
    proj \
    geos

# Only copy installed packages from builder
COPY --from=builder /code/deps /usr/local

# Copy app source code
COPY ./app /code/app
WORKDIR /code/app

# Expose the port
EXPOSE 8080

ENV PYTHONPATH=/code
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8080"]
