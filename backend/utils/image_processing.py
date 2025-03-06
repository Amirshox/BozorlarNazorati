import base64
import io
import logging
import os
import uuid
from typing import Optional, Tuple

import cv2
import numpy as np
import PIL
import requests
import sentry_sdk
from celery.exceptions import TaskError
from fastapi import HTTPException, status
from PIL import ExifTags, Image, UnidentifiedImageError

from utils.log import timeit

MINIO_PROTOCOL = os.getenv("MINIO_PROTOCOL")
MINIO_HOST = os.getenv("MINIO_HOST2")
MINIO_HOST3 = os.getenv("MINIO_HOST3")

logger = logging.getLogger(__name__)


def pre_process_image(image: bytes, image_list: list):
    try:
        image = Image.open(image)
    except UnidentifiedImageError as e:
        sentry_sdk.capture_exception(e)
        raise TaskError("Bad image") from e

    image_list.append(image)
    img_array_raw = np.array(image)
    img_array = cv2.resize(img_array_raw, (299, 299))
    img_array = img_array[..., :3]
    img_array = np.expand_dims(img_array, axis=0)
    img_array = img_array / 255.0
    img_array = img_array.astype(np.float32)

    return img_array, img_array_raw


def correct_image_orientation(image):
    """
    Corrects the orientation of an image using its EXIF data.

    Parameters:
        image (PIL.Image): The input PIL.Image object.

    Returns:
        PIL.Image: The corrected PIL.Image object.
    """
    try:
        exif = image._getexif()  # Getting the EXIF data
        if exif is not None:
            for tag, value in exif.items():
                decoded = ExifTags.TAGS.get(tag, tag)
                if decoded == "Orientation":
                    if value == 3:
                        image = image.rotate(180, expand=True)
                    elif value == 6:
                        image = image.rotate(270, expand=True)
                    elif value == 8:
                        image = image.rotate(90, expand=True)
                    break
    except AttributeError:
        pass  # In case the image doesn't have EXIF data
    return image


def compress_image_to_target_size_pil(image, target_size_kb, tolerance=5):
    """
    Compress an image represented as a PIL.Image object to the target size.

    Parameters:
        image (PIL.Image): The input PIL.Image object to be compressed.
        target_size_kb (int): The target size in kilobytes.
        tolerance (int): The tolerance in kilobytes for the target size.

    Returns:
        PIL.Image: The compressed PIL.Image object.
    """

    img_format = image.format if image.format is not None else "JPEG"

    # Convert size to bytes
    target_size_bytes = target_size_kb * 1024

    quality = 100

    # Try reducing the quality to reach the target size
    while quality > 10:
        # Create a bytes buffer to save the image
        img_bytes = io.BytesIO()
        # Save image to the buffer with the current quality
        image.save(img_bytes, format=img_format, quality=quality)
        size_in_bytes = img_bytes.tell()

        # Check if the size is within the target range
        if size_in_bytes <= target_size_bytes + tolerance * 1024:
            # Load the image from the buffer
            img_bytes.seek(0)
            return Image.open(img_bytes)

        # Decrease the quality for the next loop
        quality -= 10

    # If low quality still exceeds the target size, return the image at the lowest quality tested
    img_bytes = io.BytesIO()
    image.save(img_bytes, format=img_format, quality=quality)
    img_bytes.seek(0)
    return Image.open(img_bytes)


@timeit
def image_url_to_base64(image_url: str = None) -> str | None:
    try:
        response = requests.get(image_url)
        response.raise_for_status()
        image_data = io.BytesIO(response.content)
        base64_image = base64.b64encode(image_data.read()).decode("utf-8")
        return base64_image
    except Exception:
        return None


@timeit
def get_image_from_url(url: str) -> bytes:
    try:
        response = requests.get(url)
        response.raise_for_status()
        image = response.content
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)) from e
    return image


def is_base64_image(data: str) -> bool:
    try:
        # Strip out any leading data URL scheme if present
        if data.startswith("data:image"):
            data = data.split(";base64,")[-1]

        # Decode the Base64 string
        image_data = base64.b64decode(data)

        # Use Pillow to open the image object
        image = PIL.Image.open(io.BytesIO(image_data))
        image.verify()  # Verifies that the object is an image

        return True
    except Exception as e:
        print(e)
        return False


