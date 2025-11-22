# PPT Batch Orchestration Architecture

## System Overview

```
┌────────────────────────────────────────────────────────────────────────────────┐
│                         PPT BATCH ORCHESTRATION SYSTEM                          │
├────────────────────────────────────────────────────────────────────────────────┤
│                                                                                  │
│  ┌────────────────────────────────────────────────────────────────────────┐   │
│  │  USER REQUEST                                                          │   │
│  │  {                                                                     │   │
│  │    "course_bucket": "crewai-course-artifacts",                        │   │
│  │    "project_folder": "251031-databricks-ciencia-datos",              │   │
│  │    "auto_combine": true                                              │   │
│  │  }                                                                     │   │
│  └───────────────────────────┬────────────────────────────────────────────┘   │
│                              │                                                  │
│                              ▼                                                  │
│  ┌────────────────────────────────────────────────────────────────────────┐   │
│  │  STEP 1: PPT BATCH ORCHESTRATOR LAMBDA                                │   │
│  │  ─────────────────────────────────────────────────────────────────────│   │
│  │  • Load book from S3: s3://bucket/folder/book/*.json                 │   │
│  │  • Count total lessons: 16                                            │   │
│  │  • Calculate batches:                                                 │   │
│  │    - Batch 0: Lessons 1-6 (6 lessons)                                │   │
│  │    - Batch 1: Lessons 7-12 (6 lessons)                               │   │
│  │    - Batch 2: Lessons 13-16 (4 lessons)                              │   │
│  │  • Create Step Functions execution                                    │   │
│  │  • Return execution_arn                                               │   │
│  │                                                                        │   │
│  │  Lambda Config:                                                        │   │
│  │  • Runtime: Python 3.12                                               │   │
│  │  • Memory: 512 MB                                                     │   │
│  │  • Timeout: 60 seconds                                                │   │
│  └───────────────────────────┬────────────────────────────────────────────┘   │
│                              │                                                  │
│                              ▼                                                  │
│  ┌────────────────────────────────────────────────────────────────────────┐   │
│  │  STEP 2: STEP FUNCTIONS STATE MACHINE (ORCHESTRATOR)                  │   │
│  │  ─────────────────────────────────────────────────────────────────────│   │
│  │                                                                        │   │
│  │  ValidateInput → ExpandPptBatches → ProcessPptBatchesInParallel      │   │
│  │                                              │                        │   │
│  │                        ┌─────────────────────┼─────────────────────┐  │   │
│  │                        │                     │                     │  │   │
│  │                        ▼                     ▼                     ▼  │   │
│  │                    Batch Task         Batch Task            Batch Task   │   │
│  │                        0                    1                    2      │   │
│  │                   Invoke Infographic   Invoke Infographic  Invoke Inf  │   │
│  │                   Generator (1-6)      Generator (7-12)    Generator   │   │
│  │                   Timeout: 900s        Timeout: 900s        (13-16)    │   │
│  │                        │                     │                     │  │   │
│  │                        ▼                     ▼                     ▼  │   │
│  │                    PPT Batch 1         PPT Batch 2          PPT Batch 3   │
│  │                    (147 slides)        (147 slides)         (88 slides)   │
│  │                        │                     │                     │  │   │
│  │                        └─────────────────────┴─────────────────────┘  │   │
│  │                                              │                        │   │
│  │                                        Aggregated                      │   │
│  │                                        Results                         │   │
│  │                                              │                        │   │
│  │                        ┌─────────────────────▼────────────────────┐   │   │
│  │                        │ CheckIfAutoComplete                      │   │   │
│  │                        │ if auto_combine == true → Invoke Merger  │   │   │
│  │                        └─────────────────────┬────────────────────┘   │   │
│  │                                              │                        │   │
│  │                                              ▼                        │   │
│  │                        ┌────────────────────────────────────────┐    │   │
│  │                        │ PptOrchestrationComplete (Succeed)     │    │   │
│  │                        └────────────────────────────────────────┘    │   │
│  └────────────────────────────────────────────────────────────────────────┘   │
│                              │                                                  │
│                              ▼                                                  │
│  ┌────────────────────────────────────────────────────────────────────────┐   │
│  │  STEP 3: STRANDS INFOGRAPHIC GENERATOR LAMBDA (x3 parallel)           │   │
│  │  ─────────────────────────────────────────────────────────────────────│   │
│  │                                                                        │   │
│  │  BATCH 0: Lessons 1-6                                                │   │
│  │  • Load lessons from S3                                               │   │
│  │  • Call Claude Bedrock API (6 times, ~130 sec each)                  │   │
│  │  • Generate slide structures (HTML)                                   │   │
│  │  • Convert to PowerPoint (147 slides)                                │   │
│  │  • Save to S3: .../infographic_1.pptx                                │   │
│  │  • Duration: ~780 seconds                                             │   │
│  │                                                                        │   │
│  │  BATCH 1: Lessons 7-12 (PARALLEL with Batch 0)                       │   │
│  │  • Same process as Batch 0                                            │   │
│  │  • Save to S3: .../infographic_2.pptx                                │   │
│  │  • Duration: ~780 seconds                                             │   │
│  │                                                                        │   │
│  │  BATCH 2: Lessons 13-16 (SEQUENTIAL after Batch 0&1)                 │   │
│  │  • Load 4 lessons                                                     │   │
│  │  • Generate slide structures                                          │   │
│  │  • Convert to PowerPoint (88 slides)                                  │   │
│  │  • Save to S3: .../infographic_3.pptx                                │   │
│  │  • Duration: ~650 seconds                                             │   │
│  │                                                                        │   │
│  │  Lambda Config per invocation:                                         │   │
│  │  • Runtime: Python 3.12 ARM64                                         │   │
│  │  • Memory: 1024 MB                                                    │   │
│  │  • Timeout: 900 seconds (with 720s guard)                             │   │
│  │  • Layers: StrandsAgentsLayer, GeminiLayer, PPTLayer                  │   │
│  └───────────────────────────┬────────────────────────────────────────────┘   │
│                              │                                                  │
│                              ▼                                                  │
│  ┌────────────────────────────────────────────────────────────────────────┐   │
│  │  STEP 4: PPT MERGER LAMBDA                                            │   │
│  │  ─────────────────────────────────────────────────────────────────────│   │
│  │                                                                        │   │
│  │  Input: 3 PPT files from S3                                           │   │
│  │  • Load .../infographic_1.pptx (147 slides)                           │   │
│  │  • Load .../infographic_2.pptx (147 slides)                           │   │
│  │  • Load .../infographic_3.pptx (88 slides)                            │   │
│  │                                                                        │   │
│  │  Processing:                                                           │   │
│  │  • Merge into single presentation                                     │   │
│  │  • Add cover slide with metadata                                      │   │
│  │  • Update slide numbering (continuous)                                │   │
│  │  • Total: 382 slides + 1 cover = 383 slides                           │   │
│  │                                                                        │   │
│  │  Output:                                                               │   │
│  │  • Save to S3: .../complete.pptx (383 slides)                         │   │
│  │  • Return success response                                             │   │
│  │                                                                        │   │
│  │  Lambda Config:                                                        │   │
│  │  • Runtime: Python 3.12                                               │   │
│  │  • Memory: 1024 MB                                                    │   │
│  │  • Timeout: 600 seconds                                               │   │
│  │  • Layers: PPTLayer (has python-pptx)                                 │   │
│  │  • Dependencies: python-pptx, PIL, lxml                               │   │
│  └───────────────────────────┬────────────────────────────────────────────┘   │
│                              │                                                  │
│                              ▼                                                  │
│  ┌────────────────────────────────────────────────────────────────────────┐   │
│  │  FINAL OUTPUT                                                          │   │
│  │  ─────────────────────────────────────────────────────────────────────│   │
│  │                                                                        │   │
│  │  S3 Location:                                                          │   │
│  │  s3://crewai-course-artifacts/                                        │   │
│  │    251031-databricks-ciencia-datos/                                   │   │
│  │    infographics/                                                      │   │
│  │    251031-databricks-ciencia-datos-complete.pptx                      │   │
│  │                                                                        │   │
│  │  Metadata:                                                             │   │
│  │  • Total Slides: 383                                                  │   │
│  │  • Total Lessons: 16                                                  │   │
│  │  • Total Batches: 3                                                   │   │
│  │  • Generation Time: ~30 minutes                                        │   │
│  │  • Cost: ~$0.15                                                       │   │
│  │                                                                        │   │
│  │  User can now:                                                         │   │
│  │  • Download PPT from S3                                               │   │
│  │  • Share with students                                                │   │
│  │  • Edit in PowerPoint                                                 │   │
│  │  • Distribute as course materials                                     │   │
│  └────────────────────────────────────────────────────────────────────────┘   │
│                                                                                  │
└────────────────────────────────────────────────────────────────────────────────┘
```

