# PROMPT 41: Production Deployment (Cloud Infrastructure)

## Objective
Deploy Winnow to production using Google Cloud Platform with Cloud Run (containers), Cloud SQL (PostgreSQL), Redis, and proper CI/CD. Set up monitoring, logging, secrets management, and auto-scaling infrastructure.

---

## Context
Your app currently runs locally. For production, you need:
- **Scalable compute**: Cloud Run for auto-scaling containers
- **Managed database**: Cloud SQL for PostgreSQL
- **Caching**: Memorystore for Redis
- **CI/CD**: GitHub Actions for automated deployments
- **Monitoring**: Cloud Logging and Error Reporting
- **Secrets**: Secret Manager for API keys

---

## Prerequisites
- ✅ Full application working locally
- ✅ Google Cloud account (free trial available)
- ✅ GitHub repository for your code
- ✅ Domain name (optional, can use Cloud Run URL)

---

## Architecture Overview

```
User Request
    ↓
Cloud Load Balancer (optional with custom domain)
    ↓
Cloud Run (Next.js Frontend)
    ↓
Cloud Run (FastAPI Backend)
    ↓
├─ Cloud SQL (PostgreSQL)
├─ Memorystore (Redis)
└─ Secret Manager (API Keys)
    
Monitoring:
├─ Cloud Logging
├─ Cloud Monitoring
└─ Error Reporting
```

---

## Cost Estimate (Monthly)

**Small Scale (MVP):**
- Cloud Run (Frontend): $0-20
- Cloud Run (Backend): $0-30
- Cloud SQL: $10-50
- Redis: $50
- **Total: ~$60-100/month**

**Medium Scale (Growing):**
- Cloud Run: $50-100
- Cloud SQL: $100-200
- Redis: $100
- **Total: ~$250-400/month**

Free tier covers initial development costs.

---

## Setup Steps

### Step 0: Install Google Cloud CLI

**macOS:**
```bash
brew install --cask google-cloud-sdk
```

**Windows:**
Download from: https://cloud.google.com/sdk/docs/install

**Linux:**
```bash
curl https://sdk.cloud.google.com | bash
exec -l $SHELL
```

**Initialize:**
```bash
gcloud init
gcloud auth login
```

---

### Step 1: Create GCP Project

**Commands:**
```bash
# Set variables
export PROJECT_ID="winnow-prod"
export REGION="us-central1"

# Create project
gcloud projects create $PROJECT_ID --name="Winnow Production"

# Set as active project
gcloud config set project $PROJECT_ID

# Enable billing (required - do this in console: https://console.cloud.google.com/billing)

# Enable required APIs
gcloud services enable \
  run.googleapis.com \
  sql-component.googleapis.com \
  sqladmin.googleapis.com \
  redis.googleapis.com \
  secretmanager.googleapis.com \
  cloudbuild.googleapis.com \
  artifactregistry.googleapis.com
```

---

### Step 2: Create Cloud SQL Instance

**Commands:**
```bash
# Create PostgreSQL instance (this takes ~10 minutes)
gcloud sql instances create winnow-db \
  --database-version=POSTGRES_15 \
  --tier=db-f1-micro \
  --region=$REGION \
  --root-password=CHANGE_THIS_PASSWORD \
  --storage-auto-increase

# Create database
gcloud sql databases create winnow --instance=winnow-db

# Create user
gcloud sql users create winnow_user \
  --instance=winnow-db \
  --password=CHANGE_THIS_PASSWORD
```

**Note connection name:**
```bash
gcloud sql instances describe winnow-db --format="value(connectionName)"
# Output: PROJECT_ID:REGION:winnow-db
```

---

### Step 3: Create Redis Instance

**Commands:**
```bash
# Create Redis instance (takes ~5 minutes)
gcloud redis instances create winnow-redis \
  --size=1 \
  --region=$REGION \
  --redis-version=redis_7_0

# Get Redis host
gcloud redis instances describe winnow-redis --region=$REGION --format="value(host)"
```

---

### Step 4: Set Up Secret Manager

**Commands:**
```bash
# Create secrets
echo -n "your-secret-key-here" | gcloud secrets create app-secret-key --data-file=-
echo -n "your-stripe-secret-key" | gcloud secrets create stripe-secret-key --data-file=-
echo -n "your-stripe-webhook-secret" | gcloud secrets create stripe-webhook-secret --data-file=-

# Create database URL secret
DB_URL="postgresql://winnow_user:CHANGE_THIS_PASSWORD@/winnow?host=/cloudsql/PROJECT_ID:REGION:winnow-db"
echo -n "$DB_URL" | gcloud secrets create database-url --data-file=-

# List secrets
gcloud secrets list
```

