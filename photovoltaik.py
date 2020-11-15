#!/usr/bin/python

import requests
import sys
import shelve
import os
#from datetime import datetime as dt, date, timedelta
import datetime
import matplotlib.pyplot as plt
import matplotlib.ticker as plticker
import pandas as pd


today = datetime.date.today()
today = today.strftime("%d.%m.%Y")

MAX_DAYS = 14
url = 'http://192.168.178.58/cgi-bin/download.csv/'
path = os.path.join(os.path.expanduser("~/photovoltaik/"), 'pv_daten') #path to db
WR1_TEXT = 'SG45T2.1.20'
WR2_TEXT = 'SGl10k.1.10'

def main():
    #start_date, end_date = get_date()
    start_date = '01.11.2011'
    end_date = '10.11.2020'
    get_values_from_pv(start_date, end_date)
    #make_graph()


def make_graph():
    global path, WR1_TEXT, WR2_TEXT

    data = shelve.open(path)
    for k, item in sorted(data.items(), key=lambda x: (datetime.datetime.strptime(x[0][:10], '%d.%m.%Y')), reverse=True):
        #print (k)
        pass
    
    df = pd.DataFrame(columns=('Datum', 'Jahr', 'HausGesamt', 'WR1', 'WR2'))
    i=0
    for k, item in sorted(data.items(), key=lambda x: (datetime.datetime.strptime(x[0][:10], '%d.%m.%Y')), reverse=True):
        df.loc[i] = [k, int(k[6:10]), item[0], item[1], item[2]]
        i+=1

    #print (df.tail(7))
    df['year_sum'] = df.groupby(["Jahr"])["HausGesamt"].sum()
    print (df.tail(7))

    #exit()

    f = plt.figure(figsize = (20, 8))
    plt.style.use('dark_background')
    #move_figure(f, 540, 0)

    ''' letzten x Tage ausgeben '''
    latest_x_days = df.tail(7)

    ax = plt.subplot(111)

  

def get_date():
    global path
    #read max date from shelve db
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

    print (f'getting data for {start_date} - {end_date}')
    return start_date, end_date

def get_values_from_pv(start_date, end_date):
    global url, headers, data, path

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
    
    #writing data to database
    with shelve.open(path) as db:
        for k, v in values.items():
            db[k]= v
            print (f'Datum {k} - Werte {v}')



main()



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