## Timeline for 16-Lesson Course

```
Timeline (minutes)
0                 5                10                15                20                25                30

Batch 0 (1-6)     ├──────────────────────────────────────┤ (13 min)
                  [Running: 780 seconds of processing]

Batch 1 (7-12)    ├──────────────────────────────────────┤ (13 min, parallel)
                  [Running: 780 seconds of processing]

Batch 2 (13-16)                                           ├────────────────────┤ (11 min)
                                                          [Running: 650 seconds]

Merger                                                                          ├────────┤ (5 min)
                                                                                [Merging]

Download          ├─ Ready ─────────────────────────────────────────────────────┤
```

## Data Flow Diagram

```
┌──────────────────────┐
│  S3 Storage          │
│  ────────────────────│
│  • book.json         │
│  • lessons/          │
│  • infographics/     │
└──────────────────────┘
         ▲
         │ Read/Write
         │
    ┌────┴────────────────────────────────────┐
    │                                         │
    ▼                                         ▼
┌─────────────────────────┐       ┌─────────────────────────┐
│ PPT Orchestrator        │       │ Infographic Generator   │
│ Lambda                  │       │ Lambda (x3)             │
│ • Calculate batches     │──────▶│ • Generate PPT          │
│ • Start SF execution    │       │ • Save PPT to S3        │
└─────────────────────────┘       └─────────────────────────┘
         │                                │
         │                                │
         ▼                                ▼
┌─────────────────────────┐       ┌─────────────────────────┐
│ Step Functions          │       │ Claude Bedrock API      │
│ Orchestrator            │       │ • Generate content      │
│ • Coordinate batches    │       │ • Structure slides      │
│ • Parallel execution    │       │ • Call per lesson       │
│ • Route to merger       │       └─────────────────────────┘
└─────────────────────────┘
         │
         ▼
┌─────────────────────────┐
│ PPT Merger              │
│ Lambda                  │
│ • Combine PPTs          │
│ • Add metadata          │
│ • Save final output     │
└─────────────────────────┘
         │
         ▼
┌─────────────────────────┐
│ S3 Final Output         │
│ • complete.pptx         │
│ (383 slides)            │
└─────────────────────────┘
```

