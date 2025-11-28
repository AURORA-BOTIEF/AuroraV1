# Quick Deployment Guide - Presentaciones Feature

## Prerequisites
- AWS SAM CLI installed
- AWS credentials configured
- Node.js and npm installed

## Backend Deployment

### 1. Navigate to backend directory
```bash
cd /home/juan/AuroraV1/CG-Backend
```

### 2. Build the SAM application
```bash
sam build
```

### 3. Deploy to AWS
```bash
sam deploy
```

This will deploy the three new Lambda functions:
- `ListInfographicsFunction`
- `GetInfographicFunction`
- `UpdateInfographicFunction`

### 4. Verify deployment
```bash
# Check if the new functions are deployed
aws lambda list-functions --query 'Functions[?contains(FunctionName, `Infographic`)].FunctionName'
```

## Frontend Deployment

### 1. Navigate to frontend directory
```bash
cd /home/juan/AuroraV1
```

### 2. Install dependencies (if needed)
```bash
npm install
```

### 3. Build the frontend
```bash
npm run build
```

### 4. Test locally (optional)
```bash
npm run dev
```
Then visit `http://localhost:5173/presentaciones`

### 5. Deploy to Amplify
The deployment to AWS Amplify happens automatically when you push to your git repository:

```bash
git add .
git commit -m "Add Presentaciones viewer and editor"
git push origin main  # or your branch name
```

Amplify will automatically:
1. Detect the changes
2. Build the application
3. Deploy to production

## Verification Steps

### 1. Test Backend APIs
```bash
# Test list-infographics endpoint
curl "https://h6ysn7u0tl.execute-api.us-east-1.amazonaws.com/dev2/list-infographics?page=1&limit=10"

# Test get-infographic endpoint (replace {folder} with actual project folder)
curl "https://h6ysn7u0tl.execute-api.us-east-1.amazonaws.com/dev2/infographic/{folder}"
```

### 2. Test Frontend
1. Navigate to your deployed app
2. Click "Generador de Contenidos"
3. Click "Presentaciones" button
4. Verify presentations load
5. Click "Ver" on a presentation
6. Test navigation (arrow keys, buttons)
7. Click "Editar" on a presentation
8. Make a change and save
9. Verify changes persist

## Troubleshooting

### Backend Issues

**Lambda timeout errors:**
- Increase timeout in `template.yaml` for `UpdateInfographicFunction`
- Current: 60s, can increase to 300s if needed

**S3 permission errors:**
- Verify IAM policies in `template.yaml` include:
  - `s3:GetObject`
  - `s3:PutObject`
  - `s3:ListBucket`
  - `s3:HeadObject`

**CORS errors:**
- Verify API Gateway CORS settings in `template.yaml`
- Headers should include: `Access-Control-Allow-Origin: *`

### Frontend Issues

**Routes not working:**
- Verify routes in `App.jsx` are correctly defined
- Check that imports are correct at top of file

**API calls failing:**
- Check API_BASE constant in each component
- Should be: `https://h6ysn7u0tl.execute-api.us-east-1.amazonaws.com/dev2`

**CSS not loading:**
- Verify CSS files are in the same directory as components
- Check import statements in JSX files

**Images not showing:**
- Presigned URLs expire after 1 hour
- Reload the page to get fresh URLs
- Check browser console for 403 errors

## Rollback Plan

If something goes wrong, you can rollback:

### Backend
```bash
cd /home/juan/AuroraV1/CG-Backend
sam deploy --parameter-overrides ParameterKey=Version,ParameterValue=previous
```

### Frontend
1. Go to AWS Amplify Console
2. Find your app
3. Go to "App settings" → "Rewrites and redirects"
4. Click "Deploy a specific version"
5. Select previous deployment

## Post-Deployment Checklist

- [ ] All three Lambda functions deployed
- [ ] API Gateway endpoints responding
- [ ] Frontend builds without errors
- [ ] Can access `/presentaciones` route
- [ ] Presentations list loads
- [ ] Viewer works with keyboard navigation
- [ ] Editor can save changes
- [ ] Changes persist after page reload
- [ ] No console errors in browser

## Monitoring

### CloudWatch Logs
Monitor Lambda function logs:
```bash
# List Infographics
sam logs -n ListInfographicsFunction --tail

# Get Infographic
sam logs -n GetInfographicFunction --tail

# Update Infographic
sam logs -n UpdateInfographicFunction --tail
```

### API Gateway Metrics
Check API Gateway in AWS Console:
- 4xx errors (client errors)
- 5xx errors (server errors)
- Latency
- Request count

## Performance Optimization

### Backend
- Lambda functions are set to appropriate memory:
  - List: 256MB
  - Get: 512MB
  - Update: 1024MB (needs more for HTML generation)

### Frontend
- CSS uses CSS Grid for efficient layouts
- Images use presigned URLs (no base64 encoding)
- Pagination limits results to 12 per page

## Security Notes

- All API endpoints use IAM authorization
- S3 presigned URLs expire after 1 hour
- No sensitive data stored in frontend
- All user actions logged in CloudWatch

## Support

If you encounter issues:
1. Check CloudWatch logs for backend errors
2. Check browser console for frontend errors
3. Verify S3 bucket has infographic files
4. Confirm API_BASE URL is correct
5. Test API endpoints with curl first

## Success Metrics

After deployment, you should see:
- 3 new Lambda functions in AWS Console
- 3 new API routes in API Gateway
- New "Presentaciones" button enabled
- Ability to view and edit presentations
- HTML regeneration working correctly
