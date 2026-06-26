import json
from playwright.sync_api import sync_playwright

with open("cookies.json", "r") as f:
    cookies = json.load(f)

extracted = False
if isinstance(cookies, dict):
    for key, val in cookies.items():
        if isinstance(val, list):
            cookies = val
            extracted = True
            break
    if not extracted:
        cookies = [cookies]

for c in cookies:
    if "sameSite" in c:
        s_val = str(c["sameSite"]).lower()
        if s_val in ["no_restriction", "unspecified", "none"]:
            c["sameSite"] = "None"
        elif s_val == "lax":
            c["sameSite"] = "Lax"
        elif s_val == "strict":
            c["sameSite"] = "Strict"
        else:
            del c["sameSite"]

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    try:
        context = browser.new_context()
        context.add_cookies(cookies)
        print("Success") # If this runs, it worked
    except Exception as e:
        print("Error:", e)
    finally:
        browser.close()
