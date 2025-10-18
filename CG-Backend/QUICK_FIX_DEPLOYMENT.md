# Quick Fix for Deployment Blocker

## The Problem
`sam deploy` fails with:
```
Template error: instance of Fn::GetAtt references undefined resource PhaseCoordinator
```

## The Cause
`BothTheoryAndLabsBranch` in `template.yaml` (lines ~917-1260) still references PhaseCoordinator in 10+ places.

## Quick Fix (5 minutes) - RECOMMENDED

Replace the entire BothTheoryAndLabsBranch section with this stub:

```yaml
# Find this line (around line 917):
BothTheoryAndLabsBranch:

# Replace the entire section (lines 917-1260) with:
BothTheoryAndLabsBranch:
  Type: Pass
  Comment: "Temporarily using theory-only pattern - TODO: Add lab generation support with BatchExpander"
  ResultPath: $.both_mode_note
  Next: ExpandModulesToBatches  # Reuse the theory-only flow

# Then update the existing ExpandModulesToBatches state to handle both modes
# (It already does - no changes needed!)
```

### Exact Steps:

1. Open `/home/juan/AuroraV1/CG-Backend/template.yaml`

2. Find line ~917: `BothTheoryAndLabsBranch:`

3. Delete from line 917 to line ~1260 (everything until you see `CombineResultsAndBuildBookBoth:`)

4. Replace with:
```yaml
          BothTheoryAndLabsBranch:
            Type: Pass
            Comment: "Temporarily redirecting to theory-only flow"
            Next: ExpandModulesToBatches
```

5. Remove the duplicate `CombineResultsAndBuildBookBoth` state (keep only one CombineResultsAndBuildBook)

6. Save file

7. Build and deploy:
```bash
cd /home/juan/AuroraV1/CG-Backend
sam build
sam deploy --no-confirm-changeset
```

## Expected Result
✅ Deploy succeeds  
✅ Theory-only mode works perfectly  
⚠️ "Both" mode temporarily redirects to theory-only (labs not generated)

## To Fully Support "Both" Mode Later

Copy the TheoryOnlyBranch pattern but add lab generation:
1. Use BatchExpander to create batch tasks
2. Process batches with MaxConcurrency: 2
3. For each batch: Generate content → Process visuals → Generate images → Generate labs
4. No PhaseCoordinator locks needed

---

**That's it! Just remove/replace BothTheoryAndLabsBranch and you can deploy immediately.**
