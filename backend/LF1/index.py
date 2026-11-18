import hashlib
import json
import logging
import os
from datetime import timezone
from urllib.parse import quote, unquote_plus
from urllib.request import Request, urlopen
from urllib.error import HTTPError

import boto3
from botocore.auth import SigV4Auth
from botocore.awsrequest import AWSRequest

log = logging.getLogger()
log.setLevel(logging.INFO)
region = os.environ.get('AWS_REGION', 'us-east-1')
s3 = boto3.client('s3')
rekognition = boto3.client('rekognition')


def opensearch_request(method, path, payload=None):
    endpoint = os.environ['OPENSEARCH_ENDPOINT'].rstrip('/')
    if not endpoint.startswith('https://'):
        endpoint = 'https://' + endpoint
    url = endpoint + path
    data = None if payload is None else json.dumps(payload).encode('utf-8')
    headers = {'Content-Type': 'application/json'}
    creds = boto3.Session().get_credentials().get_frozen_credentials()
    signed_request = AWSRequest(method=method, url=url, data=data, headers=headers)
    SigV4Auth(creds, 'es', region).add_auth(signed_request)
    request = Request(url, data=data, headers=dict(signed_request.headers), method=method)
    try:
        with urlopen(request, timeout=15) as response:
            raw = response.read()
            return json.loads(raw) if raw else {}
    except HTTPError as exc:
        detail = exc.read().decode('utf-8', errors='replace')
        log.error('OpenSearch HTTP %s: %s', exc.code, detail)
        raise


def handle_image(bucket, key):
    metadata = s3.head_object(Bucket=bucket, Key=key)
    # boto3 returns user-defined S3 metadata with lowercase keys.
    supplied = metadata.get('Metadata', {}).get('customlabels', '')
    custom_labels = [item.strip() for item in supplied.split(',') if item.strip()]

    detected = rekognition.detect_labels(
        Image={'S3Object': {'Bucket': bucket, 'Name': key}},
        MaxLabels=100,
        MinConfidence=70,
    )
    automatic_labels = [entry['Name'] for entry in detected.get('Labels', [])]
    labels = list(dict((value.casefold(), value) for value in
                       custom_labels + automatic_labels).values())
    index_name = os.getenv('OPENSEARCH_INDEX', 'photos')
    document = {
        'objectKey': key,
        'bucket': bucket,
        'createdTimestamp': metadata['LastModified'].astimezone(timezone.utc).isoformat(),
        'labels': labels,
    }
    doc_id = hashlib.sha256((bucket + '/' + key).encode()).hexdigest()
    result = opensearch_request('PUT',
        '/' + quote(index_name, safe='') + '/_doc/' + doc_id,
        document)
    log.info('Indexed %s/%s; %d labels; result=%s', bucket, key,
             len(labels), result.get('result'))
    return document



def lambda_handler(event, context):
    indexed = []
    deleted = []

    for record in event.get("Records", []):
        event_name = record.get("eventName", "")
        bucket = record["s3"]["bucket"]["name"]
        key = unquote_plus(record["s3"]["object"]["key"])

        if event_name.startswith("ObjectCreated:"):
            indexed.append(handle_image(bucket, key))

        elif event_name.startswith("ObjectRemoved:"):
            doc_id = hashlib.sha256(
                (bucket + "/" + key).encode()
            ).hexdigest()

            index_name = os.getenv(
                "OPENSEARCH_INDEX", "photos"
            )

            result = opensearch_request(
                "DELETE",
                "/" + quote(index_name, safe="")
                + "/_doc/" + doc_id
            )

            deleted.append({
                "objectKey": key,
                "result": result.get("result")
            })

    return {
        "statusCode": 200,
        "body": json.dumps({
            "indexed": indexed,
            "deleted": deleted
        })
    }
