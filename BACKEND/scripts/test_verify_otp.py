import json
import urllib.request
import urllib.error

url='http://localhost:5000/auth/verify-otp'
data=json.dumps({'mobile':'+911234567890','otp':'989609'}).encode()
req=urllib.request.Request(url,data=data,headers={'Content-Type':'application/json'})
try:
    resp=urllib.request.urlopen(req)
    print(resp.read().decode())
except urllib.error.HTTPError as e:
    body=e.read().decode()
    print('STATUS',e.code)
    print(body)
except Exception as ex:
    print('EX', ex)
