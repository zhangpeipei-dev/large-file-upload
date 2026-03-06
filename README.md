# 大文件上传工具（FastAPI + Vue）

支持 **10GB 级别文件** 的分片上传系统，包含断点续传、JWT 登录鉴权、上传限速与存储配额。

## 功能特性

- 10GB 级大文件上传（分片流式写入）
- 断点续传（SQLite 持久化上传任务）
- 秒传（SHA-256 去重）
- 并发上传、失败重试、暂停/继续
- 用户登录鉴权（JWT）
- 按用户上传限速（Token Bucket）
- 按用户存储配额（初始化上传前校验）
- 上传历史记录（分页查询）
- 文件管理：列表、下载、删除

## 目录结构

```text
.
├── backend
│   ├── app
│   │   ├── auth.py
│   │   ├── config.py
│   │   ├── db.py
│   │   ├── main.py
│   │   ├── rate_limiter.py
│   │   ├── schemas.py
│   │   └── service.py
│   ├── requirements.txt
│   └── run.py
├── frontend
│   └── ...
└── README.md
```

## 后端启动

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python run.py
```

服务默认监听：`http://127.0.0.1:8000`

## 一体化启动（推荐）

先编译前端静态资源，再只启动 FastAPI：

```bash
cd frontend
npm install
npm run build
```

```bash
cd backend
python run.py
```

启动后直接访问：`http://127.0.0.1:8000`

## 前端开发模式（可选）

```bash
cd frontend
npm install
npm run dev
```

前端默认：`http://127.0.0.1:5173`

## Docker 运行

在项目根目录执行：

```bash
docker build -t large-file-upload:latest .
docker run --rm -p 8000:8000 \
  -e JWT_SECRET='change-this-secret' \
  -e DEFAULT_STORAGE_QUOTA_BYTES=$((50*1024*1024*1024)) \
  -e DEFAULT_UPLOAD_RATE_BYTES_SEC=$((20*1024*1024)) \
  large-file-upload:latest
```

访问：`http://127.0.0.1:8000`

## 认证与配额

- 注册：`POST /api/auth/register`
- 登录：`POST /api/auth/login`
- 当前用户：`GET /api/auth/me`
- 配额信息：`GET /api/auth/quota`
- 上传历史：`GET /api/history?page=1&page_size=10`

上传与文件接口均需 `Authorization: Bearer <token>`。

## 环境变量（后端）

- `JWT_SECRET`：JWT 签名密钥（生产环境必须修改）
- `JWT_EXPIRE_HOURS`：token 过期小时数（默认 12）
- `DEFAULT_STORAGE_QUOTA_BYTES`：新用户默认总配额（默认 50GB）
- `DEFAULT_UPLOAD_RATE_BYTES_SEC`：新用户默认上传限速（默认 20MB/s）

示例：

```bash
export JWT_SECRET='a-very-strong-secret'
export DEFAULT_STORAGE_QUOTA_BYTES=$((100*1024*1024*1024))
export DEFAULT_UPLOAD_RATE_BYTES_SEC=$((10*1024*1024))
```

## 核心上传接口

- `POST /api/uploads/init`
- `GET /api/uploads/{upload_id}`
- `POST /api/uploads/chunk`
- `POST /api/uploads/merge`
- `GET /api/files`
- `GET /api/files/{file_id}/download`
- `DELETE /api/files/{file_id}`
