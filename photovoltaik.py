#!/usr/bin/python

import requests
import sys, os
import shelve
import datetime
import matplotlib.pyplot as plt
import matplotlib.ticker as plticker
import pandas as pd
import numpy as np
import calendar
from b2blaze import B2
import time
import smtplib, ssl
from email.mime.text import MIMEText
#set environment variables B2_KEY_ID and B2_APPLICATION_KEY

global bucketname
bucketname = 'photovoltaik'


today     = datetime.date.today()
today     = today.strftime("%d.%m.%Y")
yesterday = datetime.date.today() - datetime.timedelta(days=1)
yesterday = yesterday.strftime("%d.%m.%Y")
day7 = datetime.date.today() - datetime.timedelta(days=7)
day7 = day7.strftime("%Y-%m-%d")

current_year = today[6:10]

#historische Datenaufbereitung
years=[]
if len(sys.argv) > 1:
    if sys.argv[1] == 'history':
        history_flag = 1
        for year in range(int(current_year), 2010, -1):
            years.append(year)
else:
    years.append(int(current_year))
    history_flag = 0

#years = [2020,2019]

gs_folder = "solar-anlage-gm/"

if sys.platform.startswith('win'):
    dir = 'C:/PV/photovoltaik'
else:
    dir = '/home/mike/photovoltaik/data'

myhost = os.uname()[1]
print (myhost)
vpn_flag = 1 if myhost.startswith('rasp') else 0
    
global last_values_pv
last_values_pv = {}

anlagen = {
            'mike ' : { 'url'              : 'http://192.168.178.58/cgi-bin/download.csv/',
                        'plotname'         : 'mike_pv_'  ,
                        'db'               : 'mike_raw_data.db'  ,
                        'colors'           : {
                                                'background-color': '#121212', 
                                                'bar-color'       : 'azure',
                                                'text-color'      : 'ivory'
                                             },
                        'warning'           : 50
            }
            ,
            'halle' : { 'url'              : 'http://192.168.178.57/cgi-bin/download.csv/',
                        'plotname'         : 'halle_pv_'  ,
                        'db'               : 'halle_raw_data.db'  ,
                        'colors'           : {
                                                'background-color': '#121212', 
                                                'bar-color'       : 'aqua',
                                                'text-color'      : 'ivory'
                                             },
                        'warning'           : 100
            }
}



MAX_DAYS = 3500

def main(years):
    if vpn_flag == 1: vpn('on')
    # fuer jede Anlage einen Durchlauf
    for key, value in anlagen.items():
        start_workflow(key, value, years)
    send_email()
    if vpn_flag == 1: vpn('off')

def vpn(switch):
    if switch == 'on':
        os.system('sudo vpnc /etc/vpnc/default.conf')      #VPN connect
    elif switch == 'off':
        os.system('sudo vpnc-disconnect')    #VPN disconnect

def start_workflow(key, value, years):
    
    print (f'Erstelle Auswertung fuer {key} - Jahr: {years}')
    for year in years:
        url             = value['url']
        plot_filename   = value['plotname'] + str(year) + '.png'
        db              = value['db']
        colors          = value['colors']
        warning         = value['warning']
        path            = os.path.join(os.path.expanduser(dir), db)     

        if int(year) == int(current_year):
            start_date, end_date = get_date(url, path)
            get_values_from_pv(start_date, end_date, url, path, key)
            return

        make_graph(year, path, plot_filename, colors, warning)
    
        upload_plot(plot_filename)     

    upload_plot(plotlast7days)
    
    if history_flag == 1:
        html(value['plotname'], years)
        upload_html(html_out_filename)

def get_date(url, path):
    #read max date from shelve db
    try:
        pv_data = shelve.open(path)
    except:
        pass

    try:
        for k, item in sorted(pv_data.items(), key=lambda x: (datetime.datetime.strptime(x[0][:10], '%d.%m.%Y')), reverse=True):
            last_date = k[0:10]
            break
        print (f'last date value already in database - {last_date}')
        start_date = datetime.datetime.strptime(last_date, '%d.%m.%Y') + datetime.timedelta(days=1)
        start_date = str(start_date.strftime("%d.%m.%Y"))[0:10]
        if start_date > yesterday: start_date = yesterday
        end_date = yesterday
    except:
        print (f'database has no values yet')
        start_date = datetime.datetime.strptime(yesterday, '%d.%m.%Y') - datetime.timedelta(days=MAX_DAYS)
        start_date = str(start_date.strftime("%d.%m.%Y"))[0:10]
        end_date = yesterday

    print (f'getting values for {start_date} - {end_date}')
    return start_date, end_date

