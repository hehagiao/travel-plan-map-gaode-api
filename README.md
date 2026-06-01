# China Travel Map Explorer

一个本地运行的中国旅游地图工具，支持全国行政区分层浏览、地名检索，以及基于高德 API 的多目的地公共交通方案查询。

使用高德地图 API 的一种旅游路线、费用和出行方式规划可视化网页。

![Preview](./assets/github-cover-travel-map.svg)

## Features

- 全国地图常驻显示，缩放即可查看省、市、区县边界
- 支持搜索行政区名称或 `adcode` 并自动定位
- 支持查看区域名称、层级和 `adcode`
- 支持设置 1 个起点和多个终点，批量查询公共交通方案
- 自动整理高铁、动车、普通铁路与换乘结果，适合旅行路线比较

## Repository Structure

```text
china-map-public/
├─ assets/
│  └─ github-cover-travel-map.svg
├─ data/
│  ├─ datav/                      # 运行脚本后生成，仓库默认不附带
│  └─ maps/                       # 预留目录，仓库默认不附带
├─ scripts/
│  └─ download_datav_boundaries.py
├─ preview.html
├─ server.py
├─ .env.example
└─ .gitignore
```

## Quick Start

1. 进入项目目录。（注意：由于第3步中是需要在powershell中操作的，所以建议刚开始的时候不要在cmd中打开，而是在powershell中打开，）
2. 下载并生成地图数据：

```powershell
python .\scripts\download_datav_boundaries.py
```

3. 复制环境变量模板（注意，这个需要在powershell中输入）：

```powershell
Copy-Item .env.example .env
```

4. 在 `.env` 中填入你自己的高德 Web Service Key：

```env
AMAP_KEY=your_amap_key_here
```

5. 启动本地服务：

```powershell
python .\server.py
```

6. 打开浏览器访问：

```text
http://localhost:8788/preview.html
```

如果未配置 `AMAP_KEY`，地图浏览和搜索仍可使用，但公共交通查询接口会返回配置提示。

## Data Bootstrapping

仓库默认不直接附带第三方行政区边界数据。首次使用时，请运行：

```powershell
python .\scripts\download_datav_boundaries.py
```

这个脚本会：

- 从 `https://geo.datav.aliyun.com/areas_v3/bound` 下载分级边界数据
- 写入 `data/datav/*.json`
- 自动生成前端所需的 `combined_province.json`、`combined_city.json`、`combined_district.json`

## Environment Variables

- `AMAP_KEY`: 高德 Web Service API Key
- `AMAP_MAPS_API_KEY`: `AMAP_KEY` 的备用变量名
- `CHINA_MAP_PORT`: 本地服务端口，默认 `8788`

## Data Source And Copyright Note

- 行政区边界抓取源：`https://geo.datav.aliyun.com/areas_v3/bound`
- 相关文档页：`https://datav.aliyun.com/tools/atlas`
- 根据阿里云相关文档说明，相关行政区数据来源于高德

为避免直接再分发第三方边界数据，本仓库默认只公开代码与下载脚本，不默认附带边界数据文件。

使用者在下载、缓存、再分发或商用相关数据前，请自行核对源站服务协议、版权说明与使用限制。

## Tech Stack

- Frontend: HTML / CSS / JavaScript / SVG
- Backend: Python standard library `http.server` + `urllib`
- Data: local GeoJSON boundary files + AMap transit API
