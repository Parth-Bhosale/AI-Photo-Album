"""Photo indexing from S3 create/delete events.
Review against the deployed Lambda code before enabling CodePipeline.
"""
import hashlib
import json
import logging
import os
from datetime import timezone
from urllib.error import HTTPError
from urllib.parse import quote, unquote_plus
from urllib.request import Request, urlopen

import boto3
from botocore.auth import SigV4Auth
from botocore.awsrequest import AWSRequest

log = logging.getLogger(__name__)
log.setLevel(logging.INFO)
region = os.environ.get("AWS_REGION", "us-east-1")
s3 = boto3.client("s3")
rekognition = boto3.client("rekognition")


def opensearch_request(method, path, payload=None):
    endpoint = os.environ["OPENSEARCH_ENDPOINT"].rstrip("/")
    if not endpoint.startswith("https://"):
        endpoint = "https://" + endpoint
    url = endpoint + path
    data = None if payload is None else json.dumps(payload).encode("utf-8")
    headers = {"Content-Type": "application/json"}
    credentials = boto3.Session().get_credentials().get_frozen_credentials()
    request_to_sign = AWSRequest(method=method, url=url, data=data, headers=headers)
    SigV4Auth(credentials, "es", region).add_auth(request_to_sign)
    request = Request(url, data=data, headers=dict(request_to_sign.headers), method=method)
    try:
        with urlopen(request, timeout=15) as response:
            body = response.read()
            return json.loads(body) if body else {}
    except HTTPError as error:
        log.error("OpenSearch HTTP %s: %s", error.code, error.read().decode(errors="replace"))
        raise


def document_id(bucket, key):
    return hashlib.sha256((bucket + "/" + key).encode("utf-8")).hexdigest()


def index_photo(bucket, key):
    metadata = s3.head_object(Bucket=bucket, Key=key)
    labels_field = metadata.get("Metadata", {}).get("customlabels", "")
    custom_labels = [label.strip() for label in labels_field.split(",") if label.strip()]
    detection = rekognition.detect_labels(
        Image={"S3Object": {"Bucket": bucket, "Name": key}},
        MaxLabels=100,
        MinConfidence=70
    )
    automatic_labels = [item["Name"] for item in detection.get("Labels", [])]
    labels = list(dict((v.casefold(), v) for v in custom_labels + automatic_labels).values())
    document = {
        "objectKey": key,
        "bucket": bucket,
        "createdTimestamp": metadata["LastModified"].astimezone(timezone.utc).isoformat(),
        "labels": labels
    }
    index_name = quote(os.getenv("OPENSEARCH_INDEX", "photos"), safe="")
    result = opensearch_request("PUT", f"/{index_name}/_doc/{document_id(bucket, key)}", document)
    log.info("Indexed %s/%s; %s labels; %s", bucket, key, len(labels), result.get("result"))
    return document


def remove_photo(bucket, key):
    index_name = quote(os.getenv("OPENSEARCH_INDEX", "photos"), safe="")
    path = f"/{index_name}/_doc/{document_id(bucket, key)}"
    try:
        result = opensearch_request("DELETE", path)
        log.info("Removed indexed photo %s/%s: %s", bucket, key, result.get("result"))
        return {"objectKey": key, "result": result.get("result")}
    except HTTPError as error:
        if error.code == 404:
            return {"objectKey": key, "result": "not_found"}
        raise


def lambda_handler(event, context):
    indexed, deleted = [], []
    for record in event.get("Records", []):
        event_name = record.get("eventName", "")
        bucket = record["s3"]["bucket"]["name"]
        key = unquote_plus(record["s3"]["object"]["key"])
        if event_name.startswith("ObjectCreated:"):
            indexed.append(index_photo(bucket, key))
        elif event_name.startswith("ObjectRemoved:"):
            deleted.append(remove_photo(bucket, key))
    return {"statusCode": 200, "body": json.dumps({"indexed": indexed, "deleted": deleted})}
