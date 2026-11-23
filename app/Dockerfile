# VULN (container scan): old, end-of-life base image with many OS-level CVEs
FROM python:3.8-slim-buster

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY app.py .

EXPOSE 5000
# VULN (container scan): no USER instruction, so the app runs as root
CMD ["python", "app.py"]
