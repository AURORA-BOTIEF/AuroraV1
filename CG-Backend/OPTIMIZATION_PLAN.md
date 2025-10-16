# Pipeline Parallelization Optimization Plan

## Current Architecture (Sequential)
```
[All Modules] → ContentGen (loops internally) → [All Lessons Generated]
                ↓
[All Lessons] → Map: VisualPlanner (parallel per lesson)
                ↓
[All Prompts] → ImagesGen (processes all)
                ↓
              BookBuilder
```

**Problem:** Module 2 can't start until Module 1 is complete, even though Module 2 doesn't depend on Module 1's images.

## Proposed Architecture (Pipelined)
```
Map State (per module, MaxConcurrency: 3):
  Module 1: ContentGen → VisualPlanner → ImagesGen ──┐
  Module 2: ContentGen → VisualPlanner → ImagesGen ──┼→ [Wait All]
  Module 3: ContentGen → VisualPlanner → ImagesGen ──┘       ↓
                                                        BookBuilder
```

**Benefit:** Module 2 starts immediately after Module 1 ContentGen completes (doesn't wait for images).

## Implementation Changes

### 1. **State Machine Changes** (template.yaml)

#### Add PrepareModulesList state (before processing)
```yaml
PrepareModulesList:
  Type: Pass
  Comment: "Convert modules_to_generate array into Map items"
  Parameters:
    modules.$: $.modules_to_generate
    base_params:
      course_bucket.$: $.course_bucket
      outline_s3_key.$: $.outline_s3_key
      project_folder.$: $.project_folder
      model_provider.$: $.model_provider
      content_source.$: $.content_source
  Next: ProcessModulesInParallel
```

#### Add ProcessModulesInParallel Map state
```yaml
ProcessModulesInParallel:
  Type: Map
  ItemsPath: $.modules
  MaxConcurrency: 3  # Process 3 modules at a time
  Parameters:
    module_number.$: $$.Map.Item.Value
    course_bucket.$: $.base_params.course_bucket
    outline_s3_key.$: $.base_params.outline_s3_key
    project_folder.$: $.base_params.project_folder
    model_provider.$: $.base_params.model_provider
    content_source.$: $.base_params.content_source
  Iterator:
    StartAt: GenerateModuleContent
    States:
      GenerateModuleContent:
        Type: Task
        Resource: arn:aws:states:::lambda:invoke
        Parameters:
          FunctionName: !GetAtt StrandsContentGen.Arn
          Payload:
            module_number.$: $.module_number  # Single module!
            course_bucket.$: $.course_bucket
            # ... other params
        Next: ProcessVisualsForModule
      
      ProcessVisualsForModule:
        Type: Map
        ItemsPath: $.Payload.lesson_keys
        MaxConcurrency: 3
        Parameters:
          lesson_key.$: $$.Map.Item.Value
          # ...
        Iterator:
          StartAt: InvokeVisualPlanner
          # ... (same as current)
        Next: GenerateImagesForModule
      
      GenerateImagesForModule:
        Type: Task
        Resource: arn:aws:states:::lambda:invoke
        Parameters:
          FunctionName: !GetAtt ImagesGen.Arn
          # ...
        End: true
  ResultPath: $.all_module_results
  Next: CombineAndBuildBook
```

#### Add CombineAndBuildBook state
```yaml
CombineAndBuildBook:
  Type: Pass
  Comment: "Flatten results from all modules"
  Parameters:
    course_bucket.$: $.base_params.course_bucket
    project_folder.$: $.base_params.project_folder
    all_lesson_keys.$: $.all_module_results[*].lesson_keys[*]
    all_image_mappings.$: $.all_module_results[*].images_result.Payload.image_mappings
  Next: InvokeBookBuilder
```

### 2. **ContentGen Lambda Changes** (strands_content_gen.py)

#### Modify to support both single module AND array (backward compatible)
```python
def lambda_handler(event, context):
    # NEW: Support single module_number (for parallel processing)
    module_number = event.get('module_number')
    modules_to_generate = event.get('modules_to_generate')
    
    if module_number is not None:
        # Single module mode (NEW - for parallel processing)
        modules_to_generate = [int(module_number)]
        print(f"🔧 Single module mode: {module_number}")
    elif modules_to_generate is not None:
        # Array mode (EXISTING - backward compatible)
        if not isinstance(modules_to_generate, list):
            modules_to_generate = [int(modules_to_generate)]
        print(f"🔧 Multi-module mode: {modules_to_generate}")
    else:
        # Fallback (EXISTING)
        module_to_generate = event.get('module_to_generate', 1)
        modules_to_generate = [int(module_to_generate)]
    
    # Rest of the code remains unchanged!
    # The loop already handles the array correctly
```

**Backward Compatibility Guaranteed:**
- ✅ Old invocations with `modules_to_generate: [1,2,3]` still work
- ✅ New invocations with `module_number: 1` work for parallel processing
- ✅ No breaking changes to existing code

### 3. **No Changes Needed For:**
- ✅ VisualPlanner - already processes single lesson
- ✅ ImagesGen - already processes prompts folder
- ✅ BookBuilder - already combines multiple lesson results
- ✅ LabPlanner/LabWriter - can be optimized separately later

## Performance Improvement Estimate

### Current Performance (4-module course):
```
Module 1 ContentGen:   5 min ──┐
Module 2 ContentGen:   5 min   ├→ 20 min total
Module 3 ContentGen:   5 min   │
Module 4 ContentGen:   5 min ──┘
                                ↓
Visual Planner (all): 3 min
Images Gen (all):     8 min
Book Builder:         1 min
───────────────────────────────
TOTAL: 32 minutes
```

### Optimized Performance (4-module course):
```
┌─ Module 1: ContentGen 5min → Visual 1min → Images 2min ──┐
├─ Module 2: ContentGen 5min → Visual 1min → Images 2min ──┼→ Wait all
├─ Module 3: ContentGen 5min → Visual 1min → Images 2min ──┤
└─ Module 4: ContentGen 5min → Visual 1min → Images 2min ──┘
                                                             ↓
                                                    Book Builder: 1min
──────────────────────────────────────────────────────────────────────
TOTAL: ~9 minutes (3x faster!)
```

**Improvement:** **~70% reduction** in total execution time!

## Risks & Mitigation

### Risk 1: Concurrent Lambda limits
**Mitigation:** MaxConcurrency: 3 prevents overwhelming AWS account limits

### Risk 2: S3 write conflicts
**Mitigation:** Each module writes to separate S3 keys (already isolated by design)

### Risk 3: BookBuilder expects specific data structure
**Mitigation:** CombineAndBuildBook state flattens and structures data correctly

### Risk 4: Breaking existing executions
**Mitigation:** Keep backward compatibility in ContentGen, deploy as new version first

## Deployment Strategy

### Phase 1: Test with single module (verify no breaking changes)
1. Deploy ContentGen with single module support
2. Test with `module_number: 1` → should work identically
3. Test with `modules_to_generate: [1,2]` → should work as before

### Phase 2: Deploy new state machine (theory-only first)
1. Update TheoryOnlyBranch with new Map state
2. Test with 2-module course
3. Verify: Module 2 starts before Module 1 images finish

### Phase 3: Update BothTheoryAndLabsBranch
1. Apply same pattern to "both" branch
2. Test full course generation

### Phase 4: Optimize labs (optional - future)
1. Similar approach: per-module lab generation
2. Even more parallelization opportunities

## Testing Checklist

- [ ] Single module: `module_number: 1` (new parameter)
- [ ] Array mode: `modules_to_generate: [1,2]` (backward compat)
- [ ] Multi-module: `modules_to_generate: [1,3,4]` (skipping module 2)
- [ ] Full course: `"all"` parameter
- [ ] Verify S3 structure unchanged
- [ ] Verify BookBuilder output correct
- [ ] Check CloudWatch metrics for concurrency
- [ ] Monitor Lambda duration (should be ~1/N of before)

## Rollback Plan

If issues occur:
1. Revert template.yaml to previous version
2. ContentGen still works with old state machine (backward compatible)
3. No data corruption risk (S3 writes are isolated)

## Next Steps

1. Review this plan
2. Approve optimization approach
3. Implement ContentGen changes first (low risk)
4. Test thoroughly
5. Deploy state machine changes
6. Monitor first production run
7. Celebrate 3x speedup! 🚀
