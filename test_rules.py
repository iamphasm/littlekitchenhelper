import json, urllib.request, urllib.error
B = "http://127.0.0.1:8090"
def call(m, p, body=None, tok=""):
    r = urllib.request.Request(B + p, data=json.dumps(body).encode() if body is not None else None, method=m)
    r.add_header("Content-Type", "application/json")
    if tok: r.add_header("Authorization", tok)
    try:
        with urllib.request.urlopen(r) as x: return x.status, json.loads(x.read() or b"{}")
    except urllib.error.HTTPError as e: return e.code, json.loads(e.read() or b"{}")
def login(u, p):
    s, d = call("POST", "/api/collections/users/auth-with-password", {"identity": u, "password": p}); assert s == 200, d; return d["token"], d["record"]
fails = 0
def check(name, got, want):
    global fails
    ok = got == want; fails += not ok
    print("OK  " if ok else "FAIL", name, got, "(want", want, ")")
mt, mom = login("mom", "momsecret123")
print("mom:", mom["role"], mom["memberNo"])
for x in call("GET", "/api/collections/users/records?filter=" + urllib.request.quote('username="kid"'), None, mt)[1]["items"]: call("DELETE", f"/api/collections/users/records/{x['id']}", None, mt)
s, kid = call("POST", "/api/collections/users/records", {"username": "kid", "role": "barn", "password": "kidsecret123", "passwordConfirm": "kidsecret123", "emailVisibility": True}, mt)
check("parent creates kid", s, 200); print("kid memberNo", kid.get("memberNo"))
kt, kid = login("kid", "kidsecret123")
s, _ = call("POST", "/api/collections/users/records", {"username": "x", "role": "barn", "password": "xxxxxxxx1", "passwordConfirm": "xxxxxxxx1"}, kt); check("kid cannot create member", s, 400 if False else s)
check("kid create member blocked", s in (400, 403), True)
s, _ = call("PATCH", f"/api/collections/users/records/{kid['id']}", {"role": "forelder"}, kt); check("kid cannot promote self", s in (400, 403, 404), True)
s, _ = call("PATCH", f"/api/collections/users/records/{kid['id']}", {"phone": "123"}, kt); check("kid edits own phone", s, 200)
s, _ = call("PATCH", f"/api/collections/users/records/{mom['id']}", {"phone": "9"}, kt); check("kid edits mom", s in (403, 404), True)
# todos
s, tm = call("POST", "/api/collections/todos/records", {"member": kid["id"], "text": "by mom", "day": "Mandag", "done": False, "createdBy": mom["id"]}, mt); check("mom adds kid todo", s, 200)
s, tk = call("POST", "/api/collections/todos/records", {"member": kid["id"], "text": "by kid", "day": "Mandag", "done": False, "createdBy": kid["id"]}, kt); check("kid adds own todo", s, 200)
s, _ = call("POST", "/api/collections/todos/records", {"member": mom["id"], "text": "evil", "createdBy": kid["id"]}, kt); check("kid adds todo to mom", s in (400, 403), True)
s, _ = call("POST", "/api/collections/todos/records", {"member": kid["id"], "text": "spoof", "createdBy": mom["id"]}, kt); check("kid spoofs createdBy", s in (400, 403), True)
s, _ = call("PATCH", f"/api/collections/todos/records/{tm['id']}", {"done": True}, kt); check("kid ticks done on own-list todo", s, 200)
s, _ = call("PATCH", f"/api/collections/todos/records/{tm['id']}", {"text": "hacked"}, kt); check("kid edits text of mom-made todo", s in (400, 403, 404), True)
s, _ = call("PATCH", f"/api/collections/todos/records/{tk['id']}", {"done": True}, kt); check("kid edits own todo", s, 200)
s, _ = call("PATCH", f"/api/collections/todos/records/{tk['id']}", {"done": False}, mt); check("mom edits kid todo", s, 200)
s, _ = call("DELETE", f"/api/collections/todos/records/{tm['id']}", None, kt); check("kid deletes mom-made todo", s in (403, 404), True)
# recipes + weekplan (clean leftovers from earlier runs)
for x in call("GET", "/api/collections/weekplan/records", None, mt)[1]["items"]: call("DELETE", f"/api/collections/weekplan/records/{x['id']}", None, mt)
s, r = call("POST", "/api/collections/recipes/records", {"title": "Soup", "steps": ["a"], "createdBy": mom["id"]}, mt); check("mom adds recipe", s, 200)
s, _ = call("POST", "/api/collections/recipes/records", {"title": "Spoof", "createdBy": mom["id"]}, kt); check("kid spoofs recipe owner", s in (400, 403), True)
s, _ = call("DELETE", f"/api/collections/recipes/records/{r['id']}", None, kt); check("kid deletes mom recipe", s in (403, 404), True)
s, w = call("POST", "/api/collections/weekplan/records", {"day": "Mandag", "recipe": r["id"]}, mt); check("mom plans day", s, 200)
s, _ = call("PATCH", f"/api/collections/weekplan/records/{w['id']}", {"recipe": ""}, kt); check("kid edits weekplan", s in (403, 404), True)
s, _ = call("DELETE", f"/api/collections/recipes/records/{r['id']}", None, mt); check("mom deletes recipe", s, 204)
s, ww = call("GET", f"/api/collections/weekplan/records/{w['id']}", None, mt); print("weekplan after recipe delete:", s, ww.get("recipe") if s == 200 else ww)
# anon
s, _ = call("GET", "/api/collections/recipes/records"); check("anon list recipes", s in (200, 403), True); 
s, d = call("GET", "/api/collections/recipes/records"); check("anon sees nothing", d.get("items", []) , [] if s == 200 else d.get("items", []))
s, _ = call("POST", "/api/generate", {"prompt": "hi"}); check("anon generate", s, 401)
s, d = call("POST", "/api/generate", {"prompt": "hi"}, kt); print("generate no key:", s, d)
# member list visible, kid delete user
s, d = call("GET", "/api/collections/users/records", None, kt); check("kid lists members", s, 200); print([(x["username"], x["memberNo"], x.get("email")) for x in d["items"]])
s, _ = call("DELETE", f"/api/collections/users/records/{mom['id']}", None, kt); check("kid deletes mom", s in (403, 404), True)
s, _ = call("DELETE", f"/api/collections/users/records/{kid['id']}", None, mt); check("mom deletes kid", s, 204)
s, d = call("GET", "/api/collections/todos/records", None, mt); print("todos left (cascade):", [x["text"] for x in d["items"]])
print("FAILS:", fails)
