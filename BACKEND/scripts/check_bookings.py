import json, urllib.request, urllib.error

url='http://localhost:5000/api/bookings'

# No auth
try:
    req=urllib.request.Request(url, headers={'Content-Type':'application/json'})
    resp=urllib.request.urlopen(req)
    print('NO AUTH STATUS', resp.getcode())
    print(resp.read().decode())
except urllib.error.HTTPError as e:
    print('NO AUTH STATUS', e.code)
    print(e.read().decode())

# Obtain token

def post(url,payload):
    data=json.dumps(payload).encode()
    req=urllib.request.Request(url,data=data,headers={'Content-Type':'application/json'})
    return urllib.request.urlopen(req).read().decode()

r = post('http://localhost:5000/auth/request-otp', {'mobile':'+911234567890'})
obj=json.loads(r)
print('OTP RESPONSE', obj)
otp=obj.get('otp')

v = post('http://localhost:5000/auth/verify-otp', {'mobile':'+911234567890','otp':otp})
vt=json.loads(v)
print('VERIFY RESPONSE keys', list(vt.keys()))
token=vt.get('token')

# call bookings with token
try:
    req2=urllib.request.Request(url, headers={'Content-Type':'application/json','Authorization':f'Bearer {token}'})
    resp=urllib.request.urlopen(req2)
    print('AUTH STATUS', resp.getcode())
    print(resp.read().decode())
except urllib.error.HTTPError as e:
    print('AUTH STATUS', e.code)
    print(e.read().decode())
