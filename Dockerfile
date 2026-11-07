FROM python:3.13-slim
WORKDIR /app
COPY publish.py queue.json ./
CMD ["python", "publish.py"]