---

### Step 5: Backend Dockerfile

**Location:** Create `services/api/Dockerfile`

**Code:**
```dockerfile
FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    postgresql-client \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Expose port
EXPOSE 8080

# Run with gunicorn
CMD exec gunicorn --bind :$PORT --workers 1 --worker-class uvicorn.workers.UvicornWorker --timeout 0 app.main:app
```

**Update `requirements.txt`:**
```txt
fastapi==0.104.1
uvicorn[standard]==0.24.0
gunicorn==21.2.0
sqlalchemy==2.0.23
psycopg2-binary==2.9.9
alembic==1.12.1
python-jose[cryptography]==3.3.0
passlib[bcrypt]==1.7.4
python-multipart==0.0.6
redis==5.0.1
stripe==7.8.0
pydantic-settings==2.1.0
```

---

### Step 6: Frontend Dockerfile

**Location:** Create `web/Dockerfile`

**Code:**
```dockerfile
FROM node:20-alpine AS builder

WORKDIR /app

# Copy package files
COPY package*.json ./

# Install dependencies
RUN npm ci

# Copy source
COPY . .

# Build Next.js app
RUN npm run build

# Production image
FROM node:20-alpine

WORKDIR /app

ENV NODE_ENV production

# Copy built files
COPY --from=builder /app/public ./public
COPY --from=builder /app/.next/standalone ./
COPY --from=builder /app/.next/static ./.next/static

EXPOSE 8080

CMD ["node", "server.js"]
```

**Update `next.config.js`:**
```javascript
/** @type {import('next').NextConfig} */
const nextConfig = {
  output: 'standalone',
}

module.exports = nextConfig
```

---

### Step 7: Deploy Backend to Cloud Run

**Commands:**
```bash
cd services/api

# Build and push to Artifact Registry
gcloud builds submit \
  --tag gcr.io/$PROJECT_ID/winnow-backend

# Deploy to Cloud Run
gcloud run deploy winnow-backend \
  --image gcr.io/$PROJECT_ID/winnow-backend \
  --platform managed \
  --region $REGION \
  --allow-unauthenticated \
  --add-cloudsql-instances $PROJECT_ID:$REGION:winnow-db \
  --set-secrets DATABASE_URL=database-url:latest,SECRET_KEY=app-secret-key:latest,STRIPE_SECRET_KEY=stripe-secret-key:latest,STRIPE_WEBHOOK_SECRET=stripe-webhook-secret:latest \
  --set-env-vars REDIS_HOST=REDIS_HOST_FROM_STEP3 \
  --memory 512Mi \
  --cpu 1 \
  --min-instances 0 \
  --max-instances 10

# Get backend URL
gcloud run services describe winnow-backend --region $REGION --format="value(status.url)"
# Output: https://winnow-backend-XXXXX-uc.a.run.app
```

---

### Step 8: Run Migrations

**Commands:**
```bash
# Connect to Cloud SQL via proxy
cloud_sql_proxy -instances=$PROJECT_ID:$REGION:winnow-db=tcp:5432 &

# Set DATABASE_URL
export DATABASE_URL="postgresql://winnow_user:PASSWORD@localhost:5432/winnow"

# Run migrations
cd services/api
alembic upgrade head

# Kill proxy
pkill cloud_sql_proxy
```

---

### Step 9: Deploy Frontend to Cloud Run

**Commands:**
```bash
cd web

# Build and push
gcloud builds submit \
  --tag gcr.io/$PROJECT_ID/winnow-frontend

# Deploy
gcloud run deploy winnow-frontend \
  --image gcr.io/$PROJECT_ID/winnow-frontend \
  --platform managed \
  --region $REGION \
  --allow-unauthenticated \
  --set-env-vars NEXT_PUBLIC_API_URL=https://winnow-backend-XXXXX-uc.a.run.app \
  --memory 512Mi \
  --cpu 1 \
  --min-instances 0 \
  --max-instances 10

# Get frontend URL
gcloud run services describe winnow-frontend --region $REGION --format="value(status.url)"
# Output: https://winnow-frontend-XXXXX-uc.a.run.app
```

---

### Step 10: Set Up CI/CD with GitHub Actions

**Location:** Create `.github/workflows/deploy.yml`