def make_graph(year, path, plot_filename, colors, warning):
    global plotlast7days
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
    
    df_last7days = df.head(7)
    df_last7days['Datum'] = pd.to_datetime(df_last7days['Datum'], dayfirst=True)
    df_last7days.sort_values(by=['Datum'], inplace=True)
    kum_value_7days = df_last7days['HausGesamt'].sum().astype(int) 
    max_value_7days = df_last7days['HausGesamt'].max()

    if kum_value_7days < warning:
        color_7day = 'red'
    elif warning < kum_value_7days < 400:
        color_7day = 'orange'
    else:
        color_7day = 'green'

    fig, ax1 = plt.subplots(figsize=(20, 3.5), facecolor=colors['background-color'])
    name = plot_filename.split('_')
    ax1.set_title(f'PV Anlage {name[0].upper()}- Ertrag in kWh der letzten 7 Tage', fontdict={'fontsize': 28, 'fontweight': 'medium', 'color':colors['text-color']})

    ax1.set_facecolor(colors['background-color'])
    #ax1.plot(df_last7days.index, df_last7days['HausGesamt'], color=color_7day, marker="D", label='kWh', markersize = 12, linewidth=4.0, zorder=2)
    ax1.plot(df_last7days['Datum'], df_last7days['HausGesamt'], color=color_7day, marker="D", label='kWh', markersize = 12, linewidth=4.0, zorder=2)
    #ax1.set_xticks(df_last7days.index)
    ax1.set_xticks(df_last7days['Datum'])
    ax1.tick_params(labelcolor='tab:orange',labelsize='large', width=3)
    ax1.set_ylim(0, max_value_7days + 50)
    ax1.grid(True, linestyle='-.', color=colors['text-color']) 
    ax1.spines['bottom'].set_color(colors['text-color'])
    ax1.spines['bottom'].set_linestyle('-.')
    #for p in ax1.patches:
    #    ax1.annotate("%d" % p.get_height(), (p.get_x() + p.get_width() / 2., p.get_height()), ha='center', va='center', xytext=(0, 10), textcoords='offset points', color=colors['text-color'] ,fontsize=14)

    plt.text(1, 0.6, f'{kum_value_7days}\nErtrag kummuliert', ha='center', color='white', size=20, style='italic', transform=ax1.transAxes,
                bbox=dict(boxstyle="round, pad=1",
                          fc=color_7day,
                          ec='lightgrey',
                          alpha=0.5
                   )
    )

    #plt.show()    
    plotlast7days = plot_filename.split('_')[0]+'_last7days.png'
    fig.savefig(f'{plotlast7days}', dpi=400)

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
    
    df_avg = df.loc[df.groupby("Monatabs")["haus_sum_monatabs"].idxmax()]
    df_avg1 = df_avg[df_avg['haus_sum_monatabs'] != 0]
    df_avg2 = df_avg1[df_avg1['Jahr'] != int(current_year)]
    df_mean = df_avg2.groupby("Monat").agg({"haus_sum_monatabs" : np.mean}).reset_index()
    
    df_max = df.loc[df.groupby("Monat")["haus_sum_monatabs"].idxmax()]
    df_max['haus_max_monat']     = df_avg['haus_sum_monatabs']

    df0 = df[df['haus_sum_monatabs'] != 0]
    df1 = df0[df0['Jahr'] != int(current_year)]
    df_min = df1.loc[df1.groupby("Monat")["haus_sum_monatabs"].idxmin()]
    df_min['haus_min_monat']     = df_min['haus_sum_monatabs']
    
   
    df = df[(df.Jahr == int(year))]
    max_value = df_max['haus_sum_monatabs'].max()
    kum_value = df['HausGesamt'].sum().astype(int) 
    #print (df_max)
    #print (df_mean)
    #print (df_min)

    fig, ax = plt.subplots(figsize=(20, 10), facecolor=colors['background-color'])
    ax.set_facecolor(colors['background-color'])
    
    name = plot_filename.split('_')
    ax.set_title(f'PV Anlage {name[0].upper()}- Ertrag in kWh für das Jahr {year}', fontdict={'fontsize': 28, 'fontweight': 'medium', 'color':colors['text-color']})

    ax.plot(df_mean['Monat'], df_mean['haus_sum_monatabs'], '_', mew=3, ms=68, color='orange', label='Durchschnittswerte', zorder=2)
    ax.plot(df_max['Monat'], df_max['haus_max_monat'],      '_', mew=3, ms=68, color='green', label='Max Werte', zorder = 3)
    ax.plot(df_min['Monat'], df_min['haus_min_monat'],      '_', mew=3, ms=68, color='red' ,   label='Min Werte', zorder = 3)
    ax2 = ax.twinx()
    ax2.bar(df['Monat'], df['haus_sum_monatabs'],label='Monatssumme', color=f'xkcd:{colors["bar-color"]}', zorder=1)
    ax.set_xticks([1,2,3,4,5,6,7,8,9,10,11,12])
    ax.set_xticklabels(['Jan', 'Feb', 'Mar','Apr','Mai','Jun','Jul','Aug','Sep','Okt','Nov','Dez'])
    #ax.set_yticklabels(rotation=0, fontsize=18)
    
    ax.set_ylim(0, max_value + 500)
    ax2.set_ylim(0, max_value + 500)

    ax.set_ylabel('kWh', color=colors['text-color'], fontsize=24)
    ax.tick_params(labelcolor='tab:orange',labelsize='large', width=3)
    ax2.tick_params(labelcolor=colors['background-color'])
    ax.spines['bottom'].set_color(colors['text-color'])
    ax.spines['top'].set_color(colors['text-color'])
    ax.spines['left'].set_color(colors['text-color'])
    ax.spines['right'].set_color(colors['text-color'])
    ax.set_zorder(ax2.get_zorder()+1)
    ax.patch.set_visible(False)
    ax.legend(loc="upper left",markerscale=0.2)
    ax.grid(True, linestyle='-.', color=colors['text-color'])   
    ax.xaxis.grid(False)

    for p in ax2.patches:
        ax.annotate("%d" % p.get_height(), (p.get_x() + p.get_width() / 2., p.get_height()), ha='center', va='center', xytext=(0, 10), textcoords='offset points', color=colors['text-color'] ,fontsize=14)

    ypos = max_value * 0.7
    ax.text(10.5, ypos, f'{kum_value}\nJahresertrag kummuliert', ha='center', color='white', size=20, rotation=-25., style='italic',
                bbox=dict(boxstyle="round, pad=1",
                          fc='fuchsia',
                          ec='lightgrey',
                          alpha=0.5
                   )
    )

    #plt.show()
    
    fig.savefig(f'{plot_filename}', dpi=400)
    #savefig(f'{plot_filename}', facecolor=fig.get_facecolor(), transparent=True)
  
