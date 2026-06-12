"""End-to-end API smoke test against a running local server."""
import json
import sys

import httpx

BASE = "http://localhost:8000"
client = httpx.Client(base_url=BASE, timeout=30)
failures = []
TID = None


def check(name, fn):
    try:
        fn()
        print(f"  PASS  {name}")
    except Exception as exc:
        failures.append(name)
        print(f"  FAIL  {name}: {exc}")


def _expect(actual, *allowed):
    assert actual in allowed, f"got {actual}"


# --- logins -------------------------------------------------------------------
r = client.post("/auth/login", json={"email": "demo@tenderradar.example",
                                     "password": "Demo@12345"})
r.raise_for_status()
demo_h = {"Authorization": f"Bearer {r.json()['access_token']}"}
demo_refresh = r.json()["refresh_token"]

admin_h = {"Authorization": "Bearer " + client.post(
    "/auth/login", json={"email": "admin@tenderradar.example",
                         "password": "Admin@12345"}).json()["access_token"]}
free_h = {"Authorization": "Bearer " + client.post(
    "/auth/login", json={"email": "free@tenderradar.example",
                         "password": "Free@12345"}).json()["access_token"]}


# --- helper flows ----------------------------------------------------------------
def _register_flow():
    email = "smoke@test.example"
    r = client.post("/auth/register", json={
        "email": email, "password": "Smoke@12345", "company_name": "Smoke Co",
        "state": "Kerala", "industry": "IT"})
    assert r.status_code in (201, 409), r.text
    if r.status_code == 201:
        token = r.json()["dev_verification_token"]
        client.post("/auth/verify-email", json={"token": token}).raise_for_status()
    client.post("/auth/login", json={"email": email,
                                     "password": "Smoke@12345"}).raise_for_status()


def _reset_flow():
    r = client.post("/auth/forgot-password", json={"email": "smoke@test.example"})
    otp = r.json()["dev_otp"]
    client.post("/auth/reset-password", json={
        "email": "smoke@test.example", "otp": otp,
        "new_password": "Smoke@12345"}).raise_for_status()


def _portals():
    r = client.get("/portals", headers=demo_h)
    r.raise_for_status()
    assert len(r.json()) == 19, f"expected 19, got {len(r.json())}"


def _keywords():
    r = client.post("/keywords", headers=demo_h, json={
        "keyword_text": "ambulance AND ALS", "category": "secondary",
        "synonyms": ["life support"], "portals": []})
    r.raise_for_status()
    kid = r.json()["id"]
    client.put(f"/keywords/{kid}", headers=demo_h, json={
        "keyword_text": "ambulance", "category": "secondary",
        "synonyms": [], "portals": []}).raise_for_status()
    client.delete(f"/keywords/{kid}", headers=demo_h).raise_for_status()


def _free_limit():
    statuses = []
    for i in range(6):
        r = client.post("/keywords", headers=free_h,
                        json={"keyword_text": f"limit-test-{i}"})
        statuses.append(r.status_code)
    assert 402 in statuses, f"no 402 in {statuses}"
    for k in client.get("/keywords", headers=free_h).json():
        if k["keyword_text"].startswith("limit-test"):
            client.delete(f"/keywords/{k['id']}", headers=free_h)


def _search():
    r = client.get("/tenders", headers=demo_h,
                   params={"keyword": "drone", "sort": "relevance"})
    r.raise_for_status()
    d = r.json()
    assert d["total"] > 0, "no results for 'drone'"
    print(f"        drone -> {d['total']} tenders, top score "
          f"{d['items'][0]['relevance_score']}")


def _gating():
    r = client.get("/tenders", headers=free_h, params={"page_size": 100})
    r.raise_for_status()
    portals = {t["portal_code"] for t in r.json()["items"]}
    assert portals <= {"gem", "cppp", "etenders-nic"}, f"free saw {portals}"


def _detail():
    global TID
    TID = client.get("/tenders", headers=demo_h,
                     params={"keyword": "drone"}).json()["items"][0]["id"]
    client.get(f"/tenders/{TID}", headers=demo_h).raise_for_status()
    client.get(f"/tenders/{TID}/related", headers=demo_h).raise_for_status()
    r = client.get(f"/tenders/{TID}/summary", headers=demo_h)
    r.raise_for_status()
    assert len(r.json()["summary"]) == 3


def _status():
    r = client.post(f"/tenders/{TID}/status", headers=demo_h,
                    json={"status": "bidding", "bookmarked": True, "notes": "EMD 2L"})
    r.raise_for_status()
    assert r.json()["user_status"] == "bidding" and r.json()["bookmarked"]
    bm = client.get("/tenders/bookmarks", headers=demo_h).json()
    assert any(t["id"] == TID for t in bm)


def _share():
    r = client.post(f"/tenders/{TID}/share", headers=demo_h)
    r.raise_for_status()
    token = r.json()["share_token"]
    client.get(f"/share/{token}").raise_for_status()  # public — no auth header


