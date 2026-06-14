"""Enable GitHub Pages via API"""
import json, urllib.request

TOKEN = ("github_pat_11AZQSM5A0wzTT1PDUclcH_opAWZZ72Tt69JKQMGNfT8LdPXg"
         "WL4dzfzzqbOPcAaeC6H6GHNCIWu4BVEAz")
REPO = "20000627/insar-website"

def api(method, path, data=None):
    url = f"https://api.github.com/repos/{REPO}/{path}"
    req = urllib.request.Request(url, method=method)
    req.add_header("Authorization", f"token {TOKEN}")
    req.add_header("Accept", "application/vnd.github.v3+json")
    if data:
        req.add_header("Content-Type", "application/json")
        req.data = json.dumps(data).encode()
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            return json.loads(r.read())
    except urllib.error.HTTPError as e:
        body = e.read().decode()
        print(f"[{e.code}] {body[:200]}")
        return None

# Step 1: Check current Pages status
print("Checking current Pages config...")
pages = api("GET", "pages")
if pages:
    print(f"  Status: {pages.get('status', 'unknown')}")
    print(f"  URL: {pages.get('html_url', 'N/A')}")
    print(f"  Branch: {pages.get('source', {}).get('branch', 'N/A')}")
    if pages.get("status") == "built":
        print("\n[OK] Pages already enabled and built!")
        html_url = pages.get("html_url", "https://20000627.github.io/insar-website/")
        print(f"    Visit: {html_url}")
        exit(0)
else:
    print("  Pages not yet configured, enabling now...")

# Step 2: Enable Pages
print("\nEnabling GitHub Pages...")
result = api("POST", "pages", {
    "source": {
        "branch": "main",
        "path": "/"
    }
})

if result:
    print(f"[OK] GitHub Pages enabled!")
    print(f"    URL: https://20000627.github.io/insar-website/")
    print(f"    Note: It may take 1-2 minutes for the site to be live.")
else:
    print("[X] Failed to enable Pages via API")
    print("    Please enable manually:")
    print("    1. Go to: https://github.com/20000627/insar-website/settings/pages")
    print("    2. Source: Deploy from branch → main → /(root) → Save")
