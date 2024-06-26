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
import time
import smtplib, ssl
from email.mime.text import MIMEText
from telegram.ext import Updater
import socket
import b2sdk.v2 as b2
from dotenv import load_dotenv
from dataclasses import dataclass
#set environment variables B2_KEY_ID and B2_APPLICATION_KEY

try:
    import tomllib
except ModuleNotFoundError:
    import tomli as tomllib

with open("/home/mike/gh_projects/photovoltaik/config.toml", mode="rb") as fp:
    toml_config = tomllib.load(fp)

load_dotenv()

global bucketname
bucketname = 'photovoltaik'
hostname = socket.gethostname()

today     = datetime.date.today()
today     = today.strftime("%d.%m.%Y")
yesterday = datetime.date.today() - datetime.timedelta(days=1)
yesterday_diff_fmt = yesterday.strftime("%Y-%m-%d")
yesterday = yesterday.strftime("%d.%m.%Y")

day7 = datetime.date.today() - datetime.timedelta(days=7)
day7 = day7.strftime("%Y-%m-%d")
weekday = int(datetime.datetime.today().strftime('%w'))+1

current_year = today[6:10]
jan_01_current_year = current_year + '-01-01'

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

myhost = os.uname()[1]
print (myhost)
#vpn_flag = 1 if myhost.startswith('rasp') else 0
vpn_flag = 1

global last_values_pv
last_values_pv = {}
max_value_this_year_dict = {}

@dataclass
class PVAnlage():
    name: str

    def __post_init__(self):
        self.url = toml_config[self.name.upper()]["URL"]
        self.plotname = toml_config[self.name.upper()]["PLOTNAME"]
        self.db = toml_config[self.name.upper()]["DB"]
        self.warning = toml_config[self.name.upper()]["WARNING"]
        self.path_data = toml_config[self.name.upper()]["PATH_DATA"]
        self.path_png = toml_config[self.name.upper()]["PATH_PNG"]
        self.limit_wechselrichter = toml_config[self.name.upper()]["LIMIT_WECHSELRICHTER"]
        self.backgroundcolor = toml_config[self.name.upper()]["COLORS"]["BACKGROUND-COLOR"]
        self.barcolor = toml_config[self.name.upper()]["COLORS"]["BAR-COLOR"]
        self.textcolor = toml_config[self.name.upper()]["COLORS"]["TEXT-COLOR"]

mike = PVAnlage("mike")
halle = PVAnlage("halle")

anlagen = []
anlagen.append(mike)
#anlagen.append(halle)

MAX_DAYS = 10000

def main(years):
    if vpn_flag == 1: vpn('on')
    
    # fuer jede Anlage einen Durchlauf
    for item in anlagen:
        start_workflow(anlage=item, years=years)
    #send_email()
    if vpn_flag == 1: vpn('off')
    
def start_workflow(anlage="", years=""):
    
    print (f'Erstelle Auswertung fuer {anlage} - Jahr: {years}')
    for year in years:
        url             = anlage.url
        plot_filename   = anlage.plotname + str(year) + '.png'
        db              = anlage.db
        colors          = {
                            "background-color" : anlage.backgroundcolor,
                            "bar-color": anlage.barcolor,
                            "text-color": anlage.textcolor
                          }

        warning         = int(anlage.warning)
        path_data       = anlage.path_data
        path_png        = anlage.path_png
        path_db         = os.path.join(os.path.expanduser(path_data)+"db/", db)    

        if int(year) == int(current_year):
           start_date, end_date, last_date = get_date(url=url, path=path_db)
           get_values_from_pv(start_date=start_date, end_date=end_date, last_date=last_date, url=url, path=path_db, name=anlage.name)

        make_graph(path_db=path_db, path_png=path_png, year=year, plot_filename=plot_filename, colors=colors, warning=warning)

        if 'Pi' in hostname:
            upload(filename=plot_filename, path=path_png)  
         

    if 'Pi' in hostname:
        #upload only on raspberry
        upload(filename=plotlast7days, path=path_png)
        upload(filename=plotwr, path=path_png)
        
        if history_flag == 1:
            html(plotname=plot_filename, years=years, path=path_data)
            upload(filename=html_out_filename, path=path_data)    