def is_image_url(data: str) -> bool:
    if data and isinstance(data, str):
        return data.startswith("http://") or data.startswith("https://")
    return False


def make_minio_url_from_image(
    minio_client,
    image: bytes,
    bucket_name: str,
    pinfl: Optional[str] = None,
    is_check_hd: bool = True,
    is_check_size: bool = True,
    minio_host: Optional[str] = MINIO_HOST,
) -> str:
    try:
        pil_image = Image.open(io.BytesIO(image))
        pil_image = correct_image_orientation(pil_image)
        if is_check_hd:  # noqa
            if pil_image.width < 480 or pil_image.height < 640:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Image is not HD")

        # check if image size is less than 50kb then return bad request
        # if len(image) < 50_000:
        #     raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Image size is less than 50kb")
        if is_check_size:  # noqa
            if len(image) > 500_000:
                pil_image = compress_image_to_target_size_pil(pil_image, 500)

        img_bytes = io.BytesIO()
        pil_image.save(img_bytes, format="JPEG", quality=98)
        img_bytes.seek(0)
        file_name = f"{pinfl}/{uuid.uuid4()}.jpeg" if pinfl else f"{uuid.uuid4()}.jpeg"
        minio_client.put_object(bucket_name, str(file_name), img_bytes, len(img_bytes.getvalue()))

        photo_url = f"{MINIO_PROTOCOL}://{minio_host}/{bucket_name}/{file_name}"
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Reformat photo failed: {e}") from e
    return photo_url


def extract_minio_url(url: str) -> Tuple[str, str]:
    url_parts = url.split("/")
    bucket_name = url_parts[3]
    object_name = "/".join(url_parts[4:])
    return bucket_name, object_name


def check_image_HD(image_url: str) -> bool:
    image = get_image_from_query(image_url)
    pil_image = Image.open(io.BytesIO(image))
    pil_image = correct_image_orientation(pil_image)
    return pil_image.width >= 480 and pil_image.height >= 640


def get_image_from_query(data: str) -> bytes:
    if is_image_url(data):
        image = get_image_from_url(data)
    elif is_base64_image(data):
        image = base64.b64decode(data)
    else:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid photo")
    return image


def get_main_error_text(response: requests.Response) -> str:
    if response.status_code == 404:
        return "Device not found"
    elif response.status_code == 408:
        return "Timed out waiting for response"
    elif response.status_code == 400:
        try:
            description = response.json()["detail"]["description"]
            return description
        except Exception as e:
            print(e)
            return response.text
    else:
        return response.text


def get_error_text_from_code(error_code: int) -> str:
    error_descriptions = {
        0: "normal",
        # libcurl error codes (1-100) reference omitted for brevity
        -101: "The file name ID is the same",
        -102: "Libraries full",
        -103: "Adding a timeout",
        -104: "Parameter error",
        -105: "File is too large",
        -106: "Insufficient storage space",
        -107: "File open failed",
        -108: "No database",
        -109: "Image reading failed",
        -110: "Database file is damaged",
        -111: "Picture quality is poor",
        -112: "Image size is wrong, width and height cannot be odd numbers",
        -113: "Face detection failed (no face detected or multiple faces detected)",
        -114: "Picture format error",
        -115: "Face area error",
        -116: "Algorithm creates a handle error",
        -117: "Device is busy",
        -118: "File writing failed",
        -119: "Deletion failed (the corresponding ID was not found to delete)",
        -120: "Failed to allocate memory",
        -121: "The number of people in the list is NULL",
        -122: "Valid time error",
        -123: "Failed to write characteristic value",
        201: "Parameter does not exist",
        202: "User id already exists",
        203: "User id does not exist",
        204: "Device is busy (Duplicate)",
        205: "The parameter is invalid",
        206: "Administrator password error",
        207: "Picture name does not meet the rules",
        208: "No new information",
        209: "Device not supported",
        210: "The file format is not supported",
        299: "No reaction",
    }

    # Return the corresponding error description or a default message if not found
    if error_code in error_descriptions:
        return error_descriptions[error_code]
    elif 1 <= error_code <= 100:
        return "libcurl error"
    else:
        return "Unknown error"
