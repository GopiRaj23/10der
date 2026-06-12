"""Browser-level UI verification: logs in as the demo user, walks every page,
captures screenshots and fails on console errors."""
import sys

from playwright.sync_api import sync_playwright

BASE = "http://localhost:5173"
OUT = "/tmp/ui"
errors: list[str] = []

with sync_playwright() as pw:
    browser = pw.chromium.launch(headless=True)
    page = browser.new_page(viewport={"width": 1440, "height": 900})
    page.on("console", lambda m: errors.append(m.text) if m.type == "error" else None)
    page.on("pageerror", lambda e: errors.append(str(e)))

    # Login page
    page.goto(f"{BASE}/login", wait_until="networkidle")
    page.screenshot(path=f"{OUT}/01_login.png")

    # Sign in as demo user
    page.fill("#email", "demo@tenderradar.example")
    page.fill("#password", "Demo@12345")
    page.click("button[type=submit]")
    page.wait_for_url(f"{BASE}/", timeout=15000)
    page.wait_for_selector("text=Closing in the next 7 days", timeout=15000)
    page.wait_for_timeout(1500)  # let charts/calendar settle
    page.screenshot(path=f"{OUT}/02_dashboard.png", full_page=True)

    # Search with keyword
    page.goto(f"{BASE}/search", wait_until="networkidle")
    page.fill("input[placeholder*='drone']", "thermal camera")
    page.click("button:has-text('Search')")
    page.wait_for_timeout(1200)
    page.screenshot(path=f"{OUT}/03_search.png", full_page=True)

    # Tender detail via first row
    page.locator("tbody tr td").first.click()
    page.wait_for_url("**/tenders/**", timeout=10000)
    page.wait_for_timeout(800)
    page.click("button:has-text('AI summary')")
    page.wait_for_selector("text=AI Summary", timeout=10000)
    page.screenshot(path=f"{OUT}/04_tender_detail.png", full_page=True)

    # My tenders
    page.goto(f"{BASE}/my-tenders", wait_until="networkidle")
    page.wait_for_timeout(800)
    page.screenshot(path=f"{OUT}/05_my_tenders.png")

    # Keywords
    page.goto(f"{BASE}/keywords", wait_until="networkidle")
    page.wait_for_timeout(600)
    page.screenshot(path=f"{OUT}/06_keywords.png", full_page=True)

    # Reports
    page.goto(f"{BASE}/reports", wait_until="networkidle")
    page.wait_for_timeout(600)
    page.screenshot(path=f"{OUT}/07_reports.png")

    # Alerts
    page.goto(f"{BASE}/alerts", wait_until="networkidle")
    page.wait_for_timeout(600)
    page.screenshot(path=f"{OUT}/08_alerts.png", full_page=True)

    # Admin (re-login as admin)
    page.click("button[title='Logout']")
    page.wait_for_url("**/login", timeout=10000)
    page.fill("#email", "admin@tenderradar.example")
    page.fill("#password", "Admin@12345")
    page.click("button[type=submit]")
    page.wait_for_url(f"{BASE}/", timeout=15000)
    page.goto(f"{BASE}/admin", wait_until="networkidle")
    page.wait_for_timeout(800)
    page.screenshot(path=f"{OUT}/09_admin_users.png")
    page.click("button:has-text('Scrapers')")
    page.wait_for_timeout(1000)
    page.screenshot(path=f"{OUT}/10_admin_scrapers.png", full_page=True)

    browser.close()

real_errors = [e for e in errors if "favicon" not in e.lower()]
if real_errors:
    print("CONSOLE/PAGE ERRORS:")
    for e in real_errors:
        print("  -", e[:300])
    sys.exit(1)
print("UI CHECK PASSED — 10 screenshots in", OUT)