def get_date(url="", path=""):
    last_date = ''
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

    #dirty workaround ;) 
    if '01.01.' in start_date:
        start_date = yesterday

    print (f'getting values for {start_date} - {end_date}')
    return start_date, end_date, last_date

def make_graph(path_db="", path_png="", year="", plot_filename="", colors="", warning=""):
    global plotlast7days, plotwr, max_value_this_year_dict
    
    name = plot_filename.split('_')

    pv_data = shelve.open(path_db)
    #filename = 'values.xlsx'
    #datafile = open(filename, 'w')
    #datafile.write('Datum\tJahr\tMonatabs\tMonat\tHausgesamt\tWR1\tWR2\tWR3\tWR4\n')
    
    df = pd.DataFrame(columns=('Datum', 'Jahr', 'Monatabs', 'Monat', 'Tag', 'HausGesamt', 'WR1', 'WR2', 'WR3', 'WR4'))
    #idx = pd.date_range('01-01-2011', '12-31-2020')
    i=0
    for k, item in sorted(pv_data.items(), key=lambda x: (datetime.datetime.strptime(x[0][:10], '%d.%m.%Y')), reverse=True):
        jahr       = int(k[6:10])
        monatabs   = str(k[6:10]+k[3:5])
        monat      = int(k[3:5])
        tag        = str(jahr) + '-' + k[3:5] + '-' + k[0:2]
        #hausgesamt = float(int(item[0])/int(1000))
        hausgesamt = int(item[0]) / 1000
        #hausgesamt_anz= str(hausgesamt).replace('.','')
        wr1        = int(item[1])
        wr2        = int(item[2])
        try:
            wr3    = int(item[3])
            wr4    = int(item[4])
        except:
            wr3 = -1
            wr4 = -1
        df.loc[i] = [k, jahr, monatabs, monat, tag, hausgesamt, wr1,wr2,wr3,wr4]
        #datafile.write(f'{k}\t{jahr}\t{monatabs}\t{monat}\t{tag}\t{hausgesamt}\t{wr1}\t{wr2}\n')
        i+=1
        #if i==100: break
    
    #### last 7 days #####
    mask = (df['Tag'] >= jan_01_current_year) & (df['Tag'] <= yesterday_diff_fmt)
    max_value_thisyear = df[df['HausGesamt']==df.loc[mask]['HausGesamt'].max()]
    max_val_day = max_value_thisyear['Tag'].iloc[0]
    max_val_val = max_value_thisyear['HausGesamt'].iloc[0]
    max_value_this_year_dict[name[0]] = [max_val_day, max_val_val]

    df_last7days = df.head(7)
    df_last7days = df_last7days.copy()
    df_last7days['Datum'] = pd.to_datetime(df_last7days['Datum'], dayfirst=True)
    kum_value_7days = df_last7days['HausGesamt'].sum().astype(int) 
    max_value_7days = df_last7days['HausGesamt'].max()

    if kum_value_7days < warning:
        color_7day = 'red'
    elif warning < kum_value_7days < 400:
        color_7day = 'orange'
    else:
        color_7day = 'green'

    print ("background: ", colors['background-color'])
    fig, ax1 = plt.subplots(figsize=(20, 3.5), facecolor=colors['background-color'])
    
    ax1.set_title(f'PV Anlage {name[0].upper()}- Ertrag in kWh der letzten 7 Tage', fontdict={'fontsize': 40, 'fontweight': 'bold', 'color':colors['text-color']})

    ax1.set_facecolor(colors['background-color'])
    #ax1.plot(df_last7days.index, df_last7days['HausGesamt'], color=color_7day, marker="D", label='kWh', markersize = 12, linewidth=4.0, zorder=2)
    ax1.plot(df_last7days['Datum'], df_last7days['HausGesamt'], color=color_7day, marker="D", label='kWh', markersize = 12, linewidth=4.0, zorder=2)
    #ax1.set_xticks(df_last7days.index)
    ax1.set_xticks(df_last7days['Datum'])
    ax1.tick_params(labelcolor='white',labelsize=22, width=3, labelright='true')
    ax1.set_ylim(0, max_value_7days + 50)
    ax1.grid(True, linestyle='-.', color=colors['text-color']) 
    ax1.spines['bottom'].set_color(colors['text-color'])
    ax1.spines['bottom'].set_linestyle('-.')
    #for p in ax1.patches:
    #    ax1.annotate("%d" % p.get_height(), (p.get_x() + p.get_width() / 2., p.get_height()), ha='center', va='center', xytext=(0, 10), textcoords='offset points', color=colors['text-color'] ,fontsize=14)

    plt.text(1, 0.9, f'{kum_value_7days}\nErtrag kummuliert', ha='center', color='white', size=20, style='italic', transform=ax1.transAxes,
                bbox=dict(boxstyle="round, pad=1",
                          fc=color_7day,
                          ec='lightgrey',
                          alpha=0.5
                   )
    )

    for i in range(len(df_last7days)):
        #print (df_last7days['Datum'][i], df_last7days['HausGesamt'][i])
        plt.text( df_last7days['Datum'][i], df_last7days['HausGesamt'][i]+7, str(int(df_last7days['HausGesamt'][i])), color='white', weight='bold', size=32)
    
    #plt.show()    
    plotlast7days = plot_filename.split('_')[0]+'_last7days.png'
    fig.tight_layout()
    fig.savefig(f'{path_png}{plotlast7days}', dpi=400, facecolor=colors['background-color'])

    #### END END END last 7 days END END END #####


    #### Wechselrichter #####
    color_wr = ["#006D2C", "#31A354","#74C476", "#a5f2a7"]
    text_color_wr = 'silver'

    df_wr = df.head(7)
    df_wr = df_wr.copy()
    df_wr['Datum'] = pd.to_datetime(df_wr['Datum'], dayfirst=True)
    df_wr.sort_values(by=['Datum'], inplace=True)

    print (df_wr)

    fig1, ax3 = plt.subplots(figsize=(20, 3.5), facecolor=colors['background-color'])
    
    #ax3.set_title(f'PV Anlage {name[0].upper()}- Ertrag pro WR der letzten 7 Tage', fontdict={'fontsize': 40, 'fontweight': 'bold', 'color':colors['text-color']})

    ax3.set_facecolor(colors['background-color'])

    ##stacked bar chart
    #ax3.bar(df_wr['Datum'], df_wr['WR1'], color=color_wr[0], label='kWh', linewidth=4.0, zorder=2)
    #ax3.bar(df_wr['Datum'], df_wr['WR2'], bottom=df_wr['WR1'], color=color_wr[1], label='kWh', linewidth=4.0, zorder=3)
    # try:
    #     ax3.bar(df_wr['Datum'], df_wr['WR3'], bottom=(df_wr['WR1'] +df_wr['WR2']), color=color_wr[2], label='kWh', linewidth=4.0, zorder=4)
    #     ax3.bar(df_wr['Datum'], df_wr['WR4'], bottom=(df_wr['WR1'] +df_wr['WR2']+ df_wr['WR3']), color=color_wr[3], label='kWh', linewidth=4.0, zorder=5)
    # except:
    #     pass

    ## multiple bar chart 
    X_axis = np.arange(len(df_wr['Datum']))
    if df_wr.iloc[0].iloc[8] == -1:  # dann WR3 nicht vorhanden
        ax3.bar(X_axis-0.2, df_wr['WR1'],width=0.4, color=color_wr[0], label='kWh')
        ax3.bar(X_axis+0.2, df_wr['WR2'],width=0.4, color=color_wr[1], label='kWh') 
    else:
        ax3.bar(X_axis-0.3, df_wr['WR1'],width=0.2, color=color_wr[0], label='kWh', linewidth=4.0)
        ax3.bar(X_axis-0.1, df_wr['WR2'],width=0.2, color=color_wr[1], label='kWh', linewidth=4.0)
        ax3.bar(X_axis+0.1, df_wr['WR3'],width=0.2, color=color_wr[2], label='kWh', linewidth=4.0)
        ax3.bar(X_axis+0.3, df_wr['WR4'],width=0.2, color=color_wr[3], label='kWh', linewidth=4.0)

    #ax3.set_xticks(df_wr['Datum'])
    #plt.xticks(X_axis, df_wr['Datum'])
    #ax3.tick_params(labelcolor=text_color_wr,labelsize=22, width=3, labelright='true')
    #ax3.set_ylim(0, max_value_7days + 50)

    # ax3.tick_params(
    #     axis='y',          # changes apply to the x-axis
    #     which='both',      # both major and minor ticks are affected
    #     bottom=True,      # ticks along the bottom edge are off
    #     top=True,         # ticks along the top edge are off
    #     labelbottom=True,
    #     labelsize=22,
    #     labelcolor='white'
    # ) 

    ax3.grid(True, linestyle='-.', color=text_color_wr) 
    ax3.spines['bottom'].set_color(text_color_wr)
    ax3.spines['bottom'].set_linestyle('-.')
    #plt.show() 
    plotwr = plot_filename.split('_')[0]+'_wr.png'
    fig1.tight_layout()
    fig1.savefig(f'{path_png}{plotwr}', dpi=400, facecolor=colors['background-color'])

    #### END END END Wechselrichter END END END #####

    df['HausGesamt'] = df['HausGesamt'].astype(float)  
    #df['Datum']      = pd.to_datetime(df['Datum'])
    df['Datum'] = pd.to_datetime(df['Datum'], format="%d.%m.%Y %H:%M:%S")

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
    df_mean = df_avg2.groupby("Monat").agg({"haus_sum_monatabs" : "mean"}).reset_index()

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
    ax.set_title(f'PV Anlage {name[0].upper()}- Ertrag in kWh für das Jahr {year}', fontdict={'fontsize': 40, 'fontweight': 'bold', 'color':colors['text-color']})

    ax.plot(df_mean['Monat'], df_mean['haus_sum_monatabs'], '_', mew=3, ms=85, color='orange', label='Durchschnittswerte', zorder=2)
    ax.plot(df_max['Monat'], df_max['haus_max_monat'],      '_', mew=3, ms=85, color='green', label='Max Werte', zorder = 3)
    ax.plot(df_min['Monat'], df_min['haus_min_monat'],      '_', mew=3, ms=85, color='red' ,   label='Min Werte', zorder = 3)
    ax2 = ax.twinx()
    ax2.bar(df['Monat'], df['haus_sum_monatabs'],label='Monatssumme', color=f'xkcd:{colors["bar-color"]}', zorder=1)
    ax.set_xticks([1,2,3,4,5,6,7,8,9,10,11,12])
    ax.set_xticklabels(['Jan', 'Feb', 'Mar','Apr','Mai','Jun','Jul','Aug','Sep','Okt','Nov','Dez'])
    #ax.set_yticklabels(rotation=0, fontsize=18)
    
    ax.set_ylim(0, max_value + 500)
    ax2.set_ylim(0, max_value + 500)

    ax.set_ylabel('kWh', color=colors['text-color'], fontsize=24)
    ax.tick_params(labelcolor='white',labelsize=30, width=3)
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
        ax.annotate("%d" % p.get_height(), (p.get_x() + p.get_width() / 2., p.get_height()), ha='center', va='center', xytext=(0, 20), textcoords='offset points', color=colors['text-color'] ,fontsize=32, style='oblique')

    ypos = max_value * 0.7
    ax.text(10.5, ypos, f'{kum_value}\nJahresertrag kummuliert', ha='center', color='white', size=32, rotation=-25., style='italic',
                bbox=dict(boxstyle="round, pad=1",
                          fc='fuchsia',
                          ec='lightgrey',
                          alpha=0.5
                   )
    )

    #plt.show()
    fig.tight_layout()
    fig.savefig(f'{path_png}{plot_filename}', dpi=400, facecolor=colors['background-color'])
    