def _dash():
    s = client.get("/dashboard/stats", headers=demo_h)
    s.raise_for_status()
    assert s.json()["found"]["month"] > 0
    client.get("/dashboard/analytics", headers=demo_h).raise_for_status()
    client.get("/dashboard/calendar", headers=demo_h).raise_for_status()
    print(f"        stats: {json.dumps(s.json()['found'])}, "
          f"closing soon: {s.json()['closing_soon_count']}")


def _reports():
    for fmt in ("pdf", "csv", "xlsx"):
        r = client.post("/reports/generate", headers=demo_h,
                        json={"report_type": "weekly", "file_format": fmt})
        r.raise_for_status()
        rid = r.json()["id"]
        d = client.get(f"/reports/{rid}/download", headers=demo_h)
        d.raise_for_status()
        assert len(d.content) > 500, f"{fmt} too small"
        if fmt == "pdf":
            assert d.content[:4] == b"%PDF"
            print(f"        weekly pdf: {r.json()['tender_count']} tenders, "
                  f"{len(d.content) // 1024} KB")
    client.get("/reports", headers=demo_h).raise_for_status()


def _notif():
    client.get("/users/me/notifications", headers=demo_h).raise_for_status()
    client.post("/users/me/notifications/read-all", headers=demo_h).raise_for_status()


def _health():
    r = client.get("/admin/system-health", headers=admin_h)
    r.raise_for_status()
    h = r.json()
    print(f"        db={h['db_size']} cache={h['cache_backend']} tenders={h['tenders_total']}")


def _blacklist():
    r = client.post("/admin/blacklist", headers=admin_h,
                    json={"term": "spamword", "reason": "test"})
    assert r.status_code in (201, 409)
    bid = [b for b in client.get("/admin/blacklist", headers=admin_h).json()
           if b["term"] == "spamword"][0]["id"]
    blocked = client.post("/keywords", headers=demo_h, json={"keyword_text": "spamword"})
    assert blocked.status_code == 400, blocked.status_code
    client.delete(f"/admin/blacklist/{bid}", headers=admin_h).raise_for_status()


def _tier():
    users = client.get("/admin/users", headers=admin_h,
                       params={"q": "smoke"}).json()["items"]
    uid = users[0]["id"]
    client.put(f"/admin/users/{uid}", headers=admin_h,
               json={"tier": "pro"}).raise_for_status()
    client.put(f"/admin/users/{uid}", headers=admin_h,
               json={"tier": "free"}).raise_for_status()


# --- run ---------------------------------------------------------------------------
check("refresh token rotation", lambda: client.post(
    "/auth/refresh", json={"refresh_token": demo_refresh}).raise_for_status())
check("register + dev verification + login", _register_flow)
check("forgot/reset password (dev otp)", _reset_flow)
check("unauthenticated request rejected",
      lambda: _expect(client.get("/users/me").status_code, 401, 403))
check("GET /users/me", lambda: client.get("/users/me", headers=demo_h).raise_for_status())
check("GET /portals (19 seeded)", _portals)
check("GET /portals/status",
      lambda: client.get("/portals/status", headers=demo_h).raise_for_status())
check("keywords CRUD", _keywords)
check("keyword XSS sanitisation rejected", lambda: _expect(
    client.post("/keywords", headers=demo_h,
                json={"keyword_text": "<script>alert(1)</script>"}).status_code, 400, 422))
check("free tier keyword limit enforced", _free_limit)
check("tender search (FTS 'drone')", _search)
check("tender filters (portal+closing window)", lambda: client.get(
    "/tenders", headers=demo_h,
    params={"portal": "cppp", "closing_within_days": 30}).raise_for_status())
check("free tier portal gating", _gating)
check("tender detail + related + summary", _detail)
check("status + bookmark + notes", _status)
check("share link (public)", _share)
check("dashboard stats/analytics/calendar", _dash)
check("reports: generate pdf+csv+xlsx & download", _reports)
check("notifications endpoints", _notif)
check("scrape trigger (user, single portal)", lambda: client.post(
    "/scrape/trigger", headers=demo_h, json={"portal_code": "cppp"}).raise_for_status())
check("scrape all requires admin", lambda: _expect(
    client.post("/scrape/trigger", headers=demo_h, json={}).status_code, 403))
check("scrape logs",
      lambda: client.get("/scrape/logs", headers=demo_h).raise_for_status())
check("admin blocked for normal users", lambda: _expect(
    client.get("/admin/users", headers=demo_h).status_code, 403))
check("admin users list",
      lambda: client.get("/admin/users", headers=admin_h).raise_for_status())
check("admin system health", _health)
check("admin usage analytics",
      lambda: client.get("/admin/usage", headers=admin_h).raise_for_status())
check("admin blacklist add/enforce/remove", _blacklist)
check("admin user tier update", _tier)

print()
if failures:
    print(f"❌ {len(failures)} FAILED: {failures}")
    sys.exit(1)
print("✅ ALL SMOKE TESTS PASSED")
