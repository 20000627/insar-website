"""Debug: test GitHub API access"""
import urllib.request, json

TOKEN = "YOUR_GITHUB_TOKEN"
REPO = "20000627/insar-website"

# Test 1: Basic auth check
req = urllib.request.Request("https://api.github.com/user")
req.add_header("Authorization", f"token {TOKEN}")
try:
    with urllib.request.urlopen(req, timeout=10) as r:
        user = json.loads(r.read())
        print(f"[OK] Authenticated as: {user.get('login')}")
        print(f"    Scopes: {r.headers.get('X-OAuth-Scopes', 'unknown')}")
except Exception as e:
    print(f"[X] Auth failed: {e}")

# Test 2: Check repo access
req2 = urllib.request.Request(f"https://api.github.com/repos/{REPO}")
req2.add_header("Authorization", f"token {TOKEN}")
try:
    with urllib.request.urlopen(req2, timeout=10) as r:
        repo = json.loads(r.read())
        print(f"[OK] Repo: {repo.get('full_name')}")
        print(f"    Default branch: {repo.get('default_branch')}")
        print(f"    Permissions: {repo.get('permissions')}")
except Exception as e:
    print(f"[X] Repo access failed: {e}")

# Test 3: Push a small test file
import base64
data = {
    "message": "test upload",
    "content": base64.b64encode(b"hello world").decode(),
    "branch": "main",
}
req3 = urllib.request.Request(
    f"https://api.github.com/repos/{REPO}/contents/test.txt",
    method="PUT",
    data=json.dumps(data).encode()
)
req3.add_header("Authorization", f"token {TOKEN}")
req3.add_header("Content-Type", "application/json")
try:
    with urllib.request.urlopen(req3, timeout=10) as r:
        print(f"[OK] Test file uploaded! Status: {r.status}")
        print(f"    URL: {json.loads(r.read()).get('content',{}).get('html_url','')}")
except urllib.error.HTTPError as e:
    body = e.read().decode()
    print(f"[X] Upload failed: {e.code}")
    print(f"    Response: {body[:200]}")
except Exception as e:
    print(f"[X] Upload error: {e}")
