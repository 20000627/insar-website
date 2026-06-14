"""閫氳繃 GitHub API 鎺ㄩ€佹枃浠跺埌浠撳簱"""
import os, base64, json, urllib.request, urllib.error

TOKEN = "YOUR_GITHUB_TOKEN"
REPO = "20000627/insar-website"
BRANCH = "main"

ROOT = r"C:\Users\HP\.openclaw\workspace\insar-website"

def api(method, path, data=None):
    url = f"https://api.github.com/repos/{REPO}/{path}"
    req = urllib.request.Request(url, method=method)
    req.add_header("Authorization", f"token {TOKEN}")
    req.add_header("Accept", "application/vnd.github.v3+json")
    if data:
        req.add_header("Content-Type", "application/json")
        req.data = json.dumps(data).encode()
    try:
        with urllib.request.urlopen(req) as resp:
            return json.loads(resp.read())
    except urllib.error.HTTPError as e:
        body = e.read().decode()
        if e.code == 422 and "sha" in body:
            # File already exists, get its sha
            return api("GET", path.replace("contents/", ""))
        return None
    except Exception as e:
        print(f"  [!] API error: {e}")
        return None

def push_file(local_path, remote_path):
    """鎺ㄩ€佸崟涓枃浠?""
    with open(local_path, "rb") as f:
        content = f.read()
    
    # Check if file exists (get sha)
    existing = api("GET", f"contents/{remote_path}?ref={BRANCH}")
    sha = existing.get("sha") if existing and isinstance(existing, dict) else None
    
    data = {
        "message": f"Update {remote_path}",
        "content": base64.b64encode(content).decode(),
        "branch": BRANCH,
    }
    if sha:
        data["sha"] = sha
    
    result = api("PUT", f"contents/{remote_path}", data)
    status = "updated" if sha else "created"
    if result:
        print(f"  [OK] {remote_path} ({status})")
    else:
        print(f"  [X] {remote_path} failed")

# Collect files to push
files = []
for dirpath, dirnames, filenames in os.walk(ROOT):
    # Skip .git
    dirnames[:] = [d for d in dirnames if d != ".git"]
    for fname in filenames:
        full = os.path.join(dirpath, fname)
        # Skip git files and check_links.py (not needed on site)
        if fname == "check_links.py":
            continue
        if ".git" in full:
            continue
        rel = os.path.relpath(full, ROOT).replace("\\", "/")
        files.append((full, rel))

print(f"Pushing {len(files)} files to {REPO}...")
for local, remote in files:
    push_file(local, remote)

print("\nDone! Check: https://github.com/20000627/insar-website")
