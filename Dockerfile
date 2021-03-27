FROM python:3.9-slim
WORKDIR /photovoltaik/

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY photovoltaik_with_vpn_raspi.py /photovoltaik/

ENTRYPOINT ["python", "./photovoltaik_with_vpn_raspi.py" ]
