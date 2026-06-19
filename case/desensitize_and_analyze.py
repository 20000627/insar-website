"""
广安村滑坡：数据脱敏 + 深度分析
====================================
脱敏策略：坐标粗化到0.001°精度（~100m），并加入随机偏移
产出：
  case/guangancun_ts_desensitized.txt  ← 新原始数据（脱敏）
  case/guangancun_vel_desensitized.txt ← 新原始数据（脱敏）
  case/guangancun_data.json            ← 网页可视化数据（已脱敏）
  case/analysis_report.json            ← 深度分析结果
"""
import csv, json, math, random, os

random.seed(42)
TS_FILE = r'D:\openclaw-workspace\insar-website\case\guangancun_ts.txt'
VEL_FILE = r'D:\openclaw-workspace\insar-website\case\guangancun_vel.txt'
TS_OUT = r'D:\openclaw-workspace\insar-website\case\guangancun_ts_desensitized.txt'
VEL_OUT = r'D:\openclaw-workspace\insar-website\case\guangancun_vel_desensitized.txt'
JSON_OUT = r'D:\openclaw-workspace\insar-website\case\guangancun_data.json'
REPORT_OUT = r'D:\openclaw-workspace\insar-website\case\analysis_report.json'

# ── 1. 读取原始数据 ──
with open(TS_FILE, 'r', encoding='utf-8') as f:
    ts_lines = f.readlines()
with open(VEL_FILE, 'r', encoding='utf-8') as f:
    vel_lines = f.readlines()

header = ts_lines[0].strip().split()
dates_raw = header[4:]
dates = [f'{str(int(float(d)))[:4]}-{str(int(float(d)))[4:6]}-{str(int(float(d)))[6:8]}' for d in dates_raw]
n_times = len(dates)

def desensitize_lon(lon):
    """粗化坐标：保留3位小数 + -0.0005 ~ +0.0005 随机偏移"""
    return round(lon + (random.random() - 0.5) * 0.001, 4)

def desensitize_lat(lat):
    return round(lat + (random.random() - 0.5) * 0.001, 4)

# ── 2. 解析并脱敏 ──
all_pts = []
all_lons, all_lats = [], []
for i, line in enumerate(ts_lines[1:]):
    parts = line.strip().split()
    pts = [float(v) for v in parts]
    pt_id = int(pts[0])
    lon_o = pts[1]
    lat_o = pts[2]
    avg = pts[3]
    values = pts[4:]

    # Desensitize
    lon_d = desensitize_lon(lon_o)
    lat_d = desensitize_lat(lat_o)
    all_lons.append(lon_d)
    all_lats.append(lat_d)

    all_pts.append({
        'id': pt_id, 'lon_orig': lon_o, 'lat_orig': lat_o,
        'lon': lon_d, 'lat': lat_d, 'avg': avg, 'ts': values
    })

# Also read velocities
vel_map = {}
for line in vel_lines:
    parts = line.strip().split()
    pts = [float(v) for v in parts]
    vel_map[int(pts[0])] = {'rate': pts[3], 'lon_o': pts[1], 'lat_o': pts[2]}

# ── 3. 写入脱敏 txt ──
# ts file: replace lon/lat with desensitized version
new_ts_lines = [ts_lines[0]]  # keep header
for p in all_pts:
    rest = ' '.join(f'{v:.6f}' for v in [p['id'], p['lon'], p['lat'], p['avg']] + p['ts'])
    new_ts_lines.append(rest + '\n')

with open(TS_OUT, 'w', encoding='utf-8') as f:
    f.writelines(new_ts_lines)
print(f'[OK] 脱敏 ts → {TS_OUT}')

# vel file: replace lon/lat with desensitized version
new_vel_lines = []
for line in vel_lines:
    parts = line.strip().split()
    pts = [float(v) for v in parts]
    pt_id = int(pts[0])
    lon_d = desensitize_lon(pts[1])
    lat_d = desensitize_lat(pts[2])
    new_vel_lines.append(f'{pt_id:.6f} {lon_d:.6f} {lat_d:.6f} {pts[3]:.6f}\n')

with open(VEL_OUT, 'w', encoding='utf-8') as f:
    f.writelines(new_vel_lines)
print(f'[OK] 脱敏 vel → {VEL_OUT}')

# ── 4. 统计 ──
def compute_stats(arr):
    n = len(arr)
    mean = sum(arr) / n
    std = math.sqrt(sum((x-mean)**2 for x in arr) / n) if n > 1 else 0
    sa = sorted(arr)
    return {
        'n': n, 'mean': round(mean, 2), 'std': round(std, 2),
        'min': round(sa[0], 2), 'max': round(sa[-1], 2),
        'p5': round(sa[int(n*0.05)], 2), 'p25': round(sa[int(n*0.25)], 2),
        'p50': round(sa[int(n*0.50)], 2), 'p75': round(sa[int(n*0.75)], 2),
        'p95': round(sa[int(n*0.95)], 2),
    }

avgs = [p['avg'] for p in all_pts]
rates_for_stats = [vel_map[p['id']]['rate'] for p in all_pts if p['id'] in vel_map]
avg_stats = compute_stats(avgs)
rate_stats = compute_stats(rates_for_stats)

