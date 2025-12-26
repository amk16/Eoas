import os
import logging
import asyncio
from typing import Optional
from concurrent.futures import ThreadPoolExecutor
from dotenv import load_dotenv
from google.cloud import storage

# Ensure .env is loaded
load_dotenv()

logger = logging.getLogger(__name__)


def _get_project_id_from_gcloud() -> Optional[str]:
    """
    Try to get the project ID from gcloud config.
    Returns None if not found.
    """
    try:
        import subprocess
        result = subprocess.run(
            ['gcloud', 'config', 'get-value', 'project'],
            capture_output=True,
            text=True,
            timeout=5
        )
        if result.returncode == 0 and result.stdout.strip():
            return result.stdout.strip()
    except Exception:
        pass
    return None


def get_gcs_client() -> storage.Client:
    """
    Initialize and return a GCS client using Application Default Credentials.
    Uses gcloud CLI credentials automatically.
    """
    try:
        # Get project ID from environment variable, gcloud config, or use None to auto-detect
        project_id = os.getenv('GOOGLE_CLOUD_PROJECT')
        if not project_id:
            project_id = _get_project_id_from_gcloud()
        
        if project_id:
            client = storage.Client(project=project_id)
            logger.info(f"[gcs_service] GCS client initialized successfully using ADC with project: {project_id}")
        else:
            client = storage.Client()
            logger.info("[gcs_service] GCS client initialized successfully using ADC (auto-detected project)")
        return client
    except Exception as e:
        logger.error(f"[gcs_service] Failed to initialize GCS client: {str(e)}")
        raise Exception(f"Failed to initialize GCS client: {str(e)}")


def get_bucket_name() -> str:
    """
    Get the GCS bucket name from environment variables.
    """
    bucket_name = os.getenv('GOOGLE_CLOUD_STORAGE_BUCKET')
    if not bucket_name:
        raise ValueError("GOOGLE_CLOUD_STORAGE_BUCKET not configured in environment variables")
    return bucket_name


def _upload_image_sync(image_data: bytes, filename: str, bucket_name: str, content_type: str) -> str:
    """
    Synchronous helper function to upload an image to GCS (private upload).
    """
    client = get_gcs_client()
    bucket = client.bucket(bucket_name)
    blob = bucket.blob(filename)
    blob.upload_from_string(image_data, content_type=content_type)
    return filename


async def upload_image(image_data: bytes, filename: str, content_type: str = 'image/png') -> str:
    """
    Upload an image to Google Cloud Storage and return the blob name.
    
    Args:
        image_data: Image file bytes
        filename: Desired filename for the uploaded image
        content_type: MIME type of the image (default: 'image/png')
    
    Returns:
        The blob name (filename) in the bucket
    """
    try:
        bucket_name = get_bucket_name()
        logger.info(f"[gcs_service] Uploading image to bucket: {bucket_name}, filename: {filename}")
        
        # Run synchronous GCS operation in thread pool
        loop = asyncio.get_event_loop()
        with ThreadPoolExecutor() as executor:
            blob_name = await loop.run_in_executor(
                executor,
                _upload_image_sync,
                image_data,
                filename,
                bucket_name,
                content_type
            )
        
        logger.info(f"[gcs_service] Successfully uploaded image: {filename}")
        return blob_name
        
    except Exception as e:
        logger.error(f"[gcs_service] Error uploading image: {str(e)}")
        raise Exception(f"Failed to upload image to GCS: {str(e)}")


def get_backend_image_url(blob_name: str) -> str:
    """
    Generate a backend proxy URL for accessing a GCS image.
    
    Args:
        blob_name: The name of the blob in the bucket
    
    Returns:
        A backend API URL that will proxy the image from GCS
    """
    # Return backend API endpoint URL that will proxy the image
    return f"/api/images/gcs/{blob_name}"


def _download_image_sync(blob_name: str, bucket_name: str) -> bytes:
    """
    Synchronous helper function to download an image from GCS.
    """
    client = get_gcs_client()
    bucket = client.bucket(bucket_name)
    blob = bucket.blob(blob_name)
    if not blob.exists():
        raise FileNotFoundError(f"Blob {blob_name} does not exist in bucket {bucket_name}")
    return blob.download_as_bytes()


async def upload_image_and_get_url(image_data: bytes, filename: str, content_type: str = 'image/png') -> str:
    """
    Upload an image to GCS (private) and return a backend proxy URL in one operation.
    
    Args:
        image_data: Image file bytes
        filename: Desired filename for the uploaded image
        content_type: MIME type of the image (default: 'image/png')
    
    Returns:
        A backend API URL that will proxy the image from GCS
    """
    blob_name = await upload_image(image_data, filename, content_type)
    backend_url = get_backend_image_url(blob_name)
    logger.info(f"[gcs_service] Generated backend proxy URL for: {blob_name}")
    return backend_url


async def download_image(blob_name: str) -> bytes:
    """
    Download an image from GCS.
    
    Args:
        blob_name: The name of the blob in the bucket
    
    Returns:
        The image bytes
    """
    try:
        bucket_name = get_bucket_name()
        logger.info(f"[gcs_service] Downloading image from bucket: {bucket_name}, filename: {blob_name}")
        
        # Run synchronous GCS operation in thread pool
        loop = asyncio.get_event_loop()
        with ThreadPoolExecutor() as executor:
            image_bytes = await loop.run_in_executor(
                executor,
                _download_image_sync,
                blob_name,
                bucket_name
            )
        
        logger.info(f"[gcs_service] Successfully downloaded image: {blob_name}")
        return image_bytes
        
    except Exception as e:
        logger.error(f"[gcs_service] Error downloading image: {str(e)}")
        raise Exception(f"Failed to download image from GCS: {str(e)}")

