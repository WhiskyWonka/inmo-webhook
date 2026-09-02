FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
RUN chmod +x /app/entrypoint.sh
ENV VERIFY_TOKEN=""
EXPOSE 8000
ENTRYPOINT ["./entrypoint.sh"]
