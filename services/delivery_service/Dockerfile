FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

COPY services/delivery_service/requirements.txt ./requirements.txt
RUN pip install --upgrade pip && pip install -r ./requirements.txt

COPY . .

EXPOSE 8004

CMD ["uvicorn", "services.delivery_service.src.main:app", "--host", "0.0.0.0", "--port", "8004"]
