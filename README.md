# AI Photo Album

Natural-language photo search using S3, Lambda, Rekognition, OpenSearch, Lex V2, API Gateway, and a static website with generated API Gateway JavaScript SDK.

## Status

Both CodePipeline P1 (backend) and P2 (frontend) were deployed and successfully tested. Lambda LF1 and LF2 were synchronized from the working AWS code supplied for this assignment. P2 automatically deployed a GitHub frontend commit; a later commit `f770bf7` removed the temporary SDK download step, and both pipelines succeeded afterward.

## Repository layout

- `backend/LF1/index.py`: S3 create/delete indexing
- `backend/LF2/index.py`: Lex search with arbitrary custom labels
- `buildspec-backend.yml`: CodeBuild P1, deploys both functions
- `buildspec-frontend.yml`: CodeBuild P2, syncs frontend to S3
- `frontend/`: HTML, CSS, JavaScript, API key placeholder and complete generated `sdk/` dependencies are committed; the build generates `config.js` at deployment time
- `cloudformation/baseline.yaml`: committed CloudFormation baseline for the assignment; do not redeploy the template over your working stack without a change review

## P1 setup

Create CodePipeline using GitHub `main` as source. Build with CodeBuild and buildspec `buildspec-backend.yml`. Set environment variables:

- `INDEX_FUNCTION_NAME=photo-album-a3-index-photos`
- `SEARCH_FUNCTION_NAME=photo-album-a3-search-photos`

The CodeBuild role needs `lambda:UpdateFunctionCode`, `lambda:GetFunctionConfiguration`, and CloudWatch logging permissions. Ensure both functions use handler `index.lambda_handler`. P1 deploys *code only*, not environment variables or IAM permissions.

## P2 setup

Use the same repository `main`, with `buildspec-frontend.yml`. CodeBuild environment:

- `FRONTEND_BUCKET`: value of CloudFormation output `FrontendBucketName`
- `PHOTO_API_BASE_URL`: API Gateway stage `prod` URL
- `PHOTO_API_KEY`: load from a protected CodeBuild/Secrets Manager configuration rather than committing to GitHub

The build writes browser-visible `frontend/config.js`. API keys in public browser apps are visible to website visitors and are not an authentication mechanism; use API Gateway quotas/throttling and avoid using IAM secrets.

The CodeBuild role needs `s3:ListBucket` and `s3:PutObject`, `s3:DeleteObject`, `s3:GetObject` on the frontend bucket. P2 verifies that all generated SDK files exist in GitHub before `aws s3 sync --delete`. All SDK dependencies are now tracked in the repository. The generated `config.js` is excluded from Git history.

## Lambda configuration

Both functions use `OPENSEARCH_ENDPOINT` and `OPENSEARCH_INDEX=photos`. Search LF2 also requires `LEX_BOT_ID`, `LEX_BOT_ALIAS_ID`, `LEX_LOCALE_ID=en_US`. Ensure indexing role and OpenSearch domain policy allow `es:ESHttpDelete` for delete handling.

## acceptance tests

1. Photo upload through S3, and frontend PUT upload with `x-amz-meta-customLabels`.
2. Searches for Rekognition and custom labels.
3. S3 delete event removes the corresponding OpenSearch document.
4. P1 deployment after a backend commit.
5. P2 deployment after a frontend commit.
6. Baseline CloudFormation creates two S3 buckets, two Lambdas and API Gateway with public frontend website URL.

**Validated:** Both pipelines succeeded after commit `f770bf7` and the frontend upload/search application continued working. Additional multi-keyword, delete-event, and CloudFormation update tests should be captured before submission.
