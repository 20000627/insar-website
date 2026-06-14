"""Add SSH key to GitHub"""
import json, urllib.request

key = ("ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAICZ8noRTrBrWT9pdgz06mQoKrtwF"
       "flXcaDCH726/a+jf 20000627@github.com")
token = ("github_pat_11AZQSM5A0wzTT1PDUclcH_opAWZZ72Tt69JKQMGNfT8LdPXg"
         "WL4dzfzzqbOPcAaeC6H6GHNCIWu4BVEAz")

data = json.dumps({"title": "insar-website-deploy", "key": key}).encode()
req = urllib.request.Request("https://api.github.com/user/keys", data=data, method="POST")
req.add_header("Authorization", f"token {token}")
req.add_header("Content-Type", "application/json")

try:
    with urllib.request.urlopen(req, timeout=10) as r:
        result = json.loads(r.read())
        title = result.get("title", "")
        kid = result.get("id", "")
        print(f"[OK] SSH key added: {title} (id={kid})")
except urllib.error.HTTPError as e:
    body = e.read().decode()
    if "key is already in use" in body:
        print("[OK] SSH key already exists on GitHub")
    else:
        print(f"[X] {e.code}: {body[:200]}")
