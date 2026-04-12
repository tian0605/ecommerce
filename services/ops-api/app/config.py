"""Runtime configuration for the ops API."""
import os

from pydantic import BaseModel


DEFAULT_AUTH_USERS_JSON = '[{"username":"admin","display_name":"Ops Admin","password_hash":"pbkdf2_sha256$120000$qWZZluCu0Q9I0pek4041eA$1KqfRRjE-frz30aun3Lp3Rvjkb48AaBNdhZ4NW8cY7w","roles":["admin","owner"]},{"username":"operator","display_name":"Ops Operator","password_hash":"pbkdf2_sha256$120000$AxXjWA-3BmhdeLsyn79F5g$gmLmrTNqxYQ6hqlER-EgFz_5o97gLnqjeiFBGQhujaU","roles":["operator"]}]'


class Settings(BaseModel):
    db_host: str = 'localhost'
    db_name: str = 'ecommerce_data'
    db_user: str = 'superuser'
    db_password: str = 'Admin123!'
    db_pool_minconn: int = 1
    db_pool_maxconn: int = 12
    app_name: str = 'OpenClaw Ops API'
    app_version: str = '0.1.0'
    media_upload_dir: str = 'temp/uploads/product-media'
    media_upload_secret: str = 'openclaw-local-media-secret'
    media_upload_max_size_bytes: int = 10 * 1024 * 1024
    session_secret: str = 'openclaw-session-secret'
    session_max_age_seconds: int = 60 * 60 * 8
    auth_users_json: str = DEFAULT_AUTH_USERS_JSON
    config_encryption_secret: str = 'openclaw-config-encryption-secret'
    s3_bucket: str = ''
    s3_region: str = 'auto'
    s3_endpoint_url: str = ''
    s3_addressing_style: str = 'auto'
    s3_access_key_id: str = ''
    s3_secret_access_key: str = ''
    s3_prefix: str = 'ops-web-media'
    s3_public_base_url: str = ''
    media_max_image_width: int = 4096
    media_max_image_height: int = 4096


settings = Settings(
    db_host=os.getenv('OPS_API_DB_HOST', os.getenv('DB_HOST', 'localhost')),
    db_name=os.getenv('OPS_API_DB_NAME', os.getenv('DB_NAME', 'ecommerce_data')),
    db_user=os.getenv('OPS_API_DB_USER', os.getenv('DB_USER', 'superuser')),
    db_password=os.getenv('OPS_API_DB_PASSWORD', os.getenv('DB_PASSWORD', 'Admin123!')),
    db_pool_minconn=int(os.getenv('OPS_API_DB_POOL_MINCONN', '1')),
    db_pool_maxconn=int(os.getenv('OPS_API_DB_POOL_MAXCONN', '12')),
    app_name=os.getenv('OPS_API_APP_NAME', 'OpenClaw Ops API'),
    app_version=os.getenv('OPS_API_APP_VERSION', '0.1.0'),
    media_upload_dir=os.getenv('OPS_API_MEDIA_UPLOAD_DIR', 'temp/uploads/product-media'),
    media_upload_secret=os.getenv('OPS_API_MEDIA_UPLOAD_SECRET', 'openclaw-local-media-secret'),
    media_upload_max_size_bytes=int(os.getenv('OPS_API_MEDIA_UPLOAD_MAX_SIZE_BYTES', str(10 * 1024 * 1024))),
    session_secret=os.getenv('OPS_API_SESSION_SECRET', 'openclaw-session-secret'),
    session_max_age_seconds=int(os.getenv('OPS_API_SESSION_MAX_AGE_SECONDS', str(60 * 60 * 8))),
    auth_users_json=os.getenv('OPS_API_AUTH_USERS_JSON', DEFAULT_AUTH_USERS_JSON),
    config_encryption_secret=os.getenv('OPS_API_CONFIG_ENCRYPTION_SECRET', 'openclaw-config-encryption-secret'),
    s3_bucket=os.getenv('OPS_API_S3_BUCKET', os.getenv('OSS_BUCKET', '')),
    s3_region=os.getenv('OPS_API_S3_REGION', os.getenv('OSS_REGION', 'auto')),
    s3_endpoint_url=os.getenv('OPS_API_S3_ENDPOINT_URL', os.getenv('OSS_ENDPOINT_URL', '')),
    s3_addressing_style=os.getenv('OPS_API_S3_ADDRESSING_STYLE', 'auto'),
    s3_access_key_id=os.getenv('OPS_API_S3_ACCESS_KEY_ID', os.getenv('OSS_ACCESS_KEY_ID', '')),
    s3_secret_access_key=os.getenv('OPS_API_S3_SECRET_ACCESS_KEY', os.getenv('OSS_SECRET_ACCESS_KEY', '')),
    s3_prefix=os.getenv('OPS_API_S3_PREFIX', 'ops-web-media'),
    s3_public_base_url=os.getenv('OPS_API_S3_PUBLIC_BASE_URL', ''),
    media_max_image_width=int(os.getenv('OPS_API_MEDIA_MAX_IMAGE_WIDTH', '4096')),
    media_max_image_height=int(os.getenv('OPS_API_MEDIA_MAX_IMAGE_HEIGHT', '4096')),
)