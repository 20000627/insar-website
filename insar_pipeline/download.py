"""
ESA Data Space / ASF 数据搜索与下载
"""
import requests, json, os, re, math
from datetime import datetime, timezone
from urllib.parse import quote
try:
    from tqdm import tqdm
    HAVE_TQDM = True
except ImportError:
    HAVE_TQDM = False

# ESA Data Space OData API
ESA_CATALOGUE = "https://catalogue.dataspace.copernicus.eu/odata/v1"
ESA_DOWNLOAD  = "https://download.dataspace.copernicus.eu/odata/v1"

class Sentinel1Search:
    """Sentinel-1 数据搜索（ESA Data Space）"""
    
    def __init__(self, username=None, password=None):
        self.auth = (username, password) if username and password else None
        self.session = requests.Session()
        if self.auth:
            self._login()
    
    def _login(self):
        """ESA Data Space OAuth 登录"""
        auth_url = "https://identity.dataspace.copernicus.eu/auth/realms/CDSE/protocol/openid-connect/token"
        try:
            r = self.session.post(auth_url, data={
                "grant_type": "password",
                "username": self.auth[0],
                "password": self.auth[1],
                "client_id": "cdse-public",
            }, timeout=15)
            if r.status_code == 200:
                token = r.json().get("access_token", "")
                self.session.headers.update({"Authorization": f"Bearer {token}"})
                print("[OK] ESA Data Space 登录成功")
            else:
                print(f"[!] 登录失败: HTTP {r.status_code}")
        except Exception as e:
            print(f"[!] 登录异常: {e}")
    
    def search_scenes(self, lon, lat, start_date, end_date,
                      max_results=50, platform="SENTINEL-1",
                      product_type="SLC"):
        """
        搜索 Sentinel-1 数据
        
        参数:
            lon, lat: float — 目标中心坐标
            start_date, end_date: str — "YYYY-MM-DD"
            max_results: int — 最大返回结果数
            platform: str — "SENTINEL-1" (默认S1A+S1B)
            product_type: str — "SLC" (原始) 或 "GRD"
        
        返回:
            list[dict] — 影像信息列表
        """
        # 构建 AOI 圆 (~100km 半径)
        buffer_deg = 1.0  # 约100km
        aoi = (f"lat GE {lat - buffer_deg} AND lat LE {lat + buffer_deg}"
               f" AND lon GE {lon - buffer_deg} AND lon LE {lon + buffer_deg}")
        
        # OData filter
        filters = (
            f"Collection/Name eq '{platform}'"
            f" and OData.CSC.Intersects(area=geography'SRID=4326;"
            f"POINT({lon} {lat})')"
            f" and ContentDate/Start gt {start_date}T00:00:00.000Z"
            f" and ContentDate/Start lt {end_date}T23:59:59.999Z"
            f" and Attributes/OData.CSC.StringAttribute/any("
            f"  a:a/Name eq 'productType' and a/OData.CSC.StringAttribute/Value eq '{product_type}')"
        )
        
        url = f"{ESA_CATALOGUE}/Products"
        params = {
            "$filter": filters,
            "$top": max_results,
            "$orderby": "ContentDate/Start asc",
            "$expand": "Attributes",
            "$count": True,
        }
        
        results = []
        print(f"[ESA] 搜索 {platform} {product_type}...")
        print(f"      位置: ({lat:.4f}, {lon:.4f})")
        print(f"      时段: {start_date} ~ {end_date}")
        
        try:
            r = self.session.get(url, params=params, timeout=30,
                                 headers={"Accept": "application/json"})
            if r.status_code != 200:
                print(f"[!] ESA API 错误: HTTP {r.status_code}")
                return results
            
            data = r.json()
            items = data.get("value", [])
            total = data.get("@odata.count", len(items))
            print(f"      找到 {total} 景")
            
            for item in items:
                scene = {
                    "id": item.get("Id", ""),
                    "name": item.get("Name", ""),
                    "date": item.get("ContentDate", {}).get("Start", "")[:10],
                    "size": item.get("ContentLength", 0),
                    "platform": self._parse_platform(item.get("Name", "")),
                    "orbit_dir": self._parse_orbit(item.get("Attributes", [])),
                    "relative_orbit": self._parse_relorbit(item.get("Attributes", [])),
                    "polarization": self._parse_polarization(item.get("Attributes", [])),
                }
                results.append(scene)
            
            return results
            
        except requests.exceptions.ConnectionError:
            print("[!] ESA Data Space 连接失败（可能需要代理）")
            return []
        except Exception as e:
            print(f"[!] 错误: {e}")
            return []
    
    def _parse_platform(self, name):
        if "S1A" in name: return "Sentinel-1A"
        if "S1B" in name: return "Sentinel-1B"
        return "Sentinel-1"
    
    def _parse_orbit(self, attrs):
        for a in attrs:
            if a.get("Name") == "orbitDirection":
                return a.get("OData.CSC.StringAttribute", {}).get("Value", "")
        return ""
    
    def _parse_relorbit(self, attrs):
        for a in attrs:
            if a.get("Name") == "relativeOrbitNumber":
                v = a.get("OData.CSC.StringAttribute", {}).get("Value", "")
                return int(v) if v.isdigit() else 0
        return 0
    
    def _parse_polarization(self, attrs):
        for a in attrs:
            if a.get("Name") == "polarisationmode":
                return a.get("OData.CSC.StringAttribute", {}).get("Value", "")
        return ""
    
    def get_download_url(self, product_id):
        """获取产品下载 URL"""
        return f"{ESA_DOWNLOAD}/Products({product_id})/$value"
    
    def download_product(self, product_id, output_path):
        """下载 Sentinel-1 产品"""
        url = self.get_download_url(product_id)
        headers = self.session.headers if self.auth else {}
        
        print(f"[下载] {os.path.basename(output_path)}")
        try:
            r = self.session.get(url, headers=headers, stream=True, timeout=30)
            if r.status_code != 200:
                print(f"  HTTP {r.status_code}")
                return False
            
            total = int(r.headers.get("content-length", 0))
            chunk_size = 8192
            cnt = 0
            
            # NOTE: Sentinel-1 SLC 产品 ~4GB, 这里提供下载框架
            # 实际使用时可能需要断点续传
            with open(output_path, "wb") as f:
                if HAVE_TQDM and total:
                    pbar = tqdm(total=total, unit="B", unit_scale=True)
                    for chunk in r.iter_content(chunk_size):
                        f.write(chunk)
                        pbar.update(len(chunk))
                    pbar.close()
                else:
                    for chunk in r.iter_content(chunk_size):
                        f.write(chunk)
                        cnt += len(chunk)
                        if cnt % (50 * 1024 * 1024) == 0:  # 每50MB汇报
                            print(f"  ... {cnt // (1024*1024)} MB")
            
            print(f"  [OK] 下载完成: {total // (1024*1024)} MB")
            return True
            
        except Exception as e:
            print(f"  [!!] 下载失败: {e}")
            return False


class ASFSearch:
    """ASF 数据搜索（轻量，无需认证的可公开搜索）"""
    
    BASE = "https://api.daac.asf.alaska.edu/services/search/param"
    
    @staticmethod
    def search(lon, lat, start, end, max_results=20):
        """搜索 Sentinel-1 场景"""
        url = f"{ASFSearch.BASE}?output=json&platform=S1&"
        url += f"intersectsWith=POINT({lon}%20{lat})&"
        url += f"start={start}&end={end}&maxResults={max_results}"
        
        try:
            r = requests.get(url, timeout=20)
            if r.status_code != 200:
                return []
            data = r.json()
            results = []
            for item in data.get("results", []):
                results.append({
                    "sceneName": item.get("sceneName", ""),
                    "polarization": item.get("polarization", ""),
                    "orbit": item.get("orbit", ""),
                    "relativeOrbit": item.get("relativeOrbit", ""),
                    "frameNumber": item.get("frameNumber", ""),
                    "url": item.get("downloadUrl", ""),
                })
            return results
        except Exception as e:
            print(f"[ASF] 搜索失败: {e}")
            return []
