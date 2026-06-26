import os
import uuid
import boto3
from botocore.exceptions import ClientError

AWS_REGION = os.getenv("AWS_REGION", "us-east-1")
S3_BUCKET = os.getenv("S3_BUCKET")

# When running on EC2 with an IAM Role attached, no keys are needed.
# boto3 picks credentials automatically from the instance profile.
s3_client = boto3.client("s3", region_name=AWS_REGION)

ALLOWED_EXT = {"png", "jpg", "jpeg", "gif", "webp"}


def allowed_file(filename: str) -> bool:
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXT


def upload_profile_image(file_storage) -> tuple[str, str] | tuple[None, None]:
    """Sube un archivo a S3 y retorna (key, url). Si falla, retorna (None, None)."""
    if not file_storage or file_storage.filename == "":
        return None, None
    if not allowed_file(file_storage.filename):
        return None, None

    ext = file_storage.filename.rsplit(".", 1)[1].lower()
    key = f"profiles/{uuid.uuid4().hex}.{ext}"

    try:
        s3_client.upload_fileobj(
            file_storage,
            S3_BUCKET,
            key,
            ExtraArgs={
                "ContentType": file_storage.mimetype or f"image/{ext}",
            },
        )
        url = f"https://{S3_BUCKET}.s3.{AWS_REGION}.amazonaws.com/{key}"
        return key, url
    except ClientError as e:
        print(f"[S3] Error uploading: {e}")
        return None, None


def delete_profile_image(key: str) -> bool:
    if not key:
        return False
    try:
        s3_client.delete_object(Bucket=S3_BUCKET, Key=key)
        return True
    except ClientError as e:
        print(f"[S3] Error deleting: {e}")
        return False


def generate_presigned_url(key: str, expires_in: int = 3600) -> str | None:
    """Genera URL temporal si el bucket es privado."""
    if not key:
        return None
    try:
        return s3_client.generate_presigned_url(
            "get_object",
            Params={"Bucket": S3_BUCKET, "Key": key},
            ExpiresIn=expires_in,
        )
    except ClientError as e:
        print(f"[S3] Error presigning: {e}")
        return None
