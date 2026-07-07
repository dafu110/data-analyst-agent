FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app
ARG INSTALL_EXTRAS=""

RUN apt-get update \
    && apt-get install -y --no-install-recommends docker.io fonts-wqy-microhei fonts-noto-cjk fontconfig \
    && fc-cache -f \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml README.md ./
COPY backend ./backend
COPY data_analyst_agent ./data_analyst_agent
COPY frontend ./frontend
COPY examples ./examples
COPY evals ./evals
COPY tests ./tests

RUN if [ -n "$INSTALL_EXTRAS" ]; then pip install --no-cache-dir ".[${INSTALL_EXTRAS}]"; else pip install --no-cache-dir .; fi
RUN if [ -n "$INSTALL_EXTRAS" ]; then python -m backend.production_check; fi

EXPOSE 8000

CMD ["python", "-m", "backend.server", "--host", "0.0.0.0", "--port", "8000"]
