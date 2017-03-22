import os
import rrdtool
from datetime import datetime, timedelta
from time import mktime
import time
import requests, json
from requests.auth import HTTPBasicAuth

def changedate(datestr):
    date_obj = datetime.strptime(datestr, "%Y%m%d%H%M")
    return date_obj


def freq_to_mins(md):
    FREQ_MAP = {'ONE_MIN': 1, 'TEN_MIN': 10, 'SIXTY_MIN': 60}
    return FREQ_MAP[md['frequency']]


def duration_length(start, end, freq):
    length = int((end - start).seconds / 60 / freq) + int((end - start).days * 24 * 60 / freq)
    return length


# The report will generate data for the last 1-hour period before the current hour of the current day.
# It needs to be run for every 1 hours using cron. Prefer to run it at 10 minutes after every hour so that it can pull previous hour data
end_time = datetime.now()
end_time = (end_time + timedelta(hours=0)).replace(minute=1, second=0, microsecond=0)
end_epoch = int(mktime(end_time.timetuple())) * 1000
start_time = (end_time - timedelta(hours=1)).replace(minute=1, second=0, microsecond=0)
start_epoch = int(mktime(start_time.timetuple())) * 1000
print(start_epoch)
print(end_epoch)
# Pulls data from Monday to Sunday into a single file for each backend.
week_monday = start_time - timedelta(days=start_time.weekday())

# Get Metrics
apps = ['Cars']
target_metrics = ['Calls per Minute', 'Number of Slow Calls', 'Average Response Time (ms)','Errors per Minute']
metric_path = 'Overall Application Performance|*'
metric_name = ''
prevmetric_name = ''
for app in apps:
    export_header = 'datetime'
    url = 'http://localhost:8090/controller/rest/applications/' + app + '/metric-data?time-range-type=BETWEEN_TIMES&start-time=' + str(start_epoch) + '&end-time=' + str(end_epoch) + '&metric-path=' + metric_path + '&rollup=false&output=JSON'
    resp = requests.get(url, auth=HTTPBasicAuth('admin@customer1', 'AppDynamics'))
    # reader = codecs.getreader("utf-8")
    md_list = json.loads(resp._content.decode('utf-8'))

    freq = freq_to_mins(md_list[0])
    metrics = {}
    for md in md_list:
        if len(md['metricValues']) > 0:
            # Get the last two components of the metric path. This should be 'backend_name|metric_name'.
            backend_name, metric_name = md['metricPath'].split('|')[-2:]
            print(metric_name)
            if metric_name in target_metrics:
                prevmetric_name = metric_name
                for i in range(0, len(md['metricValues'])):
                    metric_time = int((md['metricValues'][i]['startTimeInMillis']) / 1000)
                    if metrics.has_key(metric_time):
                        metrics[metric_time].append(md['metricValues'][i]['value'])
                    else:
                        metrics[metric_time] = []
                        metrics[metric_time].append(md['metricValues'][i]['value'])

    # Write to RRD
    keys = sorted(metrics.keys())
    print(len(keys))
    for key in keys:
        rrd_string = str(key) 
        for metric in metrics[key]:
            rrd_string = rrd_string + ':' + str(metric)
        print(rrd_string)
        rrdtool.update("appdStats.rrd",rrd_string)
