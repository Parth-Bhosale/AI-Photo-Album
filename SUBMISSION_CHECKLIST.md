# Assignment 3 — Submission and verification checklist

## Functional application (verified during setup)
- [x] CloudFormation baseline stack `photo-album-a3` reaches CREATE_COMPLETE.
- [x] Photo upload triggers LF1, Rekognition returns image labels, OpenSearch `photos` index stores the document.
- [x] Lex V2 recognizes SearchIntent; LF2 also handles arbitrary custom labels when Lex returns FallbackIntent.
- [x] GET /search returns matching photo URLs from OpenSearch.
- [x] PUT /photos preserves `x-amz-meta-customLabels` in S3.
- [x] S3-hosted frontend searches and uploads with the API Gateway-generated SDK.
- [x] Custom label searches `Sam` and `SDKTest` return photos.

## CI/CD (verified during setup)
- [x] Backend CodePipeline P1 Source + CodeBuild succeed, and searches/uploads pass after deployment.
- [x] Frontend CodePipeline P2 Source + CodeBuild succeed, and all four post-P2 frontend tests pass.
- [x] GitHub commit `db0e4f7` changes the live S3 website footer to include **GitHub deployment check**.
- [ ] Confirm the footer commit appeared as an automatically triggered execution in P2 *without manually releasing a change*, if this has not already been checked.

## Repository completeness
- [x] `backend/LF1/index.py` and `backend/LF2/index.py` synchronized from working Lambda code.
- [x] `buildspec-backend.yml`, `buildspec-frontend.yml`, `cloudformation/baseline.yaml`.
- [x] Frontend `index.html`, `style.css`, `app.js`, `config.example.js`.
- [ ] Add **all generated files** under `frontend/sdk/` from the provided SDK-integrated frontend ZIP. Do not commit `frontend/config.js`.
- [ ] Once SDK is committed, remove the S3 SDK bootstrap fallback from `buildspec-frontend.yml` and deploy purely from GitHub.

## Acceptance criteria before submission
- [ ] Search an image by one of its automatically detected Rekognition labels.
- [ ] Search using two keywords and confirm expected photo matches.
- [ ] Search by each of two custom labels on the same photo.
- [ ] Delete an S3 image and verify its result disappears from OpenSearch; retain an image for the demo.
- [ ] Show a new commit automatically deploying backend and frontend code.
- [ ] Show CloudFormation stack resources, outputs including the public website URL, and a working website.

## Evidence to capture
1. CloudFormation CREATE_COMPLETE, Resources and Outputs.
2. `photos` OpenSearch index with document count / field mappings.
3. S3 object Properties with custom label metadata.
4. LF1 and LF2 successful test logs or Lambda responses.
5. Lex SearchIntent test, frontend search and frontend upload.
6. P1 and P2 successful Source/Build executions, including revision SHA.
7. GitHub repository tree and README, plus the public S3 website URL.

## Notes
- Do not commit real API keys, IAM access keys or other secrets to GitHub. Browser API Gateway usage-plan keys are *not* authentication credentials; configure appropriate quotas and throttling.
- The CloudFormation template was built as a baseline and is not a complete reproduction of the manually configured Lex, OpenSearch or CodePipeline resources.
- The generated SDK currently comes from the already-deployed S3 website in CodeBuild when the `frontend/sdk/` directory is missing; make the repo self-contained before submission.
- Stop or delete billable AWS resources when no longer needed, after documenting the assignment.
