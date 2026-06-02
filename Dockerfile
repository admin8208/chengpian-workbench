FROM node:20-alpine AS web-builder
WORKDIR /app
COPY apps/web/package*.json apps/web/
RUN cd apps/web && npm ci --ignore-scripts
COPY apps/web/ apps/web/
RUN cd apps/web && npm run build

FROM python:3.12-slim
RUN apt-get update && apt-get install -y ffmpeg && rm -rf /var/lib/apt/lists/*
WORKDIR /app

COPY apps/api/requirements.txt apps/api/
RUN pip install --no-cache-dir -r apps/api/requirements.txt --extra-index-url https://download.pytorch.org/whl/cpu

COPY . .
COPY --from=web-builder /app/apps/web/dist apps/web/dist

RUN adduser --disabled-password --gecos '' chengpian && chown -R chengpian:chengpian /app
USER chengpian

EXPOSE 8010
