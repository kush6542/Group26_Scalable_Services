FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

COPY services/restaurant_service/requirements.txt ./requirements.txt
RUN pip install --upgrade pip && pip install -r ./requirements.txt

COPY . .

EXPOSE 8002

CMD ["uvicorn", "services.restaurant_service.src.main:app", "--host", "0.0.0.0", "--port", "8002"]
