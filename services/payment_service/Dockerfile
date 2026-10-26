FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

COPY services/payment_service/requirements.txt ./requirements.txt
RUN pip install --upgrade pip && pip install -r ./requirements.txt

COPY . .

EXPOSE 8003

CMD ["uvicorn", "services.payment_service.src.main:app", "--host", "0.0.0.0", "--port", "8003"]
