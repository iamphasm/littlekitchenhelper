#!/usr/bin/env python3
"""Idempotent setup of collections, rules and settings for Little Kitchen Helper.

Usage:
  ./pocketbase superuser upsert admin@example.com 'long-password'
  python3 setup_pocketbase.py --url http://127.0.0.1:8090 \
      --admin-email admin@example.com --admin-password 'long-password' \
      --first-user mom --first-password 'another-long-password'
"""
import argparse
import json
import sys
import urllib.error
import urllib.request

PARENT = '@request.auth.role = "forelder"'
LOGGED_IN = '@request.auth.id != ""'


class Api:
    def __init__(self, base):
        self.base = base.rstrip("/")
        self.token = ""

    def call(self, method, path, body=None):
        data = json.dumps(body).encode() if body is not None else None
        req = urllib.request.Request(self.base + path, data=data, method=method)
        req.add_header("Content-Type", "application/json")
        if self.token:
            req.add_header("Authorization", self.token)
        try:
            with urllib.request.urlopen(req, timeout=30) as res:
                raw = res.read()
                return json.loads(raw) if raw else {}
        except urllib.error.HTTPError as e:
            detail = e.read().decode(errors="replace")
            raise SystemExit(f"{method} {path} -> {e.code}: {detail}")

    def login(self, email, password):
        res = self.call("POST", "/api/collections/_superusers/auth-with-password",
                        {"identity": email, "password": password})
        self.token = res["token"]


STAMPS = [
    {"name": "created", "type": "autodate", "onCreate": True, "onUpdate": False},
    {"name": "updated", "type": "autodate", "onCreate": True, "onUpdate": True},
]


def merge_fields(existing, wanted):
    """Keep system fields, add or replace wanted fields by name."""
    by_name = {f["name"]: f for f in existing}
    for f in wanted:
        old = by_name.get(f["name"])
        if old:
            f = {**f, "id": old["id"]}
        by_name[f["name"]] = f
    return list(by_name.values())


