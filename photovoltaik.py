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
import numpy as np
from collections import Counter

today = datetime.date.today()
today = today.strftime("%d.%m.%Y")

MAX_DAYS = 14
url = 'http://192.168.178.58/cgi-bin/download.csv/'
path = os.path.join(os.path.expanduser("~/photovoltaik/"), 'pv_daten') #path to db
WR1_TEXT = 'SG45T2.1.20'
WR2_TEXT = 'SGl10k.1.10'

def main():
    #start_date, end_date = get_date()
    #get_values_from_pv(start_date, end_date)
    make_graph()


def make_graph():
    global path, WR1_TEXT, WR2_TEXT

    pv_data = shelve.open(path)
    filename = 'values.xlsx'
    datafile = open(filename, 'w')
    datafile.write('Datum\tJahr\tMonatabs\tMonat\tHausgesamt\tWR1\tWR2\n')
    
    df = pd.DataFrame(columns=('Datum', 'Jahr', 'Monatabs', 'Monat', 'HausGesamt', 'WR1', 'WR2'))
    i=0
    for k, item in sorted(pv_data.items(), key=lambda x: (datetime.datetime.strptime(x[0][:10], '%d.%m.%Y')), reverse=False):
        jahr       = int(k[6:10])
        monatabs   = str(k[6:10]+k[3:5])
        monat      = int(k[3:5])
        #hausgesamt = float(int(item[0])/int(1000))
        hausgesamt = int(item[0]) / 1000
        #hausgesamt_anz= str(hausgesamt).replace('.','')
        wr1        = int(item[1])
        wr2        = int(item[2])
        df.loc[i] = [k, jahr, monatabs, monat, hausgesamt, wr1,wr2]
        datafile.write(f'{k}\t{jahr}\t{monatabs}\t{monat}\t{hausgesamt}\t{wr1}\t{wr2}\n')
        i+=1
        #if i==100: break

    datafile.close()
    df['HausGesamt'] = df['HausGesamt'].astype(float)  
    df['haus_sum_monatabs']      = df.groupby('Monatabs')['HausGesamt'].transform('sum')
    df['haus_sum_monat']         = df.groupby('Monat')['HausGesamt'].transform('sum')
       
    anz_jahre = df['Jahr'].nunique()-1
    print ("AnzahlJahre", anz_jahre)
    
    
    df_avg = df.loc[df.groupby("Monat")["haus_sum_monatabs"].idxmax()]
    df_avg['haus_avg_monat']     = df_avg['haus_sum_monat']/anz_jahre

    print (df.tail(12))
    print (df_avg)

    # ax = plt.subplot(111)
    # f = plt.figure(figsize = (20, 8))
    # plt.style.use('seaborn-basdfright')
    # #move_figure(f, 540, 0)
    # plt.bar(df['Monatabs'], df['HausGesamt'], align='center', label='')
    # #plt.bar(df_avg['Monatabs'], df['month_avg'], color='red')

    #df = df.tail(12)
    
    df = df[(df.Jahr == 2020)]
    print (df)
    
    fig, ax = plt.subplots()
    ax.bar(df['Monat'], df['haus_sum_monatabs'], color='blue', label='Monatssumme')
    ax2 = ax.twinx()
    ax2.scatter(df_avg['Monat'], df_avg['haus_avg_monat'], color='green', label='Durchschnitt')
    ax2.grid(None)
    from matplotlib import rcParams
    rcParams.update({'figure.autolayout': True})
    ax2.set_yticks(np.linspace(ax2.get_yticks()[0],ax2.get_yticks()[-1],len(ax.get_yticks())))
    #ax.set_xticklabels(df_avg['Monat'])
    ax.legend(loc='best')


    plt.show()
  

def get_date():
    global path
    #read max date from shelve db
    pv_data = shelve.open(path)
    for k, item in sorted(pv_data.items(), key=lambda x: (datetime.datetime.strptime(x[0][:10], '%d.%m.%Y')), reverse=True):
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

    print (f'getting values for {start_date} - {end_date}')
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