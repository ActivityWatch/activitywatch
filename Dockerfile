# This Dockerfile is used to build ActivityWatch in a Docker container.
#
# It lets us to build ActivityWatch on any platform that supports Docker,
# it also provides a way to build arm64 releases (not possible with GitHub Actions).

# TODO: Clean up this Dockerfile, it's a mess
# TODO: make use of multi-stage builds
# TODO: Avoid building aw-webui twice
# TODO: Fix aw-server-rust rebuilding in last step
FROM ubuntu:22.10

ARG PORT
ENV SERVER_PORT=$PORT

# Disables pip caching
ENV PIP_NO_CACHE_DIR=false

# Install dependencies
RUN apt-get update
RUN apt-get install -y python3 python3-distutils python3-pip python3-pyqt6 git build-essential apt-utils wget libfreetype6 libpng-dev libopenblas-dev gcc gfortran curl sudo zip

# Add `python` alias for `python3`
RUN ln -s /usr/bin/python3 /usr/bin/python

# Add nodejs repo
RUN curl -fsSL https://deb.nodesource.com/setup_18.x | sudo -E bash -
RUN apt-get install -y nodejs

# Install rustup
RUN curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh -s -- --default-toolchain none -y
ENV PATH="/root/.cargo/bin:$PATH"
RUN rustup toolchain install nightly --allow-downgrade --profile minimal

# Set up poetry
RUN curl -sSL https://install.python-poetry.org | python3 -
ENV PATH="/root/.local/bin:$PATH"
RUN poetry config virtualenvs.create false

# Create build directory
RUN mkdir /app
WORKDIR /app

# Install dependencies seperately, to utilize caching
RUN mkdir /app/aw-core
COPY aw-core/poetry.lock aw-core/pyproject.toml /app/aw-core
WORKDIR /app/aw-core
RUN poetry install --no-root && rm -rf ~/.cache/pypoetry/{cache,artifacts}

RUN mkdir /app/aw-server
COPY aw-server/poetry.lock aw-server/pyproject.toml /app/aw-server
WORKDIR /app/aw-server
RUN poetry install --no-root && rm -rf ~/.cache/pypoetry/{cache,artifacts}

# Set wether to build in release mode or not
ENV RELEASE=false

RUN mkdir /app/aw-server-rust
COPY aw-server-rust/. /app/aw-server-rust
WORKDIR /app/aw-server-rust
RUN --mount=type=cache,target=/app/aw-server-rust/target \
            make build SKIP_WEBUI=true

# Build the webui
#RUN mkdir /app/aw-server/aw-webui
#COPY aw-server/aw-webui/. /app/aw-server/aw-webui
#WORKDIR /app/aw-server/aw-webui
#RUN --mount=type=cache,target=/root/.npm \
#            make build

# Build the rest
WORKDIR /app
COPY . /app

#RUN make build SKIP_WEBUI=true

RUN poetry install --no-root
# NOTE: we have to skip aw-qt because there's no arm64 wheel for pyqt6 on PyPI
RUN --mount=type=cache,target=/app/aw-server-rust/target \
    --mount=type=cache,target=/root/.npm \
            make build SKIP_QT=true
RUN --mount=type=cache,target=/app/aw-server-rust/target \
            make package SKIP_QT=true

# Cleanup
RUN rm -rf ~/.cache/pypoetry/{cache,artifacts}
RUN rm -rf /app/aw-server-rust/target

# Entrypoint
ENTRYPOINT ["/bin/sh", "-c"]
