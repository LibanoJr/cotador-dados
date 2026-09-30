FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
EXPOSE 8000
# Demonstração: migra, gera amostras fictícias, publica a linha de base e sobe o servidor.
# Produção: trocar runserver por gunicorn (ver docs/02-planejamento.md).
CMD ["sh", "-c", "python manage.py migrate && python manage.py seed_demo && python manage.py runserver 0.0.0.0:8000"]