**Code:**
```yaml
name: Deploy to Cloud Run

on:
  push:
    branches:
      - main

env:
  PROJECT_ID: winnow-prod
  REGION: us-central1

jobs:
  deploy-backend:
    runs-on: ubuntu-latest
    steps:
      - name: Checkout
        uses: actions/checkout@v3

      - name: Authenticate to Google Cloud
        uses: google-github-actions/auth@v1
        with:
          credentials_json: ${{ secrets.GCP_SA_KEY }}

      - name: Set up Cloud SDK
        uses: google-github-actions/setup-gcloud@v1

      - name: Build and Push Backend
        run: |
          gcloud builds submit \
            --tag gcr.io/$PROJECT_ID/winnow-backend \
            services/api

      - name: Deploy Backend to Cloud Run
        run: |
          gcloud run deploy winnow-backend \
            --image gcr.io/$PROJECT_ID/winnow-backend \
            --platform managed \
            --region $REGION \
            --allow-unauthenticated

  deploy-frontend:
    runs-on: ubuntu-latest
    needs: deploy-backend
    steps:
      - name: Checkout
        uses: actions/checkout@v3

      - name: Authenticate to Google Cloud
        uses: google-github-actions/auth@v1
        with:
          credentials_json: ${{ secrets.GCP_SA_KEY }}

      - name: Set up Cloud SDK
        uses: google-github-actions/setup-gcloud@v1

      - name: Build and Push Frontend
        run: |
          gcloud builds submit \
            --tag gcr.io/$PROJECT_ID/winnow-frontend \
            web

      - name: Deploy Frontend to Cloud Run
        run: |
          gcloud run deploy winnow-frontend \
            --image gcr.io/$PROJECT_ID/winnow-frontend \
            --platform managed \
            --region $REGION \
            --allow-unauthenticated
```

**Set up Service Account:**
```bash
# Create service account
gcloud iam service-accounts create github-actions \
  --display-name="GitHub Actions"

# Grant permissions
gcloud projects add-iam-policy-binding $PROJECT_ID \
  --member="serviceAccount:github-actions@$PROJECT_ID.iam.gserviceaccount.com" \
  --role="roles/run.admin"

gcloud projects add-iam-policy-binding $PROJECT_ID \
  --member="serviceAccount:github-actions@$PROJECT_ID.iam.gserviceaccount.com" \
  --role="roles/cloudbuild.builds.builder"

# Create key
gcloud iam service-accounts keys create key.json \
  --iam-account=github-actions@$PROJECT_ID.iam.gserviceaccount.com

# Copy contents of key.json to GitHub Secrets as GCP_SA_KEY
cat key.json
```

**Add to GitHub:**
1. Go to repository Settings > Secrets
2. Add new secret: `GCP_SA_KEY`
3. Paste the entire contents of `key.json`

---

### Step 11: Custom Domain (Optional)

**Commands:**
```bash
# Map domain to frontend
gcloud run services update winnow-frontend \
  --platform managed \
  --region $REGION \
  --add-domain-mapping=yourdomain.com

# Map domain to backend
gcloud run services update winnow-backend \
  --platform managed \
  --region $REGION \
  --add-domain-mapping=api.yourdomain.com

# Follow instructions to add DNS records
```

---

### Step 12: Set Up Monitoring

**Commands:**
```bash
# Enable Error Reporting
gcloud services enable clouderrorreporting.googleapis.com

# Create uptime check
gcloud monitoring uptime create \
  --display-name="Winnow Frontend Health" \
  --resource-type=uptime-url \
  --monitored-resource=https://winnow-frontend-XXXXX-uc.a.run.app/api/health
```

**View logs:**
```bash
# Backend logs
gcloud logging read "resource.type=cloud_run_revision AND resource.labels.service_name=winnow-backend" --limit 50

# Frontend logs
gcloud logging read "resource.type=cloud_run_revision AND resource.labels.service_name=winnow-frontend" --limit 50
```

---

### Step 13: Set Up Alerts

**Location:** GCP Console > Monitoring > Alerting

**Create alerts for:**
1. **High Error Rate**: > 5% errors in 5 minutes
2. **High Latency**: p95 > 2 seconds
3. **Low Availability**: < 95% uptime
4. **Database Connections**: > 80% of max connections
5. **Memory Usage**: > 90% of allocated memory

---

## Environment Variables Summary

### Backend (Cloud Run)
```bash
# From Secret Manager
DATABASE_URL=secret
SECRET_KEY=secret
STRIPE_SECRET_KEY=secret
STRIPE_WEBHOOK_SECRET=secret

# Environment variables
REDIS_HOST=10.x.x.x
REDIS_PORT=6379
FRONTEND_URL=https://winnow-frontend-XXXXX-uc.a.run.app
```

### Frontend (Cloud Run)
```bash
NEXT_PUBLIC_API_URL=https://winnow-backend-XXXXX-uc.a.run.app
NEXT_PUBLIC_STRIPE_PUBLISHABLE_KEY=pk_live_...
```

