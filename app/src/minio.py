from typing import BinaryIO
from minio import Minio
from app.src.constants import MINIO_HOST, MINIO_PASSWORD, MINIO_PORT, MINIO_USERNAME

# MinIO client instance
client: Minio = Minio(
    endpoint=f"{MINIO_HOST}:{MINIO_PORT}",
    access_key=MINIO_USERNAME,
    secret_key=MINIO_PASSWORD,
    secure=False,
)


def createBucket(bucketName: str) -> None:
    """
    Create a new bucket in MinIO.

    Args:
        bucketName (str): The name of the bucket to create.

    Raises:
        S3Error: If the bucket cannot be created (e.g., already exists).
    """
    client.make_bucket(bucketName)


def deleteBucket(bucketName: str) -> None:
    """
    Delete a bucket and all its contents from MinIO.

    Args:
        bucketName (str): The name of the bucket to delete.

    Note:
        This will remove all objects inside the bucket before deleting it.

    Raises:
        S3Error: If the bucket or objects cannot be deleted.
    """
    objectsInBucket = client.list_objects(bucketName)
    for object in objectsInBucket:
        client.remove_object(bucketName, object.object_name)
    client.remove_bucket(bucketName)


def downloadFile(bucketName: str, objectID: str) -> bytes:
    """
    Download a file from MinIO.

    Args:
        bucketName (str): The name of the bucket containing the object.
        objectID (str): The unique identifier (key) of the object.

    Returns:
        bytes: The raw file data.

    Raises:
        S3Error: If the file cannot be retrieved.
    """
    return client.get_object(bucketName, objectID).data


def deleteFile(bucketName: str, objectID: str) -> None:
    """
    Delete a file from MinIO.

    Args:
        bucketName (str): The name of the bucket containing the object.
        objectID (str): The unique identifier (key) of the object.

    Raises:
        S3Error: If the file cannot be deleted.
    """
    client.remove_object(bucketName, objectID)


def uploadFile(bucketName: str, objectID: str, size: int, fileObject: BinaryIO) -> None:
    """
    Upload a file to MinIO.

    Args:
        bucketName (str): The name of the bucket where the file will be stored.
        objectID (str): The unique identifier (key) for the object in MinIO.
        size (int): The size of the file in bytes.
        fileObject (BinaryIO): A file-like object containing the data to upload.

    Raises:
        S3Error: If the file cannot be uploaded.
    """
    client.put_object(bucketName, objectID, fileObject, size)
