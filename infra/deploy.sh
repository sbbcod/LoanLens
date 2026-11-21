#!/usr/bin/env bash
# Create (or bring up to date) everything LoanLens needs on Azure.
#
#   1. budget alerts           4. Container Apps environment + the API app
#   2. resource group          5. Static Web App for the front end
#   3. Azure SQL (free offer)  6. sign-in for GitHub Actions (OpenID Connect)
#   7. wait for the API, then load the ten sample applications
#
# Safe to run again: existing resources are kept and settings are re-applied.
#
# Before running:
#   - `az login` with the account that owns the subscription
#   - the API image exists on GitHub Container Registry and is public
#     (the first push to main builds it)
#   - ANTHROPIC_API_KEY is set in backend/.env (or exported in the shell)
#
# Generated secrets (database password, API key, demo passcode) are kept in
# infra/.env.azure, which is git-ignored, so a re-run reuses them. Nothing secret
# is printed.

set -euo pipefail

AZ=${AZ:-az}
LOCATION=australiaeast
# Static Web Apps has no Australian region to choose. The files are served from
# Azure's global edge network anyway; this is only where the resource record lives.
WEB_LOCATION=eastasia

RG=rg-loanlens-demo
ENV_NAME=cae-loanlens
APP=loanlens-api
WEB=loanlens-web
DB=loanlens
SQL_ADMIN=loanlensadmin
GITHUB_REPO=${GITHUB_REPO:-sbbcod/LoanLens}
IMAGE=${IMAGE:-ghcr.io/sbbcod/loanlens-api:latest}
LLM_MODEL=${LLM_MODEL:-claude-opus-5-5}
LLM_EFFORT=${LLM_EFFORT:-medium}
BUDGET_AMOUNT=${BUDGET_AMOUNT:-15}   # in the billing currency (AUD)

ROOT=$(cd "$(dirname "$0")/.." && pwd)
STATE="$ROOT/infra/.env.azure"

step() { printf '\n\033[1m==> %s\033[0m\n' "$*"; }
exists() { "$@" --output none >/dev/null 2>&1; }
random() { openssl rand -base64 48 | tr -dc 'A-Za-z0-9' | head -c "$1"; }

# --- Preconditions ----------------------------------------------------------

step "Checking sign-in and inputs"
SUB_ID=$($AZ account show --query id --output tsv)
TENANT_ID=$($AZ account show --query tenantId --output tsv)
EMAIL=$($AZ account show --query user.name --output tsv)
echo "Subscription: $($AZ account show --query name --output tsv)"

if [[ -z "${ANTHROPIC_API_KEY:-}" && -f "$ROOT/backend/.env" ]]; then
  ANTHROPIC_API_KEY=$(sed -n 's/^ANTHROPIC_API_KEY=//p' "$ROOT/backend/.env" | tail -n 1 | tr -d '"'"'"' \r')
fi
[[ -n "${ANTHROPIC_API_KEY:-}" ]] || { echo "ANTHROPIC_API_KEY is not set." >&2; exit 1; }