## Resource Allocation

```
┌────────────────────────────────────────────────────────────────┐
│ AWS RESOURCES UTILIZED                                         │
├────────────────────────────────────────────────────────────────┤
│                                                                │
│ COMPUTE (Lambda)                                              │
│ ├─ PptBatchOrchestrator      512 MB × 60 sec                  │
│ ├─ StrandsInfographicGenerator 1024 MB × 900 sec × 3          │
│ └─ StrandsPptMerger          1024 MB × 600 sec                │
│                                                                │
│ ORCHESTRATION (Step Functions)                                │
│ └─ PptBatchOrchestrator State Machine                          │
│    ├─ 1 execution                                             │
│    ├─ 5 states                                                │
│    └─ 3 lambda invocations in parallel/sequential             │
│                                                                │
│ STORAGE (S3)                                                  │
│ ├─ Input: Course book (~100 KB)                              │
│ ├─ Batch 1: ~5 MB PPT                                         │
│ ├─ Batch 2: ~5 MB PPT                                         │
│ ├─ Batch 3: ~3 MB PPT                                         │
│ └─ Output: ~13 MB final PPT                                   │
│                                                                │
│ NETWORK                                                        │
│ ├─ S3 read: ~15 MB                                            │
│ ├─ S3 write: ~28 MB                                           │
│ ├─ Lambda-to-Bedrock: ~100 API calls (~1 MB)                 │
│ └─ Total: ~144 MB (negligible cost)                           │
│                                                                │
│ API CALLS (Bedrock)                                           │
│ └─ Claude Sonnet 4.5 × 16 lessons = 16 calls (~$0.10)        │
│                                                                │
└────────────────────────────────────────────────────────────────┘
```

