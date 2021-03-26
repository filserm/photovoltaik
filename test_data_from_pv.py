import requests

def get_values_from_pv(url):
    headers={}

    data = {
    'aggregate': 'day',
    'start_day': '24.03.2021',
    'start_time': '00:00',
    'end_day': '25.03.2021',
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
        print (line_item)
        if 4 <= len(line_item) <=6 :
            datum      = line_item[0]
            wr_gesamt  = line_item[1]
            wr1        = line_item[2]
            wr2        = line_item[3]

            value_dict = { datum: [wr_gesamt, wr1, wr2] }
            values.update(value_dict)


url= 'http://192.168.178.58/cgi-bin/download.csv/'

get_values_from_pv(url)