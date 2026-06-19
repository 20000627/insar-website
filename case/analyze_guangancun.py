"""分析广安村滑坡形变数据"""
import csv, json, math, sys

TS_FILE = r'D:\openclaw-workspace\insar-website\case\guangancun_ts.txt'
VEL_FILE = r'D:\openclaw-workspace\insar-website\case\guangancun_vel.txt'
OUT_JSON = r'D:\openclaw-workspace\insar-website\case\guangancun_data.json'

# ── 1. 读取时序数据 ──
with open(TS_FILE, 'r', encoding='utf-8') as f:
    ts_lines = f.readlines()
header = ts_lines[0].strip().split()
dates_raw = header[4:]
dates = []
for d in dates_raw:
    s = str(int(float(d)))
    dates.append(f'{s[:4]}-{s[4:6]}-{s[6:8]}')
n_times = len(dates)

points_ts = []
for line in ts_lines[1:]:
    parts = line.strip().split()
    pts = [float(v) for v in parts]
    points_ts.append({
        'id': int(pts[0]), 'lon': pts[1], 'lat': pts[2],
        'avg': pts[3], 'ts': pts[4:]
    })

# ── 2. 读取速率数据 ──
with open(VEL_FILE, 'r', encoding='utf-8') as f:
    vel_lines = f.readlines()
points_vel = []
for line in vel_lines:
    parts = line.strip().split()
    pts = [float(v) for v in parts]
    points_vel.append({
        'id': int(pts[0]), 'lon': pts[1], 'lat': pts[2], 'rate': pts[3]
    })

# ── 3. 统计 ──
def compute_stats(arr):
    n = len(arr)
    mean = sum(arr) / n
    sq = [(x - mean) ** 2 for x in arr]
    std = math.sqrt(sum(sq) / n) if n > 1 else 0
    sa = sorted(arr)
    return {
        'n': n, 'mean': round(mean, 2), 'std': round(std, 2),
        'min': round(sa[0], 2), 'max': round(sa[-1], 2),
        'p5': round(sa[int(n * 0.05)], 2),
        'p25': round(sa[int(n * 0.25)], 2),
        'p50': round(sa[int(n * 0.50)], 2),
        'p75': round(sa[int(n * 0.75)], 2),
        'p95': round(sa[int(n * 0.95)], 2),
    }

avgs = [p['avg'] for p in points_ts]
rates = [p['rate'] for p in points_vel]
avg_stats = compute_stats(avgs)
rate_stats = compute_stats(rates)

print('=== 累计形变统计 (mm) ===')
for k, v in avg_stats.items():
    print(f'  {k}: {v}')
print()
print('=== 形变速率统计 (mm/yr) ===')
for k, v in rate_stats.items():
    print(f'  {k}: {v}')

# Top/bottom
sorted_avgs = sorted(points_ts, key=lambda p: p['avg'], reverse=True)
print(f'\n最大形变 TOP5:')
for p in sorted_avgs[:5]:
    print(f'  点#{p["id"]}  lon={p["lon"]:.4f} lat={p["lat"]:.4f}  均值={p["avg"]:.1f}mm')

print(f'\n最小形变 BOTTOM5:')
for p in sorted_avgs[-5:]:
    print(f'  点#{p["id"]}  lon={p["lon"]:.4f} lat={p["lat"]:.4f}  均值={p["avg"]:.1f}mm')

# ── 4. 生成可视化数据 (采样关键点) ──
# Rate histogram bins
rate_bins = [0]*10
bin_edges = []
r_min = min(rates)
r_max = max(rates)
bin_w = (r_max - r_min) / 10
for i in range(11):
    bin_edges.append(round(r_min + i * bin_w, 1))
for r in rates:
    idx = min(int((r - r_min) / bin_w), 9)
    rate_bins[idx] += 1

hist_data = {
    'labels': [f'{bin_edges[i]:.1f}~{bin_edges[i+1]:.1f}' for i in range(10)],
    'values': rate_bins
}

# Top 5 time series
top5_ts = []
for p in sorted_avgs[:5]:
    top5_ts.append({
        'id': p['id'],
        'label': f'P#{p["id"]} ({p["avg"]:.1f}mm)',
        'data': [round(v, 2) for v in p['ts']]
    })

# Representative 3: P50, P25, P75 repoints
sorted_pts = sorted(points_ts, key=lambda p: p['avg'])
n = len(sorted_pts)
rep_pts = [
    sorted_pts[int(n * 0.25)],
    sorted_pts[int(n * 0.50)],
    sorted_pts[int(n * 0.75)],
]
rep_ts = []
for p in rep_pts:
    rep_ts.append({
        'id': p['id'],
        'label': f'P#{p["id"]} ({p["avg"]:.1f}mm, P{25 + rep_pts.index(p)*25:.0f})',
        'data': [round(v, 2) for v in p['ts']]
    })

# Build spatial data (all points for map)
spatial_pts = [{
    'id': p['id'], 'lon': p['lon'], 'lat': p['lat'],
    'avg': round(p['avg'], 2),
    'rate': round(points_vel[i]['rate'], 2)
} for i, p in enumerate(points_ts)]

# ── 5. 输出 JSON ──
output = {
    'dates': dates,
    'stats': {
        'cumulative': avg_stats,
        'rate': rate_stats
    },
    'histogram': hist_data,
    'top5_ts': top5_ts,
    'representative_ts': rep_ts,
    'spatial': spatial_pts,
    'n_points': n,
    'coords': {
        'lon_min': min(lons:=[p['lon'] for p in points_ts]),
        'lon_max': max(lons),
        'lat_min': min(lats:=[p['lat'] for p in points_ts]),
        'lat_max': max(lats),
    }
}

with open(OUT_JSON, 'w', encoding='utf-8') as f:
    json.dump(output, f, ensure_ascii=False, indent=2)

print(f'\n[OK] 数据已输出: {OUT_JSON}')
print(f'     JSON 大小: {round(os.path.getsize(OUT_JSON)/1024, 1)} KB')
import os
print(f'     JSON 大小: {round(os.path.getsize(OUT_JSON)/1024, 1)} KB')
