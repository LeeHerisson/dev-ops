FROM python:3.11-slim AS base
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt \
    && useradd --uid 10001 --create-home appuser
COPY app.py config.py ./

FROM base AS test
COPY tests/ tests/
RUN python -m unittest discover -s tests -v

FROM base AS runtime
ENV APP_ENV=production DEBUG=false
USER 10001:10001
EXPOSE 5000
STOPSIGNAL SIGINT
CMD ["python", "app.py"]
