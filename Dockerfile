FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app
COPY pyproject.toml README.md LICENSE ./
COPY src ./src
RUN pip install --no-cache-dir . && useradd --uid 10001 --create-home wildlife
COPY data ./data
COPY configs ./configs
RUN mkdir -p /app/var && chown wildlife:wildlife /app/var
USER 10001:10001
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=3s CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/healthz',timeout=2)"
CMD ["python", "-m", "src.main", "--config", "configs/pilot.yaml", "serve", "--host", "0.0.0.0"]
