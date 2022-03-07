from matplotlib.pyplot import polar
from b2blaze import B2
import time

bucketname = 'photovoltaik'
plot_filename = 'mike_last7days.png'

def upload_plot(plot_filename):
    b2 = B2()
    bucket = b2.buckets.get(bucketname)
    plot_file = open(plot_filename, 'rb')
    #try it 10 times
    for i in range(1,10):
        try: 
            print (f'try - {i} ...') 
            rc = bucket.files.upload(contents=plot_file, file_name=plot_filename)
            if 'backblaze' in rc.url:
                break
        except Exception as e:
            print ("sleep 120 sec", e)
            time.sleep(120)
            next

upload_plot(plot_filename)