# The Container App pulls the image anonymously, so it must be public.
repo_path=${IMAGE#ghcr.io/}; repo_path=${repo_path%:*}
ghcr_token=$(curl -fsS "https://ghcr.io/token?scope=repository:${repo_path}:pull" | sed -n 's/.*"token":"\([^"]*\)".*/\1/p')
if ! curl -fsS -o /dev/null -H "Authorization: Bearer $ghcr_token" \
     -H "Accept: application/vnd.oci.image.index.v1+json,application/vnd.docker.distribution.manifest.v2+json" \
     "https://ghcr.io/v2/${repo_path}/manifests/${IMAGE##*:}"; then
  echo "Can't pull $IMAGE. Push to main so GitHub Actions builds it, then make the package public." >&2
  exit 1
fi

# Generated secrets: create once, reuse on every later run.
touch "$STATE"; chmod 600 "$STATE"
# shellcheck disable=SC1090
source "$STATE"
: "${SQL_PASSWORD:=$(random 28)Aa1}"
: "${API_KEY:=$(random 40)}"
: "${DEMO_PASSCODE:=loanlens-$(random 6 | tr 'A-Z' 'a-z')}"
printf 'SQL_PASSWORD=%s\nAPI_KEY=%s\nDEMO_PASSCODE=%s\n' "$SQL_PASSWORD" "$API_KEY" "$DEMO_PASSCODE" > "$STATE"

# Globally unique names get a short suffix derived from the subscription.
SUFFIX=$(printf '%s' "$SUB_ID" | shasum | cut -c1-6)
SQL_SERVER=sql-loanlens-$SUFFIX

step "Registering resource providers"
for ns in Microsoft.App Microsoft.Sql Microsoft.Web Microsoft.Consumption; do
  $AZ provider register --namespace "$ns" --wait --output none
done

# --- 1. Budget --------------------------------------------------------------

step "Budget alerts: emails at 10%, 50% and 100% of $BUDGET_AMOUNT a month"
budget=$(mktemp)
notify() { printf '"%s": {"enabled": true, "operator": "GreaterThan", "threshold": %s, "thresholdType": "%s", "contactEmails": ["%s"]}' "$1" "$2" "$3" "$EMAIL"; }
cat > "$budget" <<JSON
{
  "properties": {
    "category": "Cost",
    "amount": $BUDGET_AMOUNT,
    "timeGrain": "Monthly",
    "timePeriod": {"startDate": "$(date -u +%Y-%m-01)T00:00:00Z", "endDate": "2030-12-31T00:00:00Z"},
    "notifications": {
      $(notify actual10 10 Actual), $(notify actual50 50 Actual),
      $(notify actual100 100 Actual), $(notify forecast100 100 Forecasted)
    }
  }
}
JSON
$AZ rest --method put --body "@$budget" --output none \
  --url "https://management.azure.com/subscriptions/$SUB_ID/providers/Microsoft.Consumption/budgets/loanlens-budget?api-version=2023-05-01"
rm -f "$budget"

# --- 2. Resource group ------------------------------------------------------

step "Resource group $RG"
$AZ group create --name "$RG" --location "$LOCATION" --output none

# --- 3. Azure SQL -----------------------------------------------------------

step "Azure SQL server $SQL_SERVER and database $DB (free offer)"
if exists $AZ sql server show --name "$SQL_SERVER" --resource-group "$RG"; then
  $AZ sql server update --name "$SQL_SERVER" --resource-group "$RG" --admin-password "$SQL_PASSWORD" --output none
else
  $AZ sql server create --name "$SQL_SERVER" --resource-group "$RG" --location "$LOCATION" \
    --admin-user "$SQL_ADMIN" --admin-password "$SQL_PASSWORD" --minimal-tls-version 1.2 --output none
fi
# 0.0.0.0 is Azure's special rule for "services running inside Azure". The
# database still needs the password; nothing outside Azure can reach it.
$AZ sql server firewall-rule create --server "$SQL_SERVER" --resource-group "$RG" \
  --name AllowAzureServices --start-ip-address 0.0.0.0 --end-ip-address 0.0.0.0 --output none
if ! exists $AZ sql db show --name "$DB" --server "$SQL_SERVER" --resource-group "$RG"; then
  # Serverless with the monthly free allowance. When the allowance runs out the
  # database pauses until next month instead of starting to bill.
  $AZ sql db create --name "$DB" --server "$SQL_SERVER" --resource-group "$RG" \
    --edition GeneralPurpose --family Gen5 --capacity 2 --compute-model Serverless \
    --use-free-limit --free-limit-exhaustion-behavior AutoPause \
    --backup-storage-redundancy Local --output none
fi
DATABASE_URL="mssql+pyodbc://${SQL_ADMIN}:${SQL_PASSWORD}@${SQL_SERVER}.database.windows.net:1433/${DB}?driver=ODBC+Driver+18+for+SQL+Server&Encrypt=yes&TrustServerCertificate=no&Connection+Timeout=30"

# --- 5 (first, so the API knows the front end's address). Static Web App ---

step "Static Web App $WEB"
if ! exists $AZ staticwebapp show --name "$WEB" --resource-group "$RG"; then
  $AZ staticwebapp create --name "$WEB" --resource-group "$RG" --location "$WEB_LOCATION" --sku Free --output none
fi
WEB_URL="https://$($AZ staticwebapp show --name "$WEB" --resource-group "$RG" --query defaultHostname --output tsv)"

# --- 4. Container Apps ------------------------------------------------------

step "Container Apps environment $ENV_NAME"
if ! exists $AZ containerapp env show --name "$ENV_NAME" --resource-group "$RG"; then
  # No Log Analytics workspace: log ingestion is billed and the demo doesn't need it.
  $AZ containerapp env create --name "$ENV_NAME" --resource-group "$RG" --location "$LOCATION" \
    --logs-destination none --output none
fi

step "Container App $APP"
SECRETS=(
  "database-url=$DATABASE_URL"
  "anthropic-api-key=$ANTHROPIC_API_KEY"
  "api-key=$API_KEY"
  "demo-passcode=$DEMO_PASSCODE"
)
ENV_VARS=(
  "DATABASE_URL=secretref:database-url"
  "ANTHROPIC_API_KEY=secretref:anthropic-api-key"
  "API_KEY=secretref:api-key"
  "DEMO_PASSCODE=secretref:demo-passcode"
  "LLM_PROVIDER=anthropic"
  "LLM_MODEL=$LLM_MODEL"
  "LLM_EFFORT=$LLM_EFFORT"
  "CORS_ORIGINS=[\"$WEB_URL\"]"
  "FRONTEND_URL=$WEB_URL"
)
if exists $AZ containerapp show --name "$APP" --resource-group "$RG"; then
  $AZ containerapp secret set --name "$APP" --resource-group "$RG" --secrets "${SECRETS[@]}" --output none
  $AZ containerapp update --name "$APP" --resource-group "$RG" --set-env-vars "${ENV_VARS[@]}" --output none
else
  # Scale to zero when idle; one replica at most, because uploads are processed
  # in the background inside the API process.
  $AZ containerapp create --name "$APP" --resource-group "$RG" --environment "$ENV_NAME" \
    --image "$IMAGE" --target-port 8000 --ingress external \
    --cpu 0.5 --memory 1.0Gi --min-replicas 0 --max-replicas 1 \
    --secrets "${SECRETS[@]}" --env-vars "${ENV_VARS[@]}" --output none
fi
API_URL="https://$($AZ containerapp show --name "$APP" --resource-group "$RG" --query properties.configuration.ingress.fqdn --output tsv)"

# --- 6. GitHub Actions sign-in ----------------------------------------------

step "GitHub Actions sign-in for $GITHUB_REPO (main branch only)"
CLIENT_ID=$($AZ ad app list --display-name loanlens-github --query "[0].appId" --output tsv)
if [[ -z "$CLIENT_ID" ]]; then
  CLIENT_ID=$($AZ ad app create --display-name loanlens-github --query appId --output tsv)
fi
exists $AZ ad sp show --id "$CLIENT_ID" || $AZ ad sp create --id "$CLIENT_ID" --output none
if [[ -z $($AZ ad app federated-credential list --id "$CLIENT_ID" --query "[?name=='github-main'].name" --output tsv) ]]; then
  $AZ ad app federated-credential create --id "$CLIENT_ID" --output none --parameters "{
    \"name\": \"github-main\",
    \"issuer\": \"https://token.actions.githubusercontent.com\",
    \"subject\": \"repo:${GITHUB_REPO}:ref:refs/heads/main\",
    \"audiences\": [\"api://AzureADTokenExchange\"]
  }"
