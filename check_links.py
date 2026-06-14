"""检查 HTML 链接完整性"""
import os, re

root = r'C:\Users\HP\.openclaw\workspace\insar-website'
errors = []

for fname in os.listdir(root):
    if not fname.endswith('.html'):
        continue
    path = os.path.join(root, fname)
    with open(path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    for m in re.finditer(r'href="([^"]+)"', content):
        link = m.group(1)
        if link.startswith(('http', '#', 'mailto')):
            continue
        target = os.path.join(root, link.replace('/', os.sep))
        if not os.path.exists(target):
            errors.append(f'{fname}: missing {link}')
    
    for m in re.finditer(r'src="([^"]+)"', content):
        link = m.group(1)
        if link.startswith(('http', '#')):
            continue
        target = os.path.join(root, link.replace('/', os.sep))
        if not os.path.exists(target):
            errors.append(f'{fname}: missing resource {link}')

for e in errors:
    print(f'[X] {e}')
if not errors:
    print('[OK] All internal links verified')

html_count = len([f for f in os.listdir(root) if f.endswith('.html')])
css_count = len(os.listdir(os.path.join(root, 'css')))
js_count = len(os.listdir(os.path.join(root, 'js')))

print(f'\nFiles: {html_count} HTML, {css_count} CSS, {js_count} JS')
