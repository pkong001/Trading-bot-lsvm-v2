import datetime

def get_current_time():
    current_time = datetime.datetime.now()
    with open('./current_time/current_time.py', 'w') as f:
        f.write('current_time = "{}"\n'.format(current_time))
