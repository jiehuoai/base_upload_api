我来帮您创建一个使用 FastAPI 封装 Cloudflare R2 存储服务的 API 方案。这个方案将提供基本的文件上传、下载、删除等功能，适合移动端 APP 使用。

首先，让我们创建项目的基本结构：

```markdown:README.md
# FastAPI Cloudflare R2 Service

一个使用 FastAPI 封装 Cloudflare R2 存储服务的 API 服务。

## 功能特性

- 文件上传
- 文件下载
- 文件删除
- 文件列表获取
- 预签名 URL 生成

## 环境要求

- Python 3.8+
- FastAPI
- boto3
- python-multipart
- python-dotenv

## 安装

1. 克隆项目
```bash
git clone <repository-url>
```

2. 安装依赖
```bash
pip install -r requirements.txt
```

3. 配置环境变量
创建 `.env` 文件并添加以下配置：
```env
R2_ACCOUNT_ID=your_account_id
R2_ACCESS_KEY_ID=your_access_key_id
R2_SECRET_ACCESS_KEY=your_secret_access_key
R2_BUCKET_NAME=your_bucket_name
```

## 运行服务

```bash
uvicorn main:app --reload
```README.md

## API 接口

### 上传文件
- **POST** `/upload`
- 请求: multipart/form-data
- 参数: file (文件)
- 返回: 文件URL和其他元数据

### 下载文件
- **GET** `/download/{file_key}`
- 返回: 文件流

### 删除文件
- **DELETE** `/file/{file_key}`
- 返回: 删除状态

### 获取文件列表
- **GET** `/files`
- 返回: 文件列表

### 生成预签名URL
- **GET** `/presigned/{file_key}`
- 参数: expiration (过期时间，秒)
- 返回: 预签名URL
```

```
uvicorn main:app --reload
```

这个实现提供了以下功能：

1. **文件上传**：
   - 支持通过 multipart/form-data 上传文件
   - 自动生成唯一文件名
   - 返回文件的访问 URL

2. **文件下载**：
   - 支持流式下载文件
   - 自动设置正确的 Content-Type

3. **文件删除**：
   - 支持通过文件键删除文件

4. **文件列表**：
   - 获取存储桶中所有文件的列表
   - 包含文件大小和最后修改时间

5. **预签名 URL**：
   - 生成临时访问 URL
   - 可配置 URL 的有效期

要使用这个服务，移动端 APP 需要：

1. 上传文件时使用 multipart/form-data 格式
2. 下载文件时可以直接使用返回的预签名 URL 或调用下载接口
3. 存储文件的 key 以便后续操作

安全建议：

1. 在生产环境中添加适当的认证机制
2. 限制上传文件的大小和类型
3. 实现速率限制
4. 使用 HTTPS
5. 考虑添加文件访问权限控制

您可以根据具体需求调整这些接口，比如添加文件类型验证、大小限制等功能。