## Failure Points & Recovery

```
┌─────────────────────────────────────────────────────────────────┐
│ FAILURE SCENARIOS & RECOVERY                                    │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│ 1. ORCHESTRATOR FAILS                                          │
│    Cause: S3 read error                                        │
│    Recovery: Automatic retry (60s timeout is short)            │
│    Impact: User sees error immediately                         │
│                                                                 │
│ 2. BATCH TIMEOUT (Step Functions)                              │
│    Cause: Individual Lambda timeout                            │
│    Recovery: Automatic retry (configured in SM)                │
│    Impact: Batch reprocessed, may retry 2x                     │
│                                                                 │
│ 3. BATCH TIMEOUT (Lambda)                                      │
│    Cause: Infographic generation takes >900s                   │
│    Recovery: Timeout guard returns partial results at 780s     │
│    Impact: Only processes subset of batch, manual rerun needed  │
│                                                                 │
│ 4. MERGER FAILS                                                │
│    Cause: Memory error or S3 write permission                  │
│    Recovery: Automatic retry + increase memory if needed       │
│    Impact: Batch PPTs still available separately in S3         │
│                                                                 │
│ 5. S3 WRITE FAILS                                              │
│    Cause: Quota exceeded or permission denied                  │
│    Recovery: Manual check + permission audit                   │
│    Impact: PPT generated but not saved                         │
│                                                                 │
│ MONITORING POINTS                                              │
│ ├─ Step Functions console for execution status                │
│ ├─ CloudWatch logs for detailed errors                        │
│ ├─ Lambda Insights for performance metrics                     │
│ ├─ S3 for verifying output files                              │
│ └─ CloudWatch alarms for critical failures                     │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

## Cost Breakdown (16-Lesson Course)

```
┌──────────────────────────────────────────────────────────────────┐
│ COST ANALYSIS                                                    │
├──────────────────────────────────────────────────────────────────┤
│                                                                  │
│ LAMBDA COMPUTE                                          COST     │
│ ├─ PptBatchOrchestrator                                         │
│ │  512 MB × 0.001667 $/GB-sec × 60 sec = $0.0512              │
│ │                                                              │
│ ├─ StrandsInfographicGenerator × 3                             │
│ │  1024 MB × 0.0000000167 $/ms × 780,000 ms × 3 = $0.0393    │
│ │                                                              │
│ └─ StrandsPptMerger                                             │
│    1024 MB × 0.0000000167 $/ms × 300,000 ms = $0.0051         │
│                                                                  │
│ SUBTOTAL (Lambda): $0.0956 ≈ $0.10                             │
│                                                                  │
│ ────────────────────────────────────────────────────────────────│
│                                                                  │
│ STEP FUNCTIONS                                                  │
│ • 1 execution × 3 state transitions = $0.0005                  │
│ • Cost per state: $0.000025                                    │
│                                                                  │
│ SUBTOTAL (Step Functions): $0.0005 ≈ $0.001                    │
│                                                                  │
│ ────────────────────────────────────────────────────────────────│
│                                                                  │
│ BEDROCK API CALLS                                               │
│ • 16 lessons × tokens per lesson ≈ $0.05-0.10                 │
│ • Depends on content complexity                                │
│                                                                  │
│ SUBTOTAL (Bedrock): $0.05-0.10                                 │
│                                                                  │
│ ────────────────────────────────────────────────────────────────│
│                                                                  │
│ TOTAL COST: $0.15 - $0.20 per complete course                 │
│                                                                  │
│ COMPARISON                                                      │
│ ├─ Before (single Lambda): Timeout ❌ Cost: $0.02 + retry     │
│ └─ After (batch orchestration): Success ✅ Cost: $0.15-0.20    │
│                                                                  │
│ ROI: Worth it to have working solution!                         │
│                                                                  │
└──────────────────────────────────────────────────────────────────┘
```

This architecture provides:
✅ Reliability - Handles large courses
✅ Scalability - Works for 100+ lessons
✅ Maintainability - Clear separation of concerns
✅ Monitoring - Full observability
✅ Cost Efficiency - Optimized resource usage
