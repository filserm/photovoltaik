import smtplib, ssl, os


last_values_pv = {'mike ': ['27.03.2021 00:00:00', 52692, 16707, 35985], 'halle': ['27.03.2021 00:00:00', 132108, 32693, 32590, 33710, 33115]}

def send_email():
    email_from = os.environ.get('EMAIL_FROM')
    email_to = os.environ.get('EMAIL_TO')
    email_pw = os.environ.get('EMAIL_PW')
    port = 587  # For starttls
    smtp_server = "smtp.gmail.com"
    
    print (last_values_pv)
    datum = last_values_pv['mike '][0][:10]
    betreff, body = [f'PV - Anlage: {datum} '], ['Folgende Erträge wurden generiert:\n']

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

        link = f'\nhttps://f003.backblazeb2.com/file/photovoltaik/{k}_pv.html\n'
        body.append(link)

    betreff = ''.join(betreff)
    body = '\n'.join(body)

    print (betreff)
    
    
send_email()