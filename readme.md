# Entebus Core Server 

This API server is built using FastAPI framework to provide a robust, efficient, and scalable solution for related tasks. FastAPI is chosen for its high performance, simplicity, and modern Python features. This application is designed to run as a Docker container in a Kubernetes environment for scalability, resilience, and easy deployment. Please ensure proper configuration and resource allocation in Kubernetes manifests to optimize performance and resource utilization.

## Development Windows 11 (WSL2 Ubuntu + Docker desktop + Kubernetes)
**Setup WSL2 Ubuntu**
- Ubuntu 22.04.3 LTS
- Python 3.12.3

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

**VS Code (plugins)**
* Code Spell Checker (streetsidesoftware.code-spell-checker)
* GitLens (eamodio.gitlens)
* Python (ms-python.python)
* Black Formatter (ms-python.black-formatter)
* autoDocstring (njpwerner.autodocstring)

**PostGIS DB**

The postgis/postgis image provides tags for running Postgres with PostGIS extensions installed. To run the Postgres container, use the following command:
```
docker run --name postgis \
    -e POSTGRES_PASSWORD=password \
    -p 5432:5432 \
    -d postgis/postgis
```

**MinIO**

The minio/minio is an object storage server that can be used to store and serve files. To run the MinIO container, use the following command:
```
docker run --name minio \
    -e MINIO_ROOT_USER=minio \
    -e MINIO_ROOT_PASSWORD=password \
    -p 9000:9000 \
    -p 9001:9001 \
    -d minio/minio server /data --console-address ":9001"
```

**OpenObserve**

The OpenObserve is used for monitoring logs, traces and metrics. To run the OpenObserve container, use the following command:
```
docker run -d \
    --name openobserve \
    -p 5080:5080 \
    -e ZO_ROOT_USER_EMAIL="admin@entebus.com" \
    -e ZO_ROOT_USER_PASSWORD="password" \
    public.ecr.aws/zinclabs/openobserve:latest
```

**Redis DB**

The redis image provides tags for running Redis DB. Redis is an in-memory key-value store, commonly used for caching, real-time analytics, session storage, and queue systems.
```
docker run --name redis \
    -p 6379:6379 \
    -e REDIS_PASSWORD=password \
    -d redis
```

For creating and removing the table and bucket you can use arguments `-cr` and `-rm`. For initializing the table with sample data you can use `-init`. For running the test the Postgres DB must be running and the tables should be created and initialized with sample data.
```
# Activate the python virtual environment
# Create all tables and buckets
python3 -m app.setup -cr
# Remove all tables and buckets
python3 -m app.setup -rm
# Initialize the table with sample data
python3 -m app.setup -init
```

**Running server**

The preferred server to run the FastAPI application is uvicorn. You can access the API from http://127.0.0.1:8080/docs.
```
# Activate the python virtual environment
# Start the server on port 8080 with hot reload
uvicorn app.main:app --port 8080 --reload
```

Once the server is running, you can populate test data using the API endpoints from a new terminal window.
```
# Populating Test Data
python3 -m app.setup -test
```

Once the server is running, you can run the tests against it using [entebus-api-test](https://github.com/NixbugSoftwares/entebus-api-test). For running the test the Postgres DB must be running and the tables should be created and initialized with sample data.

**Docker Image**

You can build the docker image and run it locally using Docker engine. Once running, the API will be available at http://127.0.0.1:8080/docs. The image is tagged using the format: `<branch-name>-<commit-id>` (for latest image you may add optional tag with `latest` instead of the commit ID).
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


