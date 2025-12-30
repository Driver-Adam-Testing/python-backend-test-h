FROM --platform=linux/amd64 python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
 POETRY_VERSION=2.1.3 \
 HATCHET_ENV=production

# Install system dependencies and Poetry
# libgit2-dev is required for pygit2 (analytics service)
RUN apt-get update && \
 apt-get install -y curl nano ripgrep ghostscript git libgit2-dev && \
 curl -sSL https://install.python-poetry.org | python3 - && \
 ln -s /root/.local/bin/poetry /usr/local/bin/poetry && \
 apt-get clean && \
 rm -rf /var/lib/apt/lists/\*

 RUN python -m pip install --upgrade pip setuptools wheel

WORKDIR /app

COPY driver_db /driver_db
COPY packages /packages
COPY content_services /app
COPY content_services/analytics /app/analytics
COPY backend/scripts/ /app/scripts/
COPY content_services/src/inspector/uctags-2024.10.02-linux-x86_64/bin/ctags /ctags

RUN poetry config virtualenvs.create false && \
 poetry install --no-root --no-interaction --no-ansi

COPY content_services/start.sh /start.sh
RUN chmod +x /start.sh

# Copy the setEnv.sh if using the deployment repo
COPY setEnv.sh* /

# Capture Git info at build time
ARG GIT_COMMIT
ARG GIT_BRANCH

# Set environment variables
ENV GIT_COMMIT=${GIT_COMMIT}
ENV GIT_BRANCH=${GIT_BRANCH}

CMD [ "/bin/sh", "-c", "/start.sh" ]
