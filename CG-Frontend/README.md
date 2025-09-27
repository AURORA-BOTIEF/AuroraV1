Frontend prototype for the CrewAI course generator

Files:
- index.html - simple UI to upload outline and start a job
- app.js - client logic; expects three backend endpoints

Backend endpoints expected (configure these or host the frontend under the API domain):
- POST /presign  -> { filename } returns { url, key }
- POST /start-job -> starts Step Functions execution (calls starter_api Lambda) returns { executionArn }
- GET  /exec-status?arn=... -> optional status endpoint that returns Step Functions execution status

Deployment notes:
- You can host this static frontend in S3 + CloudFront, or serve it from a small web server that also proxies the backend endpoints.
- For testing, run `sam local start-api` and add endpoints that map to the Lambdas (starter_api and a presign Lambda).
