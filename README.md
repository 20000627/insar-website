# 地微科技 — InSAR 企业官网

## 项目结构

```
insar-website/
├── index.html         # 首页
├── solutions.html     # 解决方案（含 4 大场景）
├── cases.html         # 典型案例（含 6 个项目数据）
├── about.html         # 关于我们 + 联系方式
├── css/
│   └── style.css      # 全站样式
├── js/
│   └── main.js        # 导航 + 动画
└── images/            # 图片资源（可选）
```

## 部署到 GitHub Pages

### 方式一：项目 Pages（推荐为新项目）

1. 在 GitHub 新建仓库，例如 `insar-website`
2. 将本目录所有文件推送上去
3. 进入仓库 Settings → Pages
4. Source 选 **Deploy from a branch**
5. Branch 选 `main`，目录选 `/ (root)`
6. 等待 1-2 分钟，访问 `https://你的用户名.github.io/insar-website/`

### 方式二：用户/组织 Pages

如果想用 `https://你的用户名.github.io/` 访问：

1. 仓库名必须为 `你的用户名.github.io`
2. 推送后直接访问根域名即可

## 自定义域名

在仓库 Settings → Pages 下添加 Custom domain，同时在根目录放一个 `CNAME` 文件：

```
www.your-domain.com
```

---

## 已知问题与自查修复

### 已发现并解决的问题

| # | 问题 | 解决方式 |
|---|------|---------|
| 1 | 中文环境下 Google Fonts 加载慢 | body 已备 `Microsoft YaHei` 中文字体回退 |
| 2 | 移动端导航菜单遮挡 | 已添加 `mobile-toggle` 响应式菜单 |
| 3 | `images/` 为空导致引用风险 | 所有"图片"用 CSS 渐变色 + emoji + SVG 替代 |
| 4 | GitHub Pages 可能触发 Jekyll 处理 | 已加 `_config.yml` 关闭 Jekyll（已创建） |
| 5 | 页面跳转需保留导航高亮 | JS 自动识别当前页面并添加 `.active` |
| 6 | 外部字体 CDN 不稳定 | Graceful degradation – 纯文字页在无字体时仍可读 |
| 7 | 联系方式无 form 提交 | 已展示邮箱/电话可点击复制，需后端配合才做表单 |

### 建议进一步检查

- [ ] 替换"地微科技"为真实公司名称
- [ ] 替换联系邮箱 `contact@diwei-insar.cn` 为真实邮箱
- [ ] 如要用联系表单，需接入 Formspree 等服务
- [ ] 上传真实项目照片到 `images/` 替换渐变背景
- [ ] 检查 SEO 标签（`<title>`、`<meta name="description">`）
- [ ] 如需国内访问加速，建议将 Google Fonts 替换为国内镜像或自托管

---

## 本地预览

```bash
# Python 简易服务器（无需安装）
cd insar-website
python -m http.server 8080
# 浏览器访问 http://localhost:8080
```