def get_values_from_pv(start_date="", end_date="", last_date="", url="", path="", name=""):
    global last_values_pv
    headers={}

    if last_date == yesterday:
        return

    data = {
    'aggregate': 'day',
    'start_day': start_date,
    'start_time': '00:00',
    'end_day': end_date,
    'end_time': '00:00'
    }

    #try it 10 times
    for i in range(1,25):
        try: 
            print (f'try - {i} ...') 
            response = requests.post(url,headers=headers, data=data, allow_redirects=False,verify=False, timeout=300)
            print (response.text)
            if 'Yield' in response.text:
                break
            else:
                print ("sleep 20 sec")
                time.sleep(20)
        except Exception as e:
            print ("sleep 20 sec", e)
            time.sleep(20)
            next

    for k, v in response.__dict__.items():
        if k == '_content':
            line = v.decode("utf-8")

    data = line.split('\n')   
    kwh_data = data[5:]

    values = {}
    for item in kwh_data:
        line_item = item.split(';')
        print ("line_item", line_item)
        if len(line_item) == 1:
            break
        datum      = line_item[0]
        wr_gesamt  = line_item[1]
        if len(line_item) == 5: #falls anlage mike, alles WR um 1 verschoben
            wr1        = line_item[3] 
            wr2        = line_item[4]
        else:
            wr1        = line_item[2] 
            wr2        = line_item[3]
        try:
            wr3    = line_item[4]
            wr4    = line_item[5]
            value_dict = { datum: [wr_gesamt, wr1, wr2, wr3, wr4] }
        except:
            value_dict = { datum: [wr_gesamt, wr1, wr2] }

        #value_dict = { datum: [wr_gesamt, wr1, wr2] }
        print ("value_dict: ", value_dict)
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
            last_values_pv[name] = [k, hausgesamt, wr1, wr2, wr3, wr4]
        except:
            last_values_pv[name] = [k, hausgesamt, wr1, wr2]
        
        break      

