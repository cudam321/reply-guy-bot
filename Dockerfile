FROM mcr.microsoft.com/playwright/python:v1.49.1-noble

WORKDIR /app

# Ensure Python output is sent straight to terminal (no buffering)
ENV PYTHONUNBUFFERED=1

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
RUN playwright install chromium

COPY . .

CMD ["python3", "main.py"]
