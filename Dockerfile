FROM python:3.11-slim
WORKDIR /srv
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY rag rag
COPY data data
EXPOSE 8000
CMD ["uvicorn", "rag.api:app", "--host", "0.0.0.0", "--port", "8000"]
