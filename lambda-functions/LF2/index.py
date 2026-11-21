import json
import logging
import os
import re
import uuid
from urllib.parse import quote
from urllib.request import Request, urlopen
from urllib.error import HTTPError

import boto3
from botocore.auth import SigV4Auth
from botocore.awsrequest import AWSRequest

log = logging.getLogger()
log.setLevel(logging.INFO)
region = os.environ.get('AWS_REGION', 'us-east-1')
lex = boto3.client('lexv2-runtime')
s3 = boto3.client('s3')
STOPWORDS = set('show me please find search for photo photos picture pictures image images '
                'with containing include including in on of at the a an and or to them it '
                'have has all my some from that are there where'.split())


def opensearch_request(method, path, payload):
    endpoint = os.environ['OPENSEARCH_ENDPOINT'].rstrip('/')
    if not endpoint.startswith('https://'):
        endpoint = 'https://' + endpoint
    url = endpoint + path
    data = json.dumps(payload).encode('utf-8')
    creds = boto3.Session().get_credentials().get_frozen_credentials()
    signed_request = AWSRequest(method=method, url=url, data=data,
                                headers={'Content-Type': 'application/json'})
    SigV4Auth(creds, 'es', region).add_auth(signed_request)
    request = Request(url, data=data, headers=dict(signed_request.headers), method=method)
    try:
        with urlopen(request, timeout=15) as response:
            return json.loads(response.read())
    except HTTPError as exc:
        log.error('OpenSearch %s: %s', exc.code, exc.read().decode(errors='replace'))
        raise



def lex_keywords(query):
    result = lex.recognize_text(
        botId=os.environ['LEX_BOT_ID'],
        botAliasId=os.environ['LEX_BOT_ALIAS_ID'],
        localeId=os.environ.get('LEX_LOCALE_ID', 'en_US'),
        sessionId=str(uuid.uuid4()),
        text=query
    )

    intent = result.get('sessionState', {}).get('intent', {})
    intent_name = intent.get('name')

    if intent_name == 'SearchIntent':
        slot = (intent.get('slots') or {}).get('Query') or {}
        value = (
            (slot.get('value') or {}).get('interpretedValue')
            or query
        )
    else:
        log.info(
            "Lex returned %s; using search text directly",
            intent_name
        )
        value = query

    words = re.findall(
        r"[\w'-]+",
        value.casefold(),
        flags=re.UNICODE
    )

    keywords = [
        word for word in words
        if word not in STOPWORDS and len(word) > 1
    ]

    return list(dict.fromkeys(keywords))[:12]



def search_index(keywords):
    if not keywords:
        return []
    name = quote(os.getenv('OPENSEARCH_INDEX', 'photos'), safe='')
    query = {'size': 1000, 'query': {'bool': {
        'should': [{'match': {'labels': {'query': kw, 'fuzziness': 'AUTO'}}}
                   for kw in keywords],
        'minimum_should_match': 1,
    }}}
    result = opensearch_request('POST', '/' + name + '/_search', query)
    hits = result.get('hits', {}).get('hits', [])
    photos = []
    seen = set()
    for hit in hits:
        entry = hit.get('_source', {})
        bucket, key = entry.get('bucket'), entry.get('objectKey')
        if not bucket or not key or (bucket, key) in seen:
            continue
        seen.add((bucket, key))
        url = s3.generate_presigned_url('get_object',
                    Params={'Bucket': bucket, 'Key': key}, ExpiresIn=900)
        photos.append({'url': url, 'labels': entry.get('labels', [])})
    return photos


def response(status, data):
    return {'statusCode': status, 'headers': {
        'Content-Type': 'application/json',
        'Access-Control-Allow-Origin': '*',
        'Access-Control-Allow-Methods': 'GET,OPTIONS',
        'Access-Control-Allow-Headers': 'Content-Type,x-api-key',
    }, 'body': json.dumps(data)}


def lambda_handler(event, context):
    try:
        query = (event.get('queryStringParameters') or {}).get('q', '').strip()
        if not query:
            return response(200, {'results': []})
        keywords = lex_keywords(query)
        return response(200, {'results': search_index(keywords)})
    except Exception:
        log.exception('Photo search failed')
        return response(500, {'code': 500, 'message': 'Search failed; see Lambda logs'})
