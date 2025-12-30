from fastapi import APIRouter, HTTPException
from fastapi.responses import Response
from ..services.gcs_service import download_image, get_bucket_name
import logging

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get('/gcs/{blob_name:path}')
async def get_gcs_image(blob_name: str) -> Response:
    """
    Proxy endpoint to serve images from Google Cloud Storage.
    Uses backend gcloud credentials to fetch private images from GCS.
    
    Args:
        blob_name: The name of the blob in the GCS bucket
    
    Returns:
        Image response with appropriate content type
    """
    try:
        # Download image from GCS using backend credentials
        image_bytes = await download_image(blob_name)
        
        # Determine content type from file extension
        content_type = 'image/png'  # default
        if blob_name.lower().endswith('.jpg') or blob_name.lower().endswith('.jpeg'):
            content_type = 'image/jpeg'
        elif blob_name.lower().endswith('.png'):
            content_type = 'image/png'
        elif blob_name.lower().endswith('.gif'):
            content_type = 'image/gif'
        elif blob_name.lower().endswith('.webp'):
            content_type = 'image/webp'
        
        logger.info(f"[images] Serving GCS image: {blob_name}")
        
        return Response(
            content=image_bytes,
            media_type=content_type,
            headers={
                "Cache-Control": "public, max-age=3600"  # Cache for 1 hour
            }
        )
    except FileNotFoundError:
        logger.warning(f"[images] Image not found in GCS: {blob_name}")
        raise HTTPException(status_code=404, detail="Image not found")
    except Exception as e:
        logger.error(f"[images] Error serving GCS image {blob_name}: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to retrieve image")




