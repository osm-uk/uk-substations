FROM python:3.15-slim

RUN mkdir /app  
WORKDIR /app
COPY ./requirements.txt .
COPY ./requirements*.txt .
RUN pip install --upgrade pip && pip install -r requirements.txt && pip install -r requirements-dev.txt
ENV PYTHONDONTWRITEBYTECODE 1