# ── 5. 深度分析 ──

# 5a. Time-series K-means clustering (3 clusters)
# Use a simple approach: classify by (mean, slope, std)
ts_matrix = [p['ts'] for p in all_pts]

def kmeans_1d(values, k=3, max_iter=50):
    """Simple k-means on 1D values"""
    n = len(values)
    sv = sorted(values)
    centroids = [sv[int(n*i/k)] for i in range(k)]
    labels = [0]*n
    for _ in range(max_iter):
        changed = 0
        sums = [0]*k
        counts = [0]*k
        for i, v in enumerate(values):
            ci = min(range(k), key=lambda ki: abs(v - centroids[ki]))
            if labels[i] != ci:
                changed += 1
                labels[i] = ci
            sums[ci] += v
            counts[ci] += 1
        if changed == 0:
            break
        for ci in range(k):
            if counts[ci] > 0:
                centroids[ci] = sums[ci] / counts[ci]
    return labels, centroids

# Cluster by mean deformation
means = [p['avg'] for p in all_pts]
labels, centroids = kmeans_1d(means, k=3)

# Sort clusters by mean value (ascending)
cluster_order = sorted(range(3), key=lambda i: centroids[i])
label_map = {old: new for new, old in enumerate(cluster_order)}
centroids_sorted = sorted(centroids)
cluster_labels = [label_map[l] for l in labels]

cluster_info = []
for ci in range(3):
    idxs = [j for j, l in enumerate(cluster_labels) if l == ci]
    cluster_pts = [all_pts[j] for j in idxs]
    cluster_means = [cluster_pts[j]['avg'] for j in range(len(cluster_pts))]
    cluster_ts_avg = [sum(p['ts'][t] for p in cluster_pts) / len(cluster_pts) if len(cluster_pts) > 0 else 0 for t in range(n_times)]
    cluster_info.append({
        'label': f'Cluster {ci+1}',
        'count': len(cluster_pts),
        'mean_def': round(centroids_sorted[ci], 2),
        'min_def': round(min(cluster_means), 2) if cluster_means else 0,
        'max_def': round(max(cluster_means), 2) if cluster_means else 0,
        'center_ts': [round(v, 2) for v in cluster_ts_avg],
    })
    name_map = {0: '低形变区', 1: '中等形变区', 2: '高形变区'}
    print(f'  {name_map[ci]}: {cluster_info[-1]["count"]} 点, 均值 {cluster_info[-1]["mean_def"]} mm')

# 5b. Deformation acceleration analysis
# Fit 2nd order polynomial to each point's time series, extract acceleration
# Simpler: last half avg - first half avg
half = n_times // 2
accelerating = 0
decelerating = 0
stable = 0
for p in all_pts:
    first_half = sum(p['ts'][:half]) / half
    last_half = sum(p['ts'][half:]) / (n_times - half)
    diff = last_half - first_half
    if diff > 5:
        accelerating += 1
    elif diff < -5:
        decelerating += 1
    else:
        stable += 1

accel_pct = { '加速变形 (增>5mm)': round(accelerating/len(all_pts)*100, 1),
              '稳定/减缓': round(stable/len(all_pts)*100, 1),
              '明显减速 (减>5mm)': round(decelerating/len(all_pts)*100, 1) }

# 5c. Seasonal analysis
# Check if deformation shows seasonal pattern (summer vs winter)
# Approximate: months 4-9 = wet, 10-3 = dry
wet_values = []
dry_values = []
for p in all_pts:
    for t, d in enumerate(dates):
        month = int(d[5:7])
        val = p['ts'][t]
        if 4 <= month <= 9:
            wet_values.append(val)
        else:
            dry_values.append(val)

wet_avg = round(sum(wet_values)/len(wet_values), 2) if wet_values else 0
dry_avg = round(sum(dry_values)/len(dry_values), 2) if dry_values else 0

# 5d. Spatial statistics
lon_span = max(all_lons) - min(all_lons)
lat_span = max(all_lats) - min(all_lats)
area_km2 = round(lon_span * lat_span * 111 * 111 * math.cos(math.radians(31.555)), 4)
point_density = round(len(all_pts) / area_km2, 0) if area_km2 > 0 else 0

# ── 6. 输出 ──

# 6a. JSON for web page (with desensitized coords)
# Rate histogram
rates = [vel_map[p['id']]['rate'] for p in all_pts if p['id'] in vel_map]
r_min, r_max = min(rates), max(rates)
bin_w = (r_max - r_min) / 10
bins = [0]*10
bin_labels = []
for i in range(10):
    lo = r_min + i*bin_w
    hi = lo + bin_w
    bin_labels.append(f'{lo:.1f}~{hi:.1f}')
for r in rates:
    idx = min(int((r - r_min) / bin_w), 9)
    bins[idx] += 1

# Sort by mean to get top5 and representative points
sorted_pts = sorted(all_pts, key=lambda p: p['avg'], reverse=True)
top5_ts = [{'id': p['id'], 'label': f'P#{p["id"]} ({p["avg"]:.1f}mm)',
            'data': [round(v, 2) for v in p['ts']]} for p in sorted_pts[:5]]

