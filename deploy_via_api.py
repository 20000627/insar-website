"""閫氳繃 Git Data API 鍒涘缓鎻愪氦"""
import os, base64, json, urllib.request

TOKEN = "YOUR_GITHUB_TOKEN"
REPO = "20000627/insar-website"
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
        with urllib.request.urlopen(req, timeout=15) as r:
            return json.loads(r.read())
    except urllib.error.HTTPError as e:
        body = e.read().decode()
        print(f"[X] API {method} {path}: {e.code} - {body[:100]}")
        return None

files = []
for dirpath, dirnames, fnames in os.walk(ROOT):
    dirnames[:] = [d for d in dirnames if d != ".git"]
    for f in fnames:
        if f in ("check_links.py", "debug_github.py", "push_to_github.py"):
            continue
        full = os.path.join(dirpath, f)
        rel = os.path.relpath(full, ROOT).replace("\\", "/")
        with open(full, "rb") as fh:
            content = fh.read()
        files.append((rel, content))

print(f"Preparing {len(files)} files...")

# 1. Get latest commit SHA on main branch
ref = api("GET", "git/refs/heads/main")
if not ref:
    # Empty repo - need to create base tree
    base_tree = api("POST", "git/trees", {
        "tree": [{
            "path": ".gitkeep",
            "mode": "100644",
            "type": "blob",
            "content": ""
        }]
    })
    if not base_tree:
        print("[X] Cannot create tree")
        exit(1)
    
    # Create empty commit
    commit = api("POST", "git/commits", {
        "message": "Initial commit via API",
        "tree": base_tree["sha"]
    })
    if not commit:
        print("[X] Cannot create commit")
        exit(1)
    
    # Create branch
    api("POST", "git/refs", {
        "ref": "refs/heads/main",
        "sha": commit["sha"]
    })
    print("[OK] Empty base commit created")

# Try again to get ref
ref = api("GET", "git/refs/heads/main")
if not ref:
    print("[X] Cannot get branch ref")
    exit(1)

latest_sha = ref["object"]["sha"]
print(f"Latest commit: {latest_sha}")

# 2. Get the tree of latest commit
latest_commit = api("GET", f"git/commits/{latest_sha}")
if not latest_commit:
    print("[X] Cannot get commit")
    exit(1)
base_tree_sha = latest_commit["tree"]["sha"]
print(f"Base tree: {base_tree_sha}")

# 3. Create blobs for each file
blobs = []
for path, content in files:
    blob = api("POST", "git/blobs", {
        "content": base64.b64encode(content).decode(),
        "encoding": "base64"
    })
    if blob:
        blobs.append({
            "path": path,
            "mode": "100644",
            "type": "blob",
            "sha": blob["sha"]
        })
        print(f"  [OK] blob: {path}")
    else:
        print(f"  [X] blob failed: {path}")

# 4. Create new tree
new_tree = api("POST", "git/trees", {
    "base_tree": base_tree_sha,
    "tree": blobs
})
if not new_tree:
    print("[X] Tree creation failed")
    # Try without base tree
    new_tree = api("POST", "git/trees", {"tree": blobs})

if not new_tree:
    print("[X] Cannot create tree")
    exit(1)

print(f"New tree: {new_tree['sha']}")

# 5. Create commit
commit_data = {
    "message": "Deploy InSAR website",
    "tree": new_tree["sha"],
    "parents": [latest_sha]
}
commit = api("POST", "git/commits", commit_data)
if not commit:
    print("[X] Commit failed")
    exit(1)

print(f"Commit: {commit['sha']}")

# 6. Update branch ref
result = api("PATCH", "git/refs/heads/main", {
    "sha": commit["sha"],
    "force": True
})
if result:
    print("\n[OK] Website deployed!")
    print(f"     https://github.com/{REPO}")
else:
    print("\n[X] Branch update failed")
