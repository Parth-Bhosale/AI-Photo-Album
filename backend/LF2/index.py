"""Lex V2 natural-language search for indexed S3 photos.
Review against the deployed Lambda code before enabling CodePipeline.
"""
import json
import logging
import os
import re
import uuid
from urllib.error import HTTPError
from urllib.parse import quote
from urllib.request import Request, urlopen

import boto3
from botocore.auth import SigV4Auth
from botocore.awsrequest import AWSRequest

log = logging.getLogger(__name__)
log.setLevel(logging.INFO)
region = os.environ.get("AWS_REGION", "us-east-1")
lex = boto3.client("lexv2-runtime")
s3 = boto3.client("s3")
STOPWORDS = set(
    "show me please find search for photo photos picture pictures image images "
    "with containing include including in on of at the a an and or to them it "
    "have has all my some from that are there where".split()
)


def opensearch_request(method, path, payload):
    endpoint = os.environ["OPENSEARCH_ENDPOINT"].rstrip("/")
    if not endpoint.startswith("https://"):
        endpoint = "https://" + endpoint
    url = endpoint + path
    data = json.dumps(payload).encode("utf-8")
    credentials = boto3.Session().get_credentials().get_frozen_credentials()
    to_sign = AWSRequest(
        method=method, url=url, data=data, headers={"Content-Type": "application/json"}
    )
    SigV4Auth(credentials, "es", region).add_auth(to_sign)
    request = Request(url, data=data, headers=dict(to_sign.headers), method=method)
    try:
        with urlopen(request, timeout=15) as response:
            return json.loads(response.read())
    except HTTPError as error:
        log.error("OpenSearch HTTP %s: %s", error.code, error.read().decode(errors="replace"))
        raise


def lex_keywords(query):
    result = lex.recognize_text(
        botId=os.environ["LEX_BOT_ID"],
        botAliasId=os.environ["LEX_BOT_ALIAS_ID"],
        localeId=os.environ.get("LEX_LOCALE_ID", "en_US"),
        sessionId=str(uuid.uuid4()),
        text=query
    )
    intent = result.get("sessionState", {}).get("intent", {})
    if intent.get("name") == "SearchIntent":
        slot = (intent.get("slots") or {}).get("Query") or {}
        value = (slot.get("value") or {}).get("interpretedValue") or query
    else:
        log.info("Lex returned %s; using search text directly", intent.get("name"))
        value = query
    tokens = re.findall(r"[\w'-]+", value.casefold(), flags=re.UNICODE)
    return list(dict.fromkeys(
        token for token in tokens if token not in STOPWORDS and len(token) > 1
    ))[:12]


def search_index(keywords):
    if not keywords:
        return []
    index_name = quote(os.getenv("OPENSEARCH_INDEX", "photos"), safe="")
    query = {
        "size": 1000,
        "query": {
            "bool": {
                "should": [{"match": {"labels": {"query": word, "fuzziness": "AUTO"}}}
                           for word in keywords],
                "minimum_should_match": 1
            }
        }
    }
    data = opensearch_request("POST", f"/{index_name}/_search", query)
    seen, photos = set(), []
    for hit in data.get("hits", {}).get("hits", []):
        doc = hit.get("_source", {})
        bucket, key = doc.get("bucket"), doc.get("objectKey")
        if not bucket or not key or (bucket, key) in seen:
            continue
        seen.add((bucket, key))
        url = s3.generate_presigned_url(
            "get_object", Params={"Bucket": bucket, "Key": key}, ExpiresIn=900
        )
        photos.append({"url": url, "labels": doc.get("labels", [])})
    return photos


def response(code, data):
    return {
        "statusCode": code,
        "headers": {
            "Content-Type": "application/json",
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Methods": "GET,OPTIONS",
            "Access-Control-Allow-Headers": "Content-Type,x-api-key"
        },
        "body": json.dumps(data)
    }


def lambda_handler(event, context):
    try:
        q = (event.get("queryStringParameters") or {}).get("q", "").strip()
        if not q:
            return response(200, {"results": []})
        return response(200, {"results": search_index(lex_keywords(q))})
    except Exception:
        log.exception("Search failed")
        return response(500, {"code": 500, "message": "Search failed; see Lambda logs"})
