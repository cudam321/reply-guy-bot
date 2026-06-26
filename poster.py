"""
poster.py — Posts a reply to a tweet using Playwright browser automation.
"""
import time
import json
import random
import subprocess
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeout
from config import COOKIES_PATH

def post_reply(tweet_id: str, author: str, reply_text: str, dry_run: bool = False) -> str | None:
    """
    Physically type and post a direct reply on the twitter UI using Playwright.
    Requires a valid cookies file from a logged-in session.
    """
    if dry_run:
        print(f"[poster] [DRY-RUN] Would reply to @{author} ({tweet_id}):\n  {reply_text}")
        return "dry-run-id"

    url = f"https://x.com/{author}/status/{tweet_id}"
    print(f"[poster] Opening {url} to post reply...")

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            args=[
                "--no-sandbox",
                "--disable-dev-shm-usage",
                "--disable-gpu",
                "--single-process",
                "--no-zygote",
                "--disable-extensions",
            ]
        )
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
            viewport={"width": 1280, "height": 800}
        )
        
        try:
            with open(COOKIES_PATH, "r") as f:
                cookies = json.load(f)
                
            # Handle different extension export formats (some wrap in object, some don't)
            if isinstance(cookies, dict):
                # If wrapped like {"cookies": [...]}, extract the array
                extracted = False
                for key, val in cookies.items():
                    if isinstance(val, list):
                        cookies = val
                        extracted = True
                        break
                # If it's just a single cookie dict, wrap it in an array
                if not extracted:
                    cookies = [cookies]
                    
            if not isinstance(cookies, list):
                print(f"[poster] ❌ {COOKIES_PATH} format invalid. Expected list, got {type(cookies)}")
                return None
                
            # Clean up cookies for Playwright's strict schema
            valid_samesite = {"Strict", "Lax", "None"}
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
                        del c["sameSite"] # Strip invalid sameSite entirely

            context.add_cookies(cookies)
        except FileNotFoundError:
            print(f"[poster] ❌ {COOKIES_PATH} missing. You MUST export your cookies first.")
            return None
        except Exception as e:
            print(f"[poster] ❌ Failed to load {COOKIES_PATH}: {e}")
            return None
            
        page = context.new_page()
        try:
            page.goto(url, wait_until="domcontentloaded", timeout=25_000)
            time.sleep(random.uniform(3, 5))
            
            # --- Login Diagnostics ---
            current_url = page.url
            if "/login" in current_url or "/i/flow/login" in current_url:
                print(f"[poster] ❌ Session Expired (Redirected to login: {current_url})")
                return None
                
            # Check for a 'Post' button or 'Account' indicator (generic way to see if we're in)
            is_logged_in = page.query_selector("a[data-testid='SideNav_NewTweet_Button']") or \
                           page.query_selector("div[data-testid='SideNav_AccountSwitcher_Button']")
            if not is_logged_in:
                # One last check: is the reply box there? If so, we're likely okay.
                if not page.query_selector("div[data-testid^='tweetTextarea_']"):
                    print("[poster] ❌ Not logged in (could not find authenticated UI elements)")
                    return None

            # The inline reply composer is usually labeled tweetTextarea_0
            editor = page.wait_for_selector("div[data-testid^='tweetTextarea_']", timeout=15_000)
            if not editor:
                print("[poster] ❌ Could not find the reply text box.")
                # Save screenshot for debugging (with timeout to avoid hang)
                try:
                    page.screenshot(path="poster_error.png", timeout=5000)
                except:
                    pass
                return None
                
            editor.click()
            time.sleep(random.uniform(0.5, 1.5))
            
            # Type the reply physically
            page.keyboard.insert_text(reply_text)
            
            time.sleep(random.uniform(1, 2))
            
            # The blue 'Reply' button inline
            reply_btn = page.wait_for_selector("button[data-testid='tweetButtonInline']", timeout=10_000)
            if not reply_btn:
                print("[poster] ❌ Could not find the Reply button.")
                return None
                
            reply_btn.click()
            
            # Wait for it to send
            time.sleep(random.uniform(3, 5))
            print(f"[poster] ✅ Reply physically typed and sent.")
            
        except Exception as e:
            print(f"[poster] ❌ Playwright posting failed: {e}")
            try:
                page.screenshot(path="poster_crash.png", timeout=5000)
            except:
                pass
            return None
        finally:
            # Re-export cookies to keep session alive
            try:
                updated_cookies = context.cookies()
                with open(COOKIES_PATH, "w") as f:
                    json.dump(updated_cookies, f, indent=2)
            except Exception:
                pass
            try:
                page.close()
            except Exception:
                pass
            try:
                context.close()
            except Exception:
                pass
            try:
                browser.close()
            except Exception:
                pass

    # Kill any orphaned chromium processes that survived browser.close()
    _kill_orphan_chromium()

    return tweet_id


def _kill_orphan_chromium():
    """Kill any leftover chromium/chrome processes to prevent memory leaks in Docker."""
    try:
        result = subprocess.run(
            ["pkill", "-f", "chromium|chrome"],
            capture_output=True, timeout=5
        )
        if result.returncode == 0:
            print("[poster] 🧹 Cleaned up orphaned chromium processes.")
    except Exception:
        pass
