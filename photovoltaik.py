#!/usr/bin/python

import requests
import sys
import shelve
import os
#from datetime import datetime as dt, date, timedelta
import datetime

today = datetime.date.today()
today = today.strftime("%d.%m.%Y")

MAX_DAYS = 14

#read max date from shelve db
path = os.path.join(os.path.expanduser("~/photovoltaik/"), 'pv_daten')
data = shelve.open(path)
for k, item in sorted(data.items(), key=lambda x: (datetime.datetime.strptime(x[0][:10], '%d.%m.%Y')), reverse=True):
    last_date = k[0:10]
    break

try:
    print (f'last date value already in database - {last_date}')
    start_date = datetime.datetime.strptime(last_date, '%d.%m.%Y') + datetime.timedelta(days=1)
    start_date = str(start_date.strftime("%d.%m.%Y"))[0:10]
    end_date = today
except:
    print (f'database has no values yet')
    start_date = datetime.datetime.strptime(today, '%d.%m.%Y') - datetime.timedelta(days=MAX_DAYS)
    start_date = str(start_date.strftime("%d.%m.%Y"))[0:10]
    end_date = today

print (f'Start: {start_date} - Ende: {end_date}')


url = 'http://192.168.178.58/cgi-bin/download.csv/'
# headers = {
#     'User-Agent': 'Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:82.0) Gecko/20100101 Firefox/82.0',
#     'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
#     'Accept-Language': 'en-US,en;q=0.5',
#     'Content-Type': 'application/x-www-form-urlencoded',
#     'Origin': 'http://192.168.178.58',
#     'Connection': 'keep-alive',
#     'Referer': 'http://192.168.178.58/cgi-bin/download.cgi',
#     'Upgrade-Insecure-Requests': '1',
# }
headers={}

data = {
  'aggregate': 'day',
  'start_day': start_date,
  'start_time': '00:00',
  'end_day': end_date,
  'end_time': '00:00'
}

response = requests.post(url,headers=headers, data=data, allow_redirects=False)

for k, v in response.__dict__.items():
    if k == '_content':
        line = v.decode("utf-8")

data = line.split('\n')   
kwh_data = data[5:]

wr1_text = 'SGl10k.1.10'
wr2_text = 'SG45T2.1.20'
values = {}
for item in kwh_data:
    line_item = item.split(';')
    if len(line_item) == 4:
        datum      = line_item[0]
        wr_gesamt  = line_item[1]
        wr1        = line_item[2]
        wr2        = line_item[3]

        value_dict = { datum: [wr_gesamt, wr1, wr2] }
        values.update(value_dict)


path = os.path.join(os.path.expanduser("~/photovoltaik/"), 'pv_daten')
with shelve.open(path) as db:
    for k, v in values.items():
        db[k]= v
        print (f'Datum {k} - Werte {v}')