def get_values_from_pv(start_date, end_date, url, path, key):
    global last_values_pv
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
        #print ("line_item", line_item)
        if 4 <= len(line_item) <=6 :
            datum      = line_item[0]
            wr_gesamt  = line_item[1]
            wr1        = line_item[2]
            wr2        = line_item[3]
            try:
                wr3    = line_item[4]
                wr4    = line_item[5]
                value_dict = { datum: [wr_gesamt, wr1, wr2, wr3, wr4] }
            except:
                value_dict = { datum: [wr_gesamt, wr1, wr2] }

            #value_dict = { datum: [wr_gesamt, wr1, wr2] }
            values.update(value_dict)
    
    #writing data to database
    with shelve.open(path) as db:
        for k, v in values.items():
            db[k]= v
            print (f'Datum {k} - Werte {v}')
    
    pv_data = shelve.open(path)
    for k, item in sorted(pv_data.items(), key=lambda x: (datetime.datetime.strptime(x[0][:10], '%d.%m.%Y')), reverse=True):
        hausgesamt = int(item[0]) 
        wr1        = int(item[1]) 
        wr2        = int(item[2]) 
        try:
            wr3    = int(item[3]) 
            wr4    = int(item[4])
            last_values_pv[key] = [k, hausgesamt, wr1, wr2, wr3, wr4]
        except:
            last_values_pv[key] = [k, hausgesamt, wr1, wr2]
        
        break      


