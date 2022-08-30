FROM python:3.8

ARG PORT
ENV SERVER_PORT=$PORT

# Disables pip caching
ENV PIP_NO_CACHE_DIR=false

# Install dependencies
RUN apt-get update
RUN apt-get install -y git build-essential apt-utils wget libfreetype6 libpng-dev libopenblas-dev gcc gfortran
RUN python3 -m pip install pipenv

RUN mkdir /app
WORKDIR /app

# Install dependencies seperately, to utilize caching
RUN mkdir /app/aw-core
COPY aw-core/requirements.txt /app/aw-core
WORKDIR /app/aw-core
RUN pip install -r requirements.txt

RUN mkdir /app/aw-server
COPY aw-server/requirements.txt /app/aw-server
WORKDIR /app/aw-server
RUN pip install -r requirements.txt

# Build the rest
WORKDIR /app
COPY . /app

# Debugging, just for printing the build context
#RUN find /tmp/build

RUN make build SKIP_WEBUI=true

# Entrypoint
ENTRYPOINT ["/bin/sh", "-c"]