def upsert_collection(api, spec):
    try:
        current = api.call("GET", f"/api/collections/{spec['name']}")
    except SystemExit:
        current = None
    if current is None:
        api.call("POST", "/api/collections", {**spec, "fields": spec["fields"] + STAMPS})
        print(f"created {spec['name']}")
        return
    payload = {**spec, "fields": merge_fields(current["fields"], spec["fields"] + STAMPS)}
    api.call("PATCH", f"/api/collections/{current['id']}", payload)
    print(f"updated {spec['name']}")


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--url", default="http://127.0.0.1:8090")
    p.add_argument("--admin-email", required=True)
    p.add_argument("--admin-password", required=True)
    p.add_argument("--first-user", help="username of first parent account")
    p.add_argument("--first-password")
    a = p.parse_args()

    api = Api(a.url)
    api.login(a.admin_email, a.admin_password)

    # 1. users (built-in auth collection, extended)
    users = api.call("GET", "/api/collections/users")
    email_field = next((f for f in users["fields"] if f["name"] == "email"), None)
    if email_field:
        email_field["required"] = False  # email is optional for family members
    user_fields = [f for f in users["fields"] if f["name"] != "email"]
    user_fields.append(email_field) if email_field else None
    user_fields = merge_fields(user_fields, [
        {"name": "username", "type": "text", "required": True, "min": 2, "max": 40},
        {"name": "role", "type": "select", "required": True, "maxSelect": 1,
         "values": ["forelder", "barn"]},
        {"name": "phone", "type": "text", "max": 30},
        {"name": "memberNo", "type": "number", "onlyInt": True},
        {"name": "photo", "type": "file", "maxSelect": 1, "maxSize": 2097152,
         "mimeTypes": ["image/jpeg", "image/png", "image/webp"],
         "thumbs": ["96x96"]},
    ])
    api.call("PATCH", f"/api/collections/{users['id']}", {
        "fields": user_fields,
        "passwordAuth": {"enabled": True, "identityFields": ["username"]},
        "indexes": ["CREATE UNIQUE INDEX idx_users_username ON users (username COLLATE NOCASE)"],
        "listRule": LOGGED_IN,
        "viewRule": LOGGED_IN,
        "createRule": PARENT,
        "updateRule": (
            f'({PARENT}) || (id = @request.auth.id && @request.body.role:isset = false'
            ' && @request.body.memberNo:isset = false)'),
        "deleteRule": f'{PARENT} && id != @request.auth.id',
    })
    print("updated users")
    users = api.call("GET", "/api/collections/users")

    # 2. recipes
    upsert_collection(api, {
        "name": "recipes", "type": "base",
        "fields": [
            {"name": "title", "type": "text", "required": True, "max": 200},
            {"name": "description", "type": "text", "max": 2000},
            {"name": "freezer_ingredients", "type": "json", "maxSize": 20000},
            {"name": "extra_ingredients", "type": "json", "maxSize": 20000},
            {"name": "steps", "type": "json", "maxSize": 50000},
            {"name": "day", "type": "text", "max": 20},
            {"name": "manual", "type": "bool"},
            {"name": "date", "type": "text", "max": 40},
            {"name": "createdBy", "type": "relation", "collectionId": users["id"],
             "maxSelect": 1, "cascadeDelete": False},
        ],
        "listRule": LOGGED_IN, "viewRule": LOGGED_IN,
        "createRule": f'{LOGGED_IN} && @request.body.createdBy = @request.auth.id',
        "updateRule": f'{PARENT} || createdBy = @request.auth.id',
        "deleteRule": f'{PARENT} || createdBy = @request.auth.id',
    })
    recipes = api.call("GET", "/api/collections/recipes")

    # 3. weekplan (one record per weekday)
    upsert_collection(api, {
        "name": "weekplan", "type": "base",
        "fields": [
            {"name": "day", "type": "text", "required": True, "max": 20},
            {"name": "recipe", "type": "relation", "collectionId": recipes["id"],
             "maxSelect": 1, "cascadeDelete": False},
        ],
        "indexes": ["CREATE UNIQUE INDEX idx_weekplan_day ON weekplan (day)"],
        "listRule": LOGGED_IN, "viewRule": LOGGED_IN,
        "createRule": PARENT, "updateRule": PARENT, "deleteRule": PARENT,
    })

    # 4. todos
    upsert_collection(api, {
        "name": "todos", "type": "base",
        "fields": [
            {"name": "member", "type": "relation", "required": True,
             "collectionId": users["id"], "maxSelect": 1, "cascadeDelete": True},
            {"name": "text", "type": "text", "required": True, "max": 500},
            {"name": "day", "type": "text", "max": 20},
            {"name": "done", "type": "bool"},
            {"name": "createdBy", "type": "relation", "required": True,
             "collectionId": users["id"], "maxSelect": 1, "cascadeDelete": False},
        ],
        "listRule": LOGGED_IN, "viewRule": LOGGED_IN,
        "createRule": (f'{LOGGED_IN} && @request.body.createdBy = @request.auth.id'
                       f' && ({PARENT} || @request.body.member = @request.auth.id)'),
        # Parents edit anything. Children edit what they created, and may only
        # tick "done" on tasks that others put on their own list.
        "updateRule": (
            '@request.body.createdBy:isset = false && @request.body.member:isset = false && ('
            f'{PARENT} || createdBy = @request.auth.id || (member = @request.auth.id'
            ' && @request.body.text:isset = false && @request.body.day:isset = false))'),
        "deleteRule": f'{PARENT} || createdBy = @request.auth.id',
    })

    # 5. settings: app name + stricter rate limits
    settings = api.call("GET", "/api/settings")
    api.call("PATCH", "/api/settings", {
        "meta": {**settings.get("meta", {}), "appName": "Little Kitchen Helper"},
        "rateLimits": {"enabled": True, "rules": [
            {"label": "*:auth", "audience": "", "duration": 60, "maxRequests": 10},
            {"label": "/api/generate", "audience": "", "duration": 60, "maxRequests": 6},
            {"label": "*:create", "audience": "", "duration": 5, "maxRequests": 20},
            {"label": "/api/", "audience": "", "duration": 10, "maxRequests": 300},
        ]},
    })
    print("updated settings")

    # 6. first parent account (superuser bypasses the rules)
    if a.first_user:
        if not a.first_password or len(a.first_password) < 8:
            sys.exit("--first-password (min 8 chars) required with --first-user")
        found = api.call("GET", "/api/collections/users/records?perPage=1&filter="
                         + urllib.request.quote(f'username="{a.first_user}"'))
        if found["items"]:
            print("first user already exists")
        else:
            api.call("POST", "/api/collections/users/records", {
                "username": a.first_user, "role": "forelder",
                "password": a.first_password, "passwordConfirm": a.first_password,
                "emailVisibility": True})
            print(f"created parent account {a.first_user}")


if __name__ == "__main__":
    main()
