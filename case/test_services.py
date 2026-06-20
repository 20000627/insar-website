"""Test reachability of InSAR processing services from China"""
import requests, json

tests = []

# 1. ASF HyP3
tests.append(('ASF HyP3', 'https://hyp3-api.asf.alaska.edu/'))

# 2. ASF Sentinel-1 search
tests.append(('ASF S1 Search', 'https://hyp3-api.asf.alaska.edu/search/granules?' +
              'platform=SENTINEL-1&intersectsWith=POINT(109.63%2031.56)&start=2017-10-01&end=2017-11-30'))

# 3. ESA Data Space
tests.append(('ESA Data Space', 'https://catalogue.dataspace.copernicus.eu/odata/v1/Products?$top=1'))

# 4. LiCSBAS GitHub
tests.append(('LiCSBAS GitHub', 'https://raw.githubusercontent.com/yumorishita/LiCSBAS/main/README.md'))

# 5. COMET LiCSAR
tests.append(('LiCSAR', 'https://gws-access.jasmin.ac.uk/public/nceo_geohazards/LiCSAR_products/'))

# 6. COMET LiCSAR portal
tests.append(('LiCSAR Portal', 'https://comet.nerc.ac.uk/comet-licsar-portal/'))

# 7. MintPy GitHub
tests.append(('MintPy GitHub', 'https://raw.githubusercontent.com/insarlab/MintPy/main/README.md'))

print('=== InSAR 服务可达性测试 (from China) ===\n')
for name, url in tests:
    try:
        r = requests.get(url, timeout=10, headers={'User-Agent': 'Mozilla/5.0'})
        status = f'HTTP {r.status_code}'
        if r.status_code == 200:
            status += f' ({len(r.text)} bytes)' if len(r.text) < 10000 else ' (OK)'
            print(f'  [OK] {name}: {status}')
        else:
            print(f'  [--] {name}: {status}')
    except requests.exceptions.Timeout:
        print(f'  [!!] {name}: 超时')
    except requests.exceptions.ConnectionError:
        print(f'  [!!] {name}: 连接失败 (可能需要代理)')
    except Exception as e:
        print(f'  [!!] {name}: {e}')

print('\n=== 总结 ===')
print('如果 LiCSAR/ASF/ESA 都不可达，推荐的本地替代方案:')
print('  1. 使用已有的形变数据（如你提供的 guangancun 数据）')
print('  2. 安装 SNAP (离线安装包 ~1.5GB) + 小 ROI 处理')
print('  3. 或使用代理/VPN 访问云服务')