def upload(filename='', path=""):
        
    info = b2.InMemoryAccountInfo()
    b2_api = b2.B2Api(info)

    application_key_id = os.getenv("B2_KEY_ID")
    application_key = os.getenv("B2_APPLICATION_KEY")

    b2_api.authorize_account("production", application_key_id, application_key)
    bucket = b2_api.get_bucket_by_name("photovoltaik")
    
    from pathlib import Path
    if 'html' in filename:
        local_file = Path(path + "html_output/"+filename).resolve()
    else:
        local_file = Path(path + filename).resolve()
    metadata = {"key": "value"}

    uploaded_file = bucket.upload_local_file(
    local_file=local_file,
    file_name=filename,
    file_infos=metadata,
    )
    print(b2_api.get_download_url_for_fileid(uploaded_file.id_))


def html(plotname="", years="", path=""):
    jahre = years[:]
    print ('jahre', jahre)
    add_line=[]
    i = 1
    html_template = os.path.join(os.path.expanduser(path+"/html_template"), 'photovoltaik_html_template.html')
    html_template_file = open(html_template, 'r')
    html_code = html_template_file.readlines()

    global html_out_filename, html_filename
    html_out_filename = f'{plotname[:-1]}.html'
    html_filename = os.path.join(os.path.expanduser(path+"/html_output"), html_out_filename)
    htmlfile = open (html_filename, 'w')

    for item in html_code:
        if item.find('##TABLEHEADER##') > 0:
            item = f'<td colspan = 5><img src="https://f003.backblazeb2.com/file/{bucketname}/{plotlast7days}" class="plot"></td>\n'
        if item.find('##WR_DATA##') > 0:
            item = f'<td colspan = 5><img src="https://f003.backblazeb2.com/file/{bucketname}/{plotwr}" class="plot"></td>\n'
            
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


