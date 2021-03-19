FROM python:3.9-slim
WORKDIR /home/mike/photovoltaik/

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY photovoltaik.py /home/mike/photovoltaik/

ENTRYPOINT ["python", "./photovoltaik.py" ]