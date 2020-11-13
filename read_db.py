import shelve
import os
from datetime import datetime as dt, timedelta

path = os.path.join(os.path.expanduser("~/photovoltaik/"), 'pv_daten')
data = shelve.open(path)

for k, item in sorted(data.items(), key=lambda x: (dt.strptime(x[0][:10], '%d.%m.%Y')), reverse=True):
    print (k, item)
 
