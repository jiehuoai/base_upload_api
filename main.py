from fastapi import FastAPI, UploadFile, HTTPException, File
from fastapi.responses import StreamingResponse
import boto3
from botocore.config import Config
import os
from dotenv import load_dotenv
from typing import List
import uuid
from pathlib import Path
import aiofiles
import tempfile

# 获取当前文件所在目录
BASE_DIR = Path(__file__).resolve().parent
env_path = BASE_DIR / '.env'

# 使用绝对路径加载
load_dotenv(dotenv_path=env_path)

# 加载环境变量并添加调试信息
print("Current working directory:", os.getcwd())
print("Loading environment variables...")
load_dotenv(verbose=True)  # 启用详细输出

# 打印环境变量值（仅用于调试）
print("Environment variables:")
for var in ['R2_ACCOUNT_ID', 'R2_ACCESS_KEY_ID', 'R2_SECRET_ACCESS_KEY', 'R2_BUCKET_NAME']:
    print(f"{var}:", os.getenv(var))

# 检查必要的环境变量
required_env_vars = [
    'R2_ACCOUNT_ID',
    'R2_ACCESS_KEY_ID',
    'R2_SECRET_ACCESS_KEY',
    'R2_BUCKET_NAME'
]

for var in required_env_vars:
    if not os.getenv(var):
        raise ValueError(f"Missing required environment variable: {var}")

# 如果环境变量未被加载，直接设置（仅用于测试）
if not os.getenv('R2_ACCOUNT_ID'):
    os.environ['R2_ACCOUNT_ID'] = 'ad0490a1255bef48b67d2c6d79caddb9'
    os.environ['R2_ACCESS_KEY_ID'] = 'ec2d51ac617d3383a444e04f3509df78'
    os.environ['R2_SECRET_ACCESS_KEY'] = 'oHWl9EFVG_9JGe7Qlv445XQj8BojgoYd-7JN0d8g'
    os.environ['R2_BUCKET_NAME'] = 'base-common-storage'

app = FastAPI()

# R2配置
account_id = os.getenv('R2_ACCOUNT_ID')
# 使用 Cloudflare R2 标准端点
endpoint_url = f"https://{account_id}.r2.cloudflarestorage.com"

try:
    r2 = boto3.client(
        service_name='s3',
        endpoint_url=endpoint_url,
        aws_access_key_id=os.getenv('R2_ACCESS_KEY_ID'),
        aws_secret_access_key=os.getenv('R2_SECRET_ACCESS_KEY'),
        config=Config(
            signature_version='s3v4',
            region_name='auto',
            retries={
                'max_attempts': 3,
                'mode': 'standard'
            }
        ),
        verify=True,
        use_ssl=True
    )
    print("R2 client initialized successfully")
    
except Exception as e:
    print(f"Failed to initialize R2 client: {str(e)}")
    print(f"Endpoint URL: {endpoint_url}")
    raise

BUCKET_NAME = os.getenv('R2_BUCKET_NAME')

@app.post("/upload")
async def upload_file(file: UploadFile = File(...)):
    try:
        print(f"Received file: {file.filename}")
        print(f"Content type: {file.content_type}")
        
        file_extension = file.filename.split('.')[-1] if '.' in file.filename else ''
        file_key = f"{uuid.uuid4()}.{file_extension}" if file_extension else str(uuid.uuid4())
        
        # 创建临时文件
        with tempfile.NamedTemporaryFile(delete=False) as temp_file:
            content = await file.read()
            temp_file.write(content)
            temp_file.flush()
            
            try:
                # 修改上传参数，添加 ACL
                with open(temp_file.name, 'rb') as f:
                    r2.put_object(
                        Bucket=BUCKET_NAME,
                        Key=file_key,
                        Body=f,
                        ContentType=file.content_type or 'application/octet-stream',
                        ACL='public-read',
                        Metadata={
                            'original-filename': file.filename
                        }
                    )
            finally:
                os.unlink(temp_file.name)
        
        # 返回自定义域名的 URL
        public_url = f"https://base-common-storage.jiehuo.ai/{file_key}"
        
        return {
            "success": True,
            "file_key": file_key,
            "url": public_url,
            "filename": file.filename,
            "content_type": file.content_type
        }
    except Exception as e:
        print(f"Upload error: {str(e)}")
        print(f"Bucket: {BUCKET_NAME}")
        print(f"Access Key ID: {os.getenv('R2_ACCESS_KEY_ID')}")
        import traceback
        print(traceback.format_exc())
        raise HTTPException(
            status_code=500,
            detail=f"Failed to upload file: {str(e)}"
        )

@app.get("/download/{file_key}")
async def download_file(file_key: str):
    try:
        file = r2.get_object(Bucket=BUCKET_NAME, Key=file_key)
        
        def iterfile():
            yield from file['Body'].iter_chunks()
            
        return StreamingResponse(
            iterfile(),
            media_type=file.get('ContentType', 'application/octet-stream')
        )
    except Exception as e:
        raise HTTPException(status_code=404, detail="File not found")

@app.delete("/file/{file_key}")
async def delete_file(file_key: str):
    try:
        r2.delete_object(Bucket=BUCKET_NAME, Key=file_key)
        return {"success": True, "message": "File deleted successfully"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/files")
async def list_files():
    try:
        response = r2.list_objects_v2(Bucket=BUCKET_NAME)
        files = []
        if 'Contents' in response:
            for item in response['Contents']:
                files.append({
                    "key": item['Key'],
                    "size": item['Size'],
                    "last_modified": item['LastModified'].isoformat()
                })
        return {"files": files}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/presigned/{file_key}")
async def get_presigned_url(file_key: str, expiration: int = 3600):
    try:
        url = r2.generate_presigned_url(
            'get_object',
            Params={'Bucket': BUCKET_NAME, 'Key': file_key},
            ExpiresIn=expiration
        )
        return {"url": url}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) 