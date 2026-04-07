import json, urllib.request, urllib.error

def post(url, payload):
    data=json.dumps(payload).encode()
    req=urllib.request.Request(url,data=data,headers={'Content-Type':'application/json'})
    try:
        resp=urllib.request.urlopen(req)
        return resp.read().decode()
    except urllib.error.HTTPError as e:
        print('HTTP', e.code, e.read().decode())
        return None

r = post('http://localhost:5000/auth/request-otp', {'mobile':'+911234567890'})
print('request-otp response:', r)
if not r:
    raise SystemExit(1)

obj = json.loads(r)
otp = obj.get('otp')
if not otp:
    print('No otp in response; abort')
    raise SystemExit(1)

v = post('http://localhost:5000/auth/verify-otp', {'mobile':'+911234567890','otp':otp})
print('verify-otp response:', v)