def send_telegram(message):
    api_token = os.environ.get('TELEGRAM_API_TOKEN')
    chat_id   = os.environ.get('TELEGRAM_CHAT_ID')

    updater = Updater(api_token)
    updater.bot.sendMessage(chat_id=chat_id, text=message)

def init_body():
    return []

def send_email():
    print (max_value_this_year_dict)

    email_from = os.environ.get('EMAIL_FROM')
    email_to = os.environ.get('EMAIL_TO')
    email_pw = os.environ.get('EMAIL_PW')
    port = 587  # For starttls
    smtp_server = "smtp.gmail.com"
    pushover_notification, message_pushover, body_dict ={}, {}, {}
    
    print (last_values_pv)
    datum = last_values_pv['mike'][0][:10]
    betreff = [f'PV - Anlage: {datum} '] 
    body = init_body()

    for k, v in last_values_pv.items():
        betreff.append(f'## {k} - {v[1]} ')
        body.append(f'{k}\n')

        for i in range(len(v)):
            
            if i == 0: 
                pass
            elif i == 1:
                value = format(int(v[i]),',').replace(',','.')
                body.append(f'Gesamt: {value}')
            else:         
                value = format(int(v[i]),',').replace(',','.')
                body.append(f'Wechselrichter {i-1}: {value}')
                if int(v[i]) < anlagen[k]['limit_wechselrichter']:
                  pushover_notification[k] = 1
        
        try:
            if pushover_notification[k] == 1:
                message_pushover[k] = '\n'.join(body[:])
        except:
            pass
        
        body.append(f'Höchster Tagesertrag in diesem Jahr: {max_value_this_year_dict[k]}\n')
        link = f'\nhttps://f003.backblazeb2.com/file/photovoltaik/{k}_pv.html\n\n'
        body.append(link)

        body = '\n'.join(body)
        body_dict[k] = body[:]
        body = init_body()

    betreff = ''.join(betreff)
    

    #### send push notification if value is below limimt
    for k, v in message_pushover.items():
        title = f'Photovoltaik Minderertrag - Anlage: '        
        message = v
        #send_pushover(title, message)
        send_telegram(message=title+message)

    #### send email if it's saturday
    if weekday == 1: 
        body = init_body()
        body.append('Folgende Erträge wurden generiert:\n')
        for k, v in body_dict.items():
            body.append(v)
        body = ''.join(body)
        print (body)
    
        msg=MIMEText(f'{body}')
        msg['Subject'] = betreff
        msg['From'] = email_from
        msg['To'] = email_to

        context = ssl.create_default_context()
        with smtplib.SMTP(smtp_server, port) as server:
            server.starttls(context=context)
            server.login(email_from, email_pw)
            server.sendmail(email_from, email_to.split(','), msg.as_string())


def vpn(switch):
    if switch == 'on':
        os.system('sudo vpnc-disconnect')    #VPN disconnect
        #try it 10 times
        for i in range(1,20):
            try: 
                print (f'try - {i} ...') 
                rc = os.system('sudo vpnc /etc/vpnc/default.conf')      #VPN connect 
                if rc == 0:
                    break           
            except Exception as e:
                print ("sleep 120 sec", e)
                time.sleep(120)
                next
    
    elif switch == 'off':
        os.system('sudo vpnc-disconnect')    #VPN disconnect

main(years)
