from minio import Minio

from app.src.constants import MINIO_HOST, MINIO_PASSWORD, MINIO_PORT, MINIO_USERNAME

client: Minio = Minio(
    endpoint=f"{MINIO_HOST}:{MINIO_PORT}",
    access_key=MINIO_USERNAME,
    secret_key=MINIO_PASSWORD,
    secure=False,
)


def createBucket(bucketName: str):
    client.make_bucket(bucketName)


def deleteBucket(bucketName: str):
    objectsInBucket = client.list_objects(bucketName)
    for object in objectsInBucket:
        client.remove_object(bucketName, object.object_name)
    client.remove_bucket(bucketName)


def downloadFile(bucketName: str, objectID: str):
    return client.get_object(bucketName, objectID).data


def deleteFile(bucketName: str, objectID: str):
    client.remove_object(bucketName, objectID)


def uploadFile(bucketName: str, objectID: str, size: int, fileObject):
    client.put_object(bucketName, objectID, fileObject, size)
