# Spike-only fake OpenAI-compatible upstream. Not a production image pin surface.
FROM python:3.12-alpine
WORKDIR /app
COPY server.py /app/server.py
EXPOSE 8080
CMD ["python", "/app/server.py"]
