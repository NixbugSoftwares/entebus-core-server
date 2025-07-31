FROM python:alpine

RUN apk add --no-cache \
    build-base \
    libpq-dev

# Copy requirements and install it
WORKDIR /code
COPY ./requirements.txt /code/requirements.txt

RUN pip install --no-cache-dir --upgrade -r /code/requirements.txt

# Copy app and run it
COPY ./app /code/app
WORKDIR /code/app
EXPOSE 8080

ENV PYTHONPATH=/code
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8080"]
