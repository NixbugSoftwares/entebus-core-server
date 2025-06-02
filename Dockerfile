# Install base OS
FROM ubuntu:latest
RUN apt-get update && apt-get -y install \
    build-essential libpq-dev python3-pip

# Copy requirements and install it
WORKDIR /code
COPY ./requirements.txt /code/requirements.txt

RUN pip install --no-cache-dir --upgrade -r /code/requirements.txt \
    --break-system-packages

# Copy app and run it
COPY ./app /code/app
WORKDIR /code/app
EXPOSE 8080

ENV PYTHONPATH=/code
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8080"]
