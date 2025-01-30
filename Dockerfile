FROM python:3.12-slim

# Set environment variables
ENV PYTHONFAULTHANDLER=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONHASHSEED=random \
    PIP_NO_CACHE_DIR=off \
    PIP_DISABLE_PIP_VERSION_CHECK=on \
    PIP_DEFAULT_TIMEOUT=100 \
    POETRY_VERSION=1.7.1

# Install system dependencies including supervisord
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        curl \
        build-essential \
        supervisor \
    && rm -rf /var/lib/apt/lists/*

# Install poetry
RUN curl -sSL https://install.python-poetry.org | python3 -

# Set working directory
WORKDIR /app

# Copy poetry files
COPY pyproject.toml poetry.lock ./

# Install dependencies
RUN poetry config virtualenvs.create false \
    && poetry install --no-interaction --no-ansi --no-root

# Copy project files
COPY . .

# Install project
RUN poetry install --no-interaction --no-ansi

# Create log directory
RUN mkdir -p /var/log

# Copy supervisord config
COPY supervisord.conf /etc/supervisor/conf.d/

# Set entrypoint
ENTRYPOINT ["supervisord", "-c", "/etc/supervisor/conf.d/supervisord.conf"]
