#!/bin/bash
# Deployment script for Presentaciones feature
# This script deploys both backend (Lambda functions) and frontend (React components)

set -e  # Exit on error

echo "=========================================="
echo "🚀 PRESENTACIONES FEATURE DEPLOYMENT"
echo "=========================================="
echo ""

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Get script directory
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
BACKEND_DIR="$SCRIPT_DIR/CG-Backend"
FRONTEND_DIR="$SCRIPT_DIR"

echo -e "${BLUE}Script directory: $SCRIPT_DIR${NC}"
echo ""

# Function to print colored messages
print_success() {
    echo -e "${GREEN}✅ $1${NC}"
}

print_error() {
    echo -e "${RED}❌ $1${NC}"
}

print_warning() {
    echo -e "${YELLOW}⚠️  $1${NC}"
}

print_info() {
    echo -e "${BLUE}ℹ️  $1${NC}"
}

# Check if AWS CLI is installed
if ! command -v aws &> /dev/null; then
    print_error "AWS CLI is not installed. Please install it first."
    exit 1
fi
print_success "AWS CLI is installed"

# Check if SAM CLI is installed
if ! command -v sam &> /dev/null; then
    print_error "SAM CLI is not installed. Please install it first."
    exit 1
fi
print_success "SAM CLI is installed"

# Check if npm is installed
if ! command -v npm &> /dev/null; then
    print_error "npm is not installed. Please install Node.js first."
    exit 1
fi
print_success "npm is installed"

echo ""
echo "=========================================="
echo "📦 STEP 1: BACKEND DEPLOYMENT (Lambda)"
echo "=========================================="
echo ""

cd "$BACKEND_DIR"
print_info "Changed to backend directory: $BACKEND_DIR"

# Build SAM application
print_info "Building SAM application..."
if sam build; then
    print_success "SAM build completed successfully"
else
    print_error "SAM build failed"
    exit 1
fi

echo ""

# Deploy SAM application
print_info "Deploying Lambda functions to AWS..."
print_warning "This may take a few minutes..."

if sam deploy --no-confirm-changeset --no-fail-on-empty-changeset; then
    print_success "Backend deployment completed successfully"
    
    # Verify Lambda functions are deployed
    echo ""
    print_info "Verifying Lambda function deployment..."
    
    FUNCTIONS=$(aws lambda list-functions --query 'Functions[?contains(FunctionName, `Infographic`)].FunctionName' --output text)
    
    if [ -z "$FUNCTIONS" ]; then
        print_warning "No Infographic functions found - this may be normal if deploying for the first time"
    else
        print_success "Deployed Lambda functions:"
        echo "$FUNCTIONS" | tr '\t' '\n' | while read func; do
            echo "  - $func"
        done
    fi
else
    print_error "Backend deployment failed"
    exit 1
fi

echo ""
echo "=========================================="
echo "🎨 STEP 2: FRONTEND DEPLOYMENT"
echo "=========================================="
echo ""

cd "$FRONTEND_DIR"
print_info "Changed to frontend directory: $FRONTEND_DIR"

# Check if node_modules exists
if [ ! -d "node_modules" ]; then
    print_info "Installing npm dependencies..."
    if npm install; then
        print_success "Dependencies installed"
    else
        print_error "npm install failed"
        exit 1
    fi
else
    print_success "Dependencies already installed"
fi

echo ""

# Build frontend
print_info "Building React application..."
if npm run build; then
    print_success "Frontend build completed successfully"
else
    print_error "Frontend build failed"
    exit 1
fi

echo ""
print_info "Frontend built successfully at: $FRONTEND_DIR/dist"
print_warning "Note: Amplify will automatically deploy when you push to git"

echo ""
echo "=========================================="
echo "📤 STEP 3: GIT COMMIT & PUSH"
echo "=========================================="
echo ""

# Check if there are changes to commit
if [ -n "$(git status --porcelain)" ]; then
    print_info "Staging changes..."
    git add .
    
    print_info "Committing changes..."
    git commit -m "feat: Add Presentaciones viewer and editor feature

- Added ListInfographicsFunction Lambda
- Added GetInfographicFunction Lambda
- Added UpdateInfographicFunction Lambda
- Created PresentacionesPage component with list view
- Created InfographicViewer with presentation and grid modes
- Created InfographicEditor with three-panel layout
- Enabled Presentaciones button in GeneradorContenidosPage
- Updated App.jsx with new routes"
    
    print_success "Changes committed"
    
    echo ""
    read -p "Do you want to push to git now? This will trigger Amplify deployment. (y/n) " -n 1 -r
    echo ""
    
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        CURRENT_BRANCH=$(git branch --show-current)
        print_info "Pushing to branch: $CURRENT_BRANCH"
        
        if git push origin "$CURRENT_BRANCH"; then
            print_success "Pushed to git successfully"
            print_info "Amplify will now automatically build and deploy the frontend"
        else
            print_error "Git push failed"
            exit 1
        fi
    else
        print_warning "Skipped git push. You can push manually later with:"
        echo "  git push origin $(git branch --show-current)"
    fi
else
    print_info "No changes to commit"
fi

echo ""
echo "=========================================="
echo "✅ DEPLOYMENT COMPLETE"
echo "=========================================="
echo ""

print_success "Backend Lambda functions deployed successfully"
print_success "Frontend built successfully"

echo ""
echo "📋 NEXT STEPS:"
echo ""
echo "1. Monitor Amplify deployment:"
echo "   https://console.aws.amazon.com/amplify/"
echo ""
echo "2. Test the new endpoints:"
echo "   curl https://h6ysn7u0tl.execute-api.us-east-1.amazonaws.com/dev2/list-infographics"
echo ""
echo "3. Access the feature in your app:"
echo "   Navigate to: /presentaciones"
echo ""
echo "4. Monitor Lambda logs:"
echo "   sam logs -n ListInfographicsFunction --tail"
echo "   sam logs -n GetInfographicFunction --tail"
echo "   sam logs -n UpdateInfographicFunction --tail"
echo ""

print_info "Deployment script completed successfully! 🎉"
echo ""
