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
import calendar

today = datetime.date.today()
today = today.strftime("%d.%m.%Y")
current_year = today[6:10]
plot_filename = f'pv{current_year}.png'

MAX_DAYS = 14
url = 'http://192.168.178.58/cgi-bin/download.csv/'
path = os.path.join(os.path.expanduser("~/photovoltaik/"), 'pv_daten') #path to db
WR1_TEXT = 'SG45T2.1.20'
WR2_TEXT = 'SGl10k.1.10'

def main():
    start_date, end_date = get_date()
    get_values_from_pv(start_date, end_date)
    make_graph()
    upload_plot()

def upload_plot():
    global plot_filename
    gs_folder = "darkshadow-share/"
    cmd1 = f'gsutil cp {plot_filename} gs://{gs_folder}'
    cmd2 = f'gsutil acl ch -u AllUsers:R gs://{gs_folder}{plot_filename}'
    os.system(cmd1)
    os.system(cmd2)

def make_graph():
    global path, WR1_TEXT, WR2_TEXT, current_year, plot_filename

    pv_data = shelve.open(path)
    filename = 'values.xlsx'
    datafile = open(filename, 'w')
    datafile.write('Datum\tJahr\tMonatabs\tMonat\tHausgesamt\tWR1\tWR2\n')
    
    df = pd.DataFrame(columns=('Datum', 'Jahr', 'Monatabs', 'Monat', 'HausGesamt', 'WR1', 'WR2'))
    #idx = pd.date_range('01-01-2011', '12-31-2020')
    i=0
    for k, item in sorted(pv_data.items(), key=lambda x: (datetime.datetime.strptime(x[0][:10], '%d.%m.%Y')), reverse=True):
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
    df['Datum']      = pd.to_datetime(df['Datum'])

    #print (df.tail(30))
    #df.index = pd.DatetimeIndex(df.Datum)
    
    #idx = pd.date_range('2011-01-01', '2020-31-12')
    #df.reindex(idx, fill_value=0)
    #print (df.head(60))
    #exit()
    df['haus_sum_monatabs']      = df.groupby('Monatabs')['HausGesamt'].transform('sum')
    df['haus_sum_monat']         = df.groupby('Monat')['HausGesamt'].transform('sum')
       
    anz_jahre = df['Jahr'].nunique()-1
    print ("AnzahlJahre", anz_jahre)
    
    
    df_avg = df.loc[df.groupby("Monat")["haus_sum_monatabs"].idxmax()]
    df_avg['haus_avg_monat']     = df_avg['haus_sum_monat']/anz_jahre
    df_avg['haus_max_monat']     = df_avg['haus_sum_monatabs']

    df1 = df[df['haus_sum_monatabs'] != 0]
    df_min = df1.loc[df1.groupby("Monat")["haus_sum_monatabs"].idxmin()]
    df_min['haus_min_monat']     = df_min['haus_sum_monatabs']
    
   
    df = df[(df.Jahr == int(current_year))]
    max_value = df['haus_sum_monatabs'].max()
    
    #r = pd.date_range(start=df.Datum.min(), end='2020-12-31')
    #df.set_index('Datum').reindex(r).fillna(0.0).rename_axis('Datum').reset_index()

    print ("Max_value", max_value)
    print (df)
    print (df_avg)

    plt.style.use('bmh') 
    fig, ax = plt.subplots()
    #fig.figure(figsize=(20,10)) 
    
    ax.set_title('PV Anlage - Ertrag in kWh', fontdict={'fontsize': 14, 'fontweight': 'medium'})

    ax.plot(df_avg['Monat'], df_avg['haus_avg_monat'], label='Durchschnittswerte', zorder=2)
    ax.scatter(df_avg['Monat'], df_avg['haus_max_monat'], label='Max Werte', s=100, zorder = 3)
    ax.scatter(df_min['Monat'], df_min['haus_min_monat'], label='Min Werte', s=50, zorder = 3)
    ax2 = ax.twinx()
    ax2.bar(df['Monat'], df['haus_sum_monatabs'],label='Monatssumme', zorder=1)
    ax.set_xticks([1,2,3,4,5,6,7,8,9,10,11,12])
    ax.set_xticklabels(['Jan', 'Feb', 'Mar','Apr','Mai','Jun','Jul','Aug','Sep','Okt','Nov','Dez'])
    ax.set_ylim(0, max_value + 500)
    ax2.set_ylim(0, max_value + 500)
    ax.set_xlabel('Monat')
    ax.set_ylabel('kWh')
    ax.set_zorder(ax2.get_zorder()+1)
    ax.patch.set_visible(False)
    ax2.grid(True)
    plt.rcParams['font.size'] = 20
    #plt.rcParams['legend.fontsize'] = 12
    
    #ax.legend(loc='best')

    #plt.show()
    
    fig.savefig(f'{plot_filename}', dpi = (600))
  

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