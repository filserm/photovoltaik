import requests, os
from datetime import datetime

user_key = os.environ.get('PUSHOVER_USER_KEY')
api_token = os.environ.get('PUSHOVER_API_TOKEN')

weekday = int(datetime.today().strftime('%w'))+1


def send_pushover(title, message):
    user_key = os.environ.get('PUSHOVER_USER_KEY')
    api_token = os.environ.get('PUSHOVER_API_TOKEN')

    r = requests.post("https://api.pushover.net/1/messages.json", data = {
    "token": api_token,
    "user": user_key,
    "title": title,
    "message": message,
    "sound": "none",
    "priority": 1,
    },
    files = {
      "attachment": ("image.jpg", open("/home/mike/photovoltaik/photovoltaik_modul.jpg", "rb"), "image/jpeg")
    }
    )
    print(r.text)
    


last_values_pv = {'mike ': ['27.03.2021 00:00:00', 52692, 16707, 35985], 'halle': ['27.03.2021 00:00:00', 132108, 32693, 32590, 33710, 33115]}

def init_body():
    return []


def send_email():
    email_from = os.environ.get('EMAIL_FROM')
    email_to = os.environ.get('EMAIL_TO')
    email_pw = os.environ.get('EMAIL_PW')
    port = 587  # For starttls
    smtp_server = "smtp.gmail.com"
    pushover_notification, message_pushover, body_dict ={}, {}, {}
    
    print (last_values_pv)
    datum = last_values_pv['mike '][0][:10]
    betreff = [f'PV - Anlage: {datum} '] 
    body = init_body()

    for k, v in last_values_pv.items():
        k=k.replace(' ','')
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
                if int(v[i]) < 20000:
                  pushover_notification[k] = 1
        
        try:
            if pushover_notification[k] == 1:
                message_pushover[k] = '\n'.join(body[:])
        except:
            pass

        link = f'\nhttps://f003.backblazeb2.com/file/photovoltaik/{k}_pv.html\n\n'
        body.append(link)

        body = '\n'.join(body)
        body_dict[k] = body[:]
        body = init_body()

    betreff = ''.join(betreff)
    

    #### send push notification if value is below limimt
    for k, v in message_pushover.items():
        title = f'Photovoltaik Minderertrag - Anlage: {k}'        
        message = v
        #send_pushover(title, message)

    #### send email if it's sunday
    if weekday == 2:
        body = init_body()
        body.append('Folgende Erträge wurden generiert:\n')
        for k, v in body_dict.items():
            body.append(v)
        body = ''.join(body)
        print (body)


    
    
send_email()
