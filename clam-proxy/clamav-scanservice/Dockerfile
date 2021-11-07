FROM python:3.8

RUN apt-get update && apt-get install -y \
    clamav \
    clamav-daemon \
 && rm -rf /var/lib/apt/lists/*


WORKDIR /opt/src

COPY requirements.txt /opt/src/requirements.txt
COPY clamd.remote.conf /opt/src/clamd.remote.conf


RUN pip install --no-cache-dir --upgrade -r /opt/src/requirements.txt

COPY src /opt/src/

EXPOSE 80

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "80", "--proxy-headers"]

