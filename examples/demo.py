"""Feed sample data into a running Quiet Sentinel instance."""
import json, urllib.request
for i in range(12):
    value = 94 if i == 11 else 20 + (i % 3)
    data = json.dumps({'host': 'gafcloud', 'metric':'cpu_percent', 'value':value}).encode()
    req=urllib.request.Request('http://127.0.0.1:8765/api/observe', data=data,headers={'Content-Type':'application/json'})
    with urllib.request.urlopen(req) as r:
        print(json.load(r))
