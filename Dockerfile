FROM mcr.microsoft.com/playwright/python:v1.41.0-jammy

WORKDIR /app

COPY requirements.txt .
RUN apt-get update -y && apt-get upgrade -y \
    && pip3 install -U pip \
    && pip3 install -U -r requirements.txt --no-cache-dir
#RUN pip install --no-cache-dir -r requirements.txt

RUN playwright install chromium

COPY . .

CMD ["python3", "psp.py"]
