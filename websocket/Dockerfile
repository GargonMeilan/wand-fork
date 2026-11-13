FROM python:3.12.12-slim-bookworm
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY start.py .
USER 65534:65534
EXPOSE 8080
CMD ["python", "start.py"]
