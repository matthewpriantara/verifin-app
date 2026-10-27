FROM python:3.12-slim
ENV PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1
WORKDIR /app
RUN pip install fastapi==0.115.6 uvicorn==0.34.0 requests==2.32.3 cryptography==44.0.0
COPY app.py /app/app.py
EXPOSE 8091
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8091"]
