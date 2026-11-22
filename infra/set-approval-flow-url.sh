#!/usr/bin/env bash
# Store the Power Automate approval flow's trigger URL as a Container Apps secret
# and point the API at it. The URL carries a signature (sig=...) that works like a
# password, so it is read without echoing and never written to disk or the repo.
#
# Usage: infra/set-approval-flow-url.sh   (then paste the URL from the flow's trigger)
set -euo pipefail

RG=${RG:-rg-loanlens-demo}
APP=${APP:-loanlens-api}
AZ=${AZ:-az}

read -rsp "Paste the approval flow URL: " FLOW_URL
echo
if [[ $FLOW_URL != https://* ]]; then
  echo "That doesn't look like a flow URL (it should start with https://)." >&2
  exit 1
fi

"$AZ" containerapp secret set --resource-group "$RG" --name "$APP" \
  --secrets "approval-flow-url=$FLOW_URL" --output none
"$AZ" containerapp update --resource-group "$RG" --name "$APP" \
  --set-env-vars "APPROVAL_FLOW_URL=secretref:approval-flow-url" --output none
unset FLOW_URL
echo "Approval flow URL saved. The API will call the flow on the next submission."
