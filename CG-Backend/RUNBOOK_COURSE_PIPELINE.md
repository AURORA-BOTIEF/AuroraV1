# Course Generator pipeline — operations runbook

## CloudWatch alarms (deployed with the stack)

- **CourseGeneratorExecutionsFailedAlarm** — Step Functions metric `ExecutionsFailed` on the Course Generator state machine.
- **CourseGeneratorExecutionsTimedOutAlarm** — metric `ExecutionsTimedOut`.

Neither alarm has `AlarmActions` in the template. To get email or Slack, attach an **SNS topic** (or use the console) and add the topic ARN to the alarm’s alarm actions after deploy.

## When a run fails: redrive vs new execution

### Redrive (same execution ARN)

Use when the failure was **transient** (throttling, short outage) and you want Step Functions to **replay failed Map items / branches** without changing input.

- AWS CLI: [StartExecution — redrive](https://docs.aws.amazon.com/step-functions/latest/apireference/API_RedriveExecution.html) / console **Redrive** on the execution.

Prefer redrive when CloudWatch shows **retryable** errors and you have **not** changed course data or S3 artifacts in a way that requires a clean slate.

### New execution with partial regeneration

Use when you need to **regenerate only some lessons or labs** or fix input and continue.

Payload fields (see starter API / state machine input):

- **`lesson_to_generate`** — limit theory generation to specific lesson id(s) when supported by your starter path.
- **`lab_ids_to_regenerate`** — regenerate only listed lab ids for the labs phase.

Start a **new** execution with the same `course_id` / identifiers as needed, plus these fields, so you avoid redoing the whole course.

## Lambda env (resilience)

| Variable | Functions | Purpose |
|----------|-----------|---------|
| `BEDROCK_APP_MAX_ATTEMPTS` | StrandsContentGen, StrandsLabWriter, StrandsVisualPlanner | App-level retries with backoff+jitter on transient Bedrock errors. |
| `LESSON_CONTEXT_MAX_CHARS` | StrandsLabWriter | Caps lesson markdown in the lab prompt (default 18000) to reduce `Sandbox.Timedout` risk. |
| `LAB_SKIP_IF_EXISTS` | StrandsLabWriter | If `1` / `true` / `yes`, skip Bedrock when the lab guide object already exists in S3 (idempotent partial reruns). |

## Starter API and SES email

If the request body includes **`user_email`**, it overrides the default notification address so failures are less likely to reference unverified placeholders. Ensure production clients send a **verified** SES identity when notifications matter.

## Step Functions retries

Critical Lambda tasks use extended `Retry` (including `Sandbox.Timedout`, `Lambda.Unknown`, throttling) with longer intervals, `BackoffRate`, `MaxAttempts`, and `JitterStrategy: FULL` where the API accepts it. After deploy, if CloudFormation rejects `JitterStrategy`, remove that field from `current_state_machine.json` and redeploy.