---

## Database Backups

**Commands:**
```bash
# Create on-demand backup
gcloud sql backups create --instance=winnow-db

# Enable automatic backups
gcloud sql instances patch winnow-db \
  --backup-start-time=03:00

# List backups
gcloud sql backups list --instance=winnow-db

# Restore from backup
gcloud sql backups restore BACKUP_ID \
  --backup-instance=winnow-db \
  --restore-instance=winnow-db
```

---

## Scaling Configuration

**Auto-scaling settings:**
```bash
# Update backend with more aggressive scaling
gcloud run services update winnow-backend \
  --min-instances=1 \
  --max-instances=20 \
  --cpu-throttling \
  --concurrency=80

# Update database for more connections
gcloud sql instances patch winnow-db \
  --tier=db-custom-2-7680
```

---

## Security Hardening

### Step 14: Security Best Practices

**1. Enable VPC Connector (optional, for private Redis):**
```bash
# Create VPC connector
gcloud compute networks vpc-access connectors create winnow-connector \
  --region=$REGION \
  --range=10.8.0.0/28

# Update Cloud Run to use connector
gcloud run services update winnow-backend \
  --vpc-connector=winnow-connector
```

**2. Set up WAF (Web Application Firewall):**
- Use Cloud Armor (requires Load Balancer)
- Set rate limiting
- Block suspicious IPs

**3. Enable audit logs:**
```bash
gcloud logging read "protoPayload.serviceName=run.googleapis.com" --limit 20
```

---

## Cost Optimization

**Tips:**
1. **Use min-instances=0** for dev/staging
2. **Set concurrency limits** to optimize container usage
3. **Use Cloud SQL Proxy** to reduce idle connections
4. **Enable auto-pause** on Cloud SQL for dev
5. **Use committed use discounts** for Cloud SQL in production

---

## Monitoring Dashboard

**Create custom dashboard:**
1. Go to Cloud Console > Monitoring > Dashboards
2. Create dashboard with:
   - Request count (Cloud Run)
   - Request latency (Cloud Run)
   - Error rate (Cloud Run)
   - Database connections (Cloud SQL)
   - Redis memory usage
   - Container CPU/Memory

---

## Rollback Procedure

**If deployment fails:**
```bash
# List revisions
gcloud run revisions list --service=winnow-backend --region=$REGION

# Rollback to previous revision
gcloud run services update-traffic winnow-backend \
  --to-revisions=REVISION_NAME=100 \
  --region=$REGION
```

---

## Testing Production

**Verify deployment:**
```bash
# Check backend health
curl https://winnow-backend-XXXXX-uc.a.run.app/health

# Check frontend
curl https://winnow-frontend-XXXXX-uc.a.run.app

# Test API endpoint
curl https://winnow-backend-XXXXX-uc.a.run.app/api/auth/signup \
  -H "Content-Type: application/json" \
  -d '{"email":"test@example.com","password":"test123","role":"candidate"}'
```

---

## Troubleshooting

### "Service not found" error
**Cause:** Service not deployed yet  
**Solution:** Run deploy command again

### "Database connection failed"
**Cause:** Cloud SQL connector not configured  
**Solution:** Add `--add-cloudsql-instances` flag to deploy

### "Secret not found"
**Cause:** Secret not created or wrong version  
**Solution:** Create secret and verify with `gcloud secrets versions list SECRET_NAME`

### High latency
**Cause:** Cold starts  
**Solution:** Set `--min-instances=1` to keep container warm

### Out of memory errors
**Cause:** Insufficient memory  
**Solution:** Increase to `--memory 1Gi` or `2Gi`

---

## Next Steps

After production deployment:

1. **Set up CDN** (Cloud CDN for static assets)
2. **Configure SSL certificates** (auto with custom domain)
3. **Set up staging environment** (separate Cloud Run services)
4. **Implement feature flags** (use environment variables)
5. **Monitor costs** (set up billing alerts)

---

## Success Criteria

✅ Backend deployed to Cloud Run  
✅ Frontend deployed to Cloud Run  
✅ Cloud SQL database created and migrated  
✅ Redis cache configured  
✅ Secrets stored in Secret Manager  
✅ CI/CD pipeline working  
✅ Monitoring and logging enabled  
✅ Custom domain configured (optional)  
✅ Backups scheduled  
✅ Production app accessible publicly  

---

**Status:** Ready for implementation  
**Estimated Time:** 4-6 hours (first time), 1-2 hours (with experience)  
**Monthly Cost:** $60-100 (low traffic), $250-400 (growing)  
**Next Prompt:** PROMPT42_Advanced_Matching.md