fi
# Contributor on this resource group only, not the whole subscription.
RG_SCOPE="/subscriptions/$SUB_ID/resourceGroups/$RG"
if [[ -z $($AZ role assignment list --assignee "$CLIENT_ID" --scope "$RG_SCOPE" --role Contributor --query "[0].id" --output tsv) ]]; then
  $AZ role assignment create --assignee "$CLIENT_ID" --role Contributor --scope "$RG_SCOPE" --output none
fi

# --- 7. Wait for the API, then seed ----------------------------------------

step "Waiting for the API (the database may need a minute to resume)"
for _ in $(seq 1 30); do
  if curl -fsS --max-time 60 "$API_URL/api/health" >/dev/null 2>&1; then break; fi
  sleep 10
done
curl -fsS --max-time 60 "$API_URL/api/health"; echo

step "Loading the ten sample applications"
curl -fsS -X POST -H "X-API-Key: $API_KEY" "$API_URL/api/admin/reset-demo"; echo

cat <<DONE

Done.
  API:       $API_URL  (docs at $API_URL/docs)
  Web app:   $WEB_URL  (appears after the first web deploy from GitHub Actions)
  Secrets:   infra/.env.azure  (demo passcode, API key, database password)

Add these as GitHub repository variables (Settings > Secrets and variables >
Actions > Variables). They are identifiers, not secrets:
  AZURE_CLIENT_ID        $CLIENT_ID
  AZURE_TENANT_ID        $TENANT_ID
  AZURE_SUBSCRIPTION_ID  $SUB_ID
  API_URL                $API_URL
Then re-run the "Test and deploy" workflow to publish the web app.
DONE
