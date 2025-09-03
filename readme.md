# 🚍 Entebus Core Server

[![FastAPI](https://img.shields.io/badge/FastAPI-0.115+-009688?logo=fastapi)](https://fastapi.tiangolo.com/)
[![Docker](https://img.shields.io/badge/Docker-ready-0db7ed?logo=docker)](https://www.docker.com/)
[![Kubernetes](https://img.shields.io/badge/Kubernetes-ready-326ce5?logo=kubernetes)](https://kubernetes.io/)

The **Entebus Core Server** is a high-performance API server built with [FastAPI](https://fastapi.tiangolo.com/). It provides the backbone for managing transport-related data and services. Designed for **containerized environments** (Docker + Kubernetes), it ensures scalability, resilience, and modern developer experience.

## ✨ Features

- ⚡ **High-performance** API with FastAPI + Uvicorn  
- 🐘 **PostGIS support** for geospatial data  
- 📦 **MinIO integration** for object storage  
- 📊 **OpenObserve** for logs, metrics & traces  
- ⚡ **Redis support** for caching & queues  
- 🐳 Ready-to-use **Docker image** with CI-friendly tags  
- ☸️ Deployment ready for **Kubernetes**  

## 🛠️ Getting Started

### Prerequisites

- Ubuntu 22.04+ (WSL2 supported)  
- Python 3.12+  
- Docker
- Kubernetes (optional, for cluster deployment)  

### Local Development Setup

```
sudo apt-get update
sudo apt-get upgrade
sudo apt autoremove

# Install the libraries and tools
sudo apt-get install build-essential
sudo apt-get install libpq-dev
sudo apt install python3-pip
sudo apt-get install python3-venv

# Create a virtual environment and install required libraries
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### VS Code (plugins)

* Code Spell Checker (streetsidesoftware.code-spell-checker)
* GitLens (eamodio.gitlens)
* Python (ms-python.python)
* Black Formatter (ms-python.black-formatter)
* autoDocstring (njpwerner.autodocstring)

### Dependencies via Docker

**PostgreSQL + PostGIS**

```
docker run --name postgis \
    -e POSTGRES_PASSWORD=password \
    -p 5432:5432 \
    -d postgis/postgis
```

**MinIO (object storage)**

```
docker run --name minio \
    -e MINIO_ROOT_USER=minio \
    -e MINIO_ROOT_PASSWORD=password \
    -p 9000:9000 \
    -p 9001:9001 \
    -d minio/minio server /data --console-address ":9001"
```

**OpenObserve (logs, traces, metrics)**

```
docker run -d \
    --name openobserve \
    -p 5080:5080 \
    -e ZO_ROOT_USER_EMAIL="admin@entebus.com" \
    -e ZO_ROOT_USER_PASSWORD="password" \
    public.ecr.aws/zinclabs/openobserve:latest
```

**Redis DB**

```
docker run --name redis \
    -p 6379:6379 \
    -e REDIS_PASSWORD=password \
    -d redis
```

## 🚀 Running the Server

### Initialize Database & Test Data

```
# Create tables and buckets
python3 -m app.setup -cr

# Remove all tables and buckets
python3 -m app.setup -rm

# Initialize with sample data
python3 -m app.setup -init

# Populate test data (requires server running)
python3 -m app.setup -test
```

### Running server

The preferred server to run the FastAPI application is Uvicorn. You can access the API from http://127.0.0.1:8080/docs.
```
# Run with Uvicorn (hot reload enabled)
uvicorn app.main:app --port 8080 --reload
```

## 🐳 Docker Image

**Docker Image**

Build, run, and push the image:
The image is tagged using the format: `<branch-name>-<commit-id>` (for latest image you may add optional tag `<branch-name>-latest`).
```
# Building the docker image
docker build -t docker.nixbug.com/entebus/entebus-core-server:develop-052bd99 \
    -t docker.nixbug.com/entebus/entebus-core-server:develop-latest .

# Running the docker image
docker run -d --name entebus-core-server -p 8080:8080 docker.nixbug.com/entebus/entebus-core-server:develop-latest

# Login to remote docker repository (only needed once)
docker login docker.nixbug.com

# Push the docker image to nexus repository
docker push docker.nixbug.com/entebus/entebus-core-server:develop-latest
docker push docker.nixbug.com/entebus/entebus-core-server:develop-052bd99

# Pull the docker image from nexus repository
docker pull docker.nixbug.com/entebus/entebus-core-server:develop-latest
```

## 🤝 Contributing

Contributions are welcome! 🚀
Please check out our [Contributing Guide](CONTRIBUTING.md) for guidelines on setting up your dev environment, coding standards, and submitting PRs. This project follows a [Code of Conduct](CODE_OF_CONDUCT.md) to ensure a welcoming community for everyone.

## 📜 License

This project is licensed under the [MIT License](LICENSE).
Feel free to use, modify, and distribute under the terms of the license.

## 📧 Contact

Developed with ❤️ by Nixbug Softwares OPC Pvt Ltd (contact@nixbug.com).
For issues or feature requests, please open a GitHub issue.
