FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

RUN pip install --no-cache-dir pandas>=2.0

COPY docker/sandbox_runner.py /sandbox_runner.py

USER nobody
WORKDIR /tmp