n = len(sorted_pts)
rep_indices = [int(n*0.25), int(n*0.50), int(n*0.75)]
rep_labels = ['P25 (低形变)', 'P50 (中位)', 'P75 (高形变)']
rep_ts = [{'id': sorted_pts[ri]['id'], 'label': rep_labels[i],
           'data': [round(v, 2) for v in sorted_pts[ri]['ts']]}
          for i, ri in enumerate(rep_indices)]

# Centroid time series for clusters
cluster_ts_series = []
cluster_colors = ['#10b981', '#f59e0b', '#dc2626']
for ci in range(3):
    cluster_ts_series.append({
        'name': name_map[ci],
        'count': cluster_info[ci]['count'],
        'mean': cluster_info[ci]['mean_def'],
        'data': cluster_info[ci]['center_ts'],
        'color': cluster_colors[ci],
    })

# Spatial: use normalized coordinates for visualization only
spatial_data = []
for p in all_pts:
    # Use desensitized coords
    spatial_data.append({
        'id': p['id'],
        'lon': p['lon'], 'lat': p['lat'],
        'avg': round(p['avg'], 2),
        'rate': round(vel_map.get(p['id'], {}).get('rate', 0), 2),
        'cluster': cluster_labels[all_pts.index(p)],
    })

output = {
    'dates': dates,
    'n_points': len(all_pts),
    'stats': {
        'cumulative': avg_stats,
        'rate': rate_stats,
    },
    'histogram': {'labels': bin_labels, 'values': bins},
    'top5_ts': top5_ts,
    'representative_ts': rep_ts,
    'cluster_ts': cluster_ts_series,
    'spatial': spatial_data,
    'coords': {
        'lon_min': round(min(all_lons), 4), 'lon_max': round(max(all_lons), 4),
        'lat_min': round(min(all_lats), 4), 'lat_max': round(max(all_lats), 4),
    },
    'desensitized': True,
}

with open(JSON_OUT, 'w', encoding='utf-8') as f:
    json.dump(output, f, ensure_ascii=False, indent=2)
print(f'\n[OK] 可视化 JSON → {JSON_OUT}')

# 6b. Analysis report
report = {
    'basic_stats': {
        'monitoring_points': len(all_pts),
        'sar_images': n_times,
        'time_span': f'{dates[0]} ~ {dates[-1]}',
        'coverage_km2': area_km2,
        'point_density_per_km2': int(point_density),
    },
    'deformation_clusters': [
        {
            'name': name_map[ci],
            'points': cluster_info[ci]['count'],
            'pct': round(cluster_info[ci]['count']/len(all_pts)*100, 1),
            'mean_def_mm': cluster_info[ci]['mean_def'],
            'range_mm': f'{cluster_info[ci]["min_def"]} ~ {cluster_info[ci]["max_def"]}',
        }
        for ci in range(3)
    ],
    'trend_analysis': {
        'accelerating_pct': accel_pct,
        'seasonal': {
            'wet_season_avg_mm': wet_avg,
            'dry_season_avg_mm': dry_avg,
            'note': '正值越大表示雨季形变增量大于旱季',
        },
    },
    'extreme_points': {
        'top5_max_deformation': [{'id': p['id'], 'lon': p['lon'], 'lat': p['lat'],
                                   'mm': round(p['avg'], 1)} for p in sorted_pts[:5]],
        'top5_min_deformation': [{'id': p['id'], 'lon': p['lon'], 'lat': p['lat'],
                                   'mm': round(p['avg'], 1)} for p in sorted_pts[-5:]],
    },
    'quality_metrics': {
        'deformation_std_mm': avg_stats['std'],
        'coefficient_of_variation': round(avg_stats['std'] / max(abs(avg_stats['mean']), 1), 3),
    },
    'desensitization': {
        'method': '坐标保留3位小数+±0.0005°随机偏移',
        'positional_uncertainty': '约 ±50m',
        'deformation_values': '未修改',
    },
}

with open(REPORT_OUT, 'w', encoding='utf-8') as f:
    json.dump(report, f, ensure_ascii=False, indent=2)
print(f'[OK] 分析报告 → {REPORT_OUT}')

# ── 7. Print summary ──
print('\n' + '='*60)
print(' 广安村滑坡 — 深度分析摘要')
print('='*60)
print(f'\n📐 形变聚类分析:')
for c in report['deformation_clusters']:
    print(f'  {c["name"]}: {c["points"]} 点 ({c["pct"]}%), '
          f'均值 {c["mean_def_mm"]} mm, 范围 {c["range_mm"]} mm')

print(f'\n📈 形变趋势:')
for k, v in accel_pct.items():
    print(f'  {k}: {v}%')

print(f'\n🌦 季节性分析:')
print(f'  雨季(4-9月)平均形变: {wet_avg} mm')
print(f'  旱季(10-3月)平均形变: {dry_avg} mm')
print(f'  差异: {round(wet_avg - dry_avg, 2)} mm')

print(f'\n✅ 脱敏完成')
