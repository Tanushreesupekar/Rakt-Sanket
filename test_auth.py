import urllib.request, json, sys

def post(url, data):
    req = urllib.request.Request(url, json.dumps(data).encode(), {'Content-Type':'application/json'})
    try:
        with urllib.request.urlopen(req, timeout=5) as r:
            return json.loads(r.read()), r.status
    except urllib.error.HTTPError as e:
        return json.loads(e.read()), e.code

def get(url, token=None):
    req = urllib.request.Request(url)
    if token: req.add_header('Authorization', 'Bearer ' + token)
    try:
        with urllib.request.urlopen(req, timeout=5) as r:
            return json.loads(r.read()), r.status
    except urllib.error.HTTPError as e:
        try: return json.loads(e.read()), e.code
        except: return {'error': e.reason}, e.code

BASE = 'http://127.0.0.1:8000/api'
ok = True

# --- Admin login ---
print('=== ADMIN LOGIN ===')
data, code = post(BASE + '/auth/login', {'email': 'admin@raktsanket.org', 'password': 'AdminPassword123!'})
print('Status:', code)
if 'access_token' in data:
    admin_token = data['access_token']
    user = data.get('user', {})
    print('Role:', user.get('role'), '| Email:', user.get('email'))
    rq, rc = get(BASE + '/admin/blood-requests', admin_token)
    count = len(rq) if isinstance(rq, list) else rq
    print('Admin blood-requests:', rc, '| count =', count)
else:
    print('FAILED:', data)
    ok = False

print()

# --- Donor login ---
print('=== DONOR LOGIN ===')
data2, code2 = post(BASE + '/auth/login', {'email': 'donor.test@raktsanket.org', 'password': 'DonorPassword123!'})
print('Status:', code2)
if 'access_token' in data2:
    donor_token = data2['access_token']
    user2 = data2.get('user', {})
    print('Role:', user2.get('role'), '| Email:', user2.get('email'))
    rq2, rc2 = get(BASE + '/donors/me', donor_token)
    name = rq2.get('name') if isinstance(rq2, dict) else rq2
    print('Donor /me:', rc2, '| name =', name)
else:
    print('FAILED:', data2)
    ok = False

print()

# --- Donor should NOT access admin endpoint ---
print('=== DONOR ACCESS ADMIN ENDPOINT (should be 403) ===')
if 'donor_token' in dir():
    rq3, rc3 = get(BASE + '/admin/blood-requests', donor_token)
    print('Admin endpoint with donor token:', rc3, '(expected 403 or 401)')

print()
print('ALL DONE -', 'PASS' if ok else 'SOME FAILURES')
