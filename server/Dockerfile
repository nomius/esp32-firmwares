FROM python:3.12-slim

RUN python3 -m venv /opt/venv

# Install dependencies:
COPY requirements.txt .
RUN . /opt/venv/bin/activate && pip install -r requirements.txt

EXPOSE 8080
WORKDIR /app
CMD . /opt/venv/bin/activate && exec python ./server.py
