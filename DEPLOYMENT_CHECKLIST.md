# Lab Generation - Quick Deployment Checklist

## ✅ Pre-Deployment Verification

- [ ] All code changes committed
- [ ] No syntax errors in Lambda functions
- [ ] SAM template validates successfully
- [ ] Strands Agents layer is available

## 🚀 Deployment Steps

### 1. Backend (AWS SAM)
```bash
cd /home/juan/AuroraV1/CG-Backend
sam build
sam deploy
```

### 2. Frontend (Git Push → Amplify)
```bash
cd /home/juan/AuroraV1
git add .
git commit -m "feat: Add lab generation module"
git push origin testing
```

## 🧪 Quick Test

### Test Labs Only
1. Go to: Generador Cursos page
2. Upload outline YAML
3. Select: "Solo Guía de Laboratorios"
4. Optional: Add requirements
5. Click "Generar Contenido"
6. Check S3: `{project}/labguide/lab-*.md`

## 📊 Success Indicators

✅ Backend Deployed:
- New Lambdas appear in AWS Console
- State machine updated
- No CloudFormation errors

✅ Frontend Deployed:
- Amplify build succeeds
- New UI options visible
- No console errors

✅ Labs Generated:
- `labguide/lab-master-plan.json` created
- Multiple `.md` files in labguide/
- CloudWatch logs show "✅ COMPLETED"

## 🔍 Troubleshooting

**Build fails?**
→ Check Lambda layer exists: `lambda-layers/strands-layer.zip`

**State machine fails?**
→ Check Lambda permissions in IAM
→ Verify content_type parameter is passed

**No labs generated?**
→ Verify outline has `lab_activities` sections
→ Check CloudWatch logs for errors

## 📞 Quick Links

- **Frontend:** https://testing.d28h59guct50tx.amplifyapp.com
- **Step Functions:** AWS Console → Step Functions → CourseGeneratorStateMachine
- **CloudWatch:** /aws/lambda/StrandsLabPlanner, /aws/lambda/StrandsLabWriter
- **S3 Bucket:** crewai-course-artifacts

## 🎯 Key Metrics

| Metric | Target | Check |
|--------|--------|-------|
| Lab Planner Timeout | <600s | CloudWatch |
| Lab Writer Timeout | <900s | CloudWatch |
| Master Plan Size | ~50KB | S3 object |
| Per-Lab Guide Size | ~10-20KB | S3 object |
| Cost per Module | ~$2.92 | AWS Cost Explorer |

---

**Last Updated:** October 14, 2025  
**Status:** ✅ Ready for Deployment
