# Dockerfile

# pull the official docker image
#FROM python:3.9-slim
FROM python:3.11-slim

# set work directory
WORKDIR /app

# set env variables
ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1

RUN apt update && apt install nano -y
# install dependencies
COPY requirements.txt .
RUN pip3 install -r requirements.txt

# 🔽 Coqui TTS + ecosistema completo
RUN pip3 install --no-cache-dir \
        TTS==0.22.0 \
        transformers==4.39.3 \
        sentencepiece==0.2.0 \
        protobuf==4.24.4
    # OJO: aquí NO ponemos --no-deps, que es lo que te estaba matando
 
# copy project
COPY . .