def upload_plot(plot_filename):
    global gs_folder
    cmd1 = f'gsutil -h "Cache-Control:no-cache,max-age=0" cp -a public-read {plot_filename} gs://{gs_folder}'
    cmd2 = f'gsutil acl ch -u AllUsers:R gs://{gs_folder}{plot_filename}'
    os.system(cmd1)
    os.system(cmd2)

def upload_html(html_out_filename):
    global gs_folder
    cmd1 = f'gsutil -h "Cache-Control:no-cache,max-age=0" cp -a public-read html_output/{html_out_filename} gs://{gs_folder}'
    cmd2 = f'gsutil acl ch -u AllUsers:R gs://{gs_folder}{html_out_filename}'
    os.system(cmd1)
    os.system(cmd2)


def upload_plot(plot_filename):
    b2 = B2()
    bucket = b2.buckets.get(bucketname)
    plot_file = open(plot_filename, 'rb')
    bucket.files.upload(contents=plot_file, file_name=plot_filename)

def upload_html_b2(html_out_filename):    
    b2 = B2()
    bucket = b2.buckets.get(bucketname)

    html_file = open(html_out_filename, 'rb')
    bucket.files.upload(contents=html_file, file_name=html_out_filename)
    

def html(plotname, years):
    jahre = years[:]
    print ('jahre', jahre)
    add_line=[]
    i = 1
    html_template = os.path.join(os.path.expanduser(dir+"/html_template"), 'photovoltaik_html_template.html')
    html_template_file = open(html_template, 'r')
    html_code = html_template_file.readlines()

    global html_out_filename, html_filename
    html_out_filename = f'{plotname[:-1]}.html'
    html_filename = os.path.join(os.path.expanduser(dir+"/html_output"), html_out_filename)
    htmlfile = open (html_filename, 'w')

    for item in html_code:
        if item.find('##TABLEHEADER##') > 0:
            item = f'<td colspan = 5><img src="https://f003.backblazeb2.com/file/{bucketname}/{plotlast7days}" class="plot"></td>\n'
            
        if item.find('##PV_DATA##') > 0:
            while jahre:
                year = jahre.pop(0)
                print (year)
                item = f'<tr><td colspan = 5><img src="https://f003.backblazeb2.com/file/{bucketname}/{plotname}{year}.png" class="plot"></td></tr>\n'
                if len(jahre)>0: 
                    print ("html link", item)
                    htmlfile.write(item)
                else:
                    pass
        htmlfile.write(item)
    htmlfile.close()



def send_email():
    email_from = os.environ.get('EMAIL_FROM')
    email_to = os.environ.get('EMAIL_TO')
    email_pw = os.environ.get('EMAIL_PW')
    port = 587  # For starttls
    smtp_server = "smtp.gmail.com"

    print (last_values_pv)

    for k, v in last_values_pv.items():
        print ("key: ", k, "value:", v)
        if k.startswith('mike'):
            link = "https://f003.backblazeb2.com/file/photovoltaik/mike_pv.html"
            msg = MIMEText(f"""
die PV Anlage {k.upper()} hat für den {v[0][:10]} folgenden Ertrag geliefert:\n
Gesamt: {v[1]}

Wechselrichter 1: {v[2]}
Wechselrichter 2: {v[3]}

Link: {link}
""")
        else:
            link = "https://f003.backblazeb2.com/file/photovoltaik/halle_pv.html"
            msg = MIMEText(f"""
die PV Anlage {k.upper()} hat für den {v[0][:10]} folgenden Ertrag geliefert:\n
Gesamt: {v[1]}

Wechselrichter 1: {v[2]}
Wechselrichter 2: {v[3]}
Wechselrichter 3: {v[4]}
Wechselrichter 4: {v[5]}

Link: {link}
""")
        msg['Subject'] = f"Photovoltaik Anlage {k.upper()} - Datum: {v[0][:10]}"
        msg['From'] = email_from
        msg['To'] = email_to


        context = ssl.create_default_context()
        with smtplib.SMTP(smtp_server, port) as server:
            server.starttls(context=context)
            server.login(email_from, email_pw)
            server.sendmail(email_from, email_to.split(','), msg.as_string())




main(years)



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