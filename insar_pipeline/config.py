"""
InSAR 全流程时序处理配置
"""
import os, json

# 项目根目录
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
WEBSITE_DIR = os.path.dirname(BASE_DIR)

# 默认配置
DEFAULTS = {
    "hyp3_api": "https://hyp3-api.asf.alaska.edu",
    "esa_catalogue": "https://catalogue.dataspace.copernicus.eu/odata/v1",
    "output_dir": os.path.join(WEBSITE_DIR, "case"),
    "s1_mission": "SENTINEL-1",
    "polarization": "VV+VH",
    "processing": {
        "looks_azimuth": 4,
        "looks_range": 20,
        "phase_filter_degree": 3,
        "phase_filter_alpha": 0.5,
        "unwrapping_method": "icu",   # icu or snaphu
        "include_dem": True,
        "include_inc_map": True,
        "include_lat_lon": True,
    },
}

# ASF HyP3 参考配置 (INSAR_GAMMA 作业类型)
HYP3_INSAR_DEFAULTS = {
    "job_type": "INSAR_GAMMA",
    "include_inc_map": True,
    "include_dem": True,
    "include_lat_lon": True,
    "include_look_vectors": False,
    "looks": "20x4",
    "phase_filter": True,
    "phase_filter_degree": 3,
    "phase_filter_alpha": 0.5,
    "unw_method": "icu",
    "apply_water_mask": True,
    "dem_matching": True,
}

def save_config(cfg, path=None):
    if path is None:
        path = os.path.join(BASE_DIR, "config.json")
    with open(path, "w") as f:
        json.dump(cfg, f, indent=2)

def load_config(path=None):
    if path is None:
        path = os.path.join(BASE_DIR, "config.json")
    if os.path.exists(path):
        with open(path) as f:
            return json.load(f)
    return {}
