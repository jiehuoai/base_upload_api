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

# 在 FastAPI app 定义之前添加文件类型映射
MIME_TYPE_DIRECTORIES = {
    'image': 'images',  # image/jpeg, image/png 等都会存在 images 目录
    'video': 'videos',  # video/mp4 等会存在 videos 目录
    'audio': 'audios',  # audio/mpeg 等会存在 audios 目录
    'application/pdf': 'documents/pdf',
    'application/msword': 'documents/word',
    'application/vnd.openxmlformats-officedocument.wordprocessingml.document': 'documents/word',
    'application/vnd.ms-excel': 'documents/excel',
    'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet': 'documents/excel',
    'text': 'documents/text',  # text/plain 等会存在 documents/text 目录
}

def get_directory_by_mime_type(content_type: str) -> str:
    """根据 MIME 类型确定存储目录"""
    if not content_type:
        return 'others'
    
    # 获取主类型
    main_type = content_type.split('/')[0]
    
    # 优先检查完整的 MIME 类型
    if content_type in MIME_TYPE_DIRECTORIES:
        return MIME_TYPE_DIRECTORIES[content_type]
    
    # 然后检查主类型
    if main_type in MIME_TYPE_DIRECTORIES:
        return MIME_TYPE_DIRECTORIES[main_type]
    
    return 'others'

@app.post("/upload")
async def upload_file(file: UploadFile = File(...)):
    try:
        print(f"Received file: {file.filename}")
        print(f"Content type: {file.content_type}")
        
        # 获取文件目录
        directory = get_directory_by_mime_type(file.content_type)
        
        file_extension = file.filename.split('.')[-1] if '.' in file.filename else ''
        file_key = f"{directory}/{uuid.uuid4()}.{file_extension}" if file_extension else f"{directory}/{uuid.uuid4()}"
        
        # 创建临时文件
        with tempfile.NamedTemporaryFile(delete=False) as temp_file:
            content = await file.read()
            temp_file.write(content)
            temp_file.flush()
            
            try:
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
        
        public_url = f"https://bcs.jiehuo.ai/{file_key}"
        
        return {
            "success": True,
            "file_key": file_key,
            "url": public_url,
            "filename": file.filename,
            "content_type": file.content_type,
            "directory": directory
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