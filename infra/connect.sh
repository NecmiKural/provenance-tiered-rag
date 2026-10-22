#!/usr/bin/env bash
# Print the export line for PROVRAG_DATABASE_URL, pointing at the RDS trial instance, with TLS
# verified against the RDS certificate bundle. Use it as:  eval "$(infra/connect.sh)"
# The password is read from Secrets Manager into the URL and is never echoed on its own.
set -euo pipefail

here="$(cd "$(dirname "$0")" && pwd)"
tf() { terraform -chdir="$here/terraform" output -raw "$1"; }

endpoint="$(tf endpoint)"
secret_arn="$(tf secret_arn)"
region="$(tf region)"

bundle="$here/rds-global-bundle.pem"
if [ ! -s "$bundle" ]; then
  curl -sf -o "$bundle" https://truststore.pki.rds.amazonaws.com/global/global-bundle.pem
fi

password="$(aws secretsmanager get-secret-value --region "$region" --secret-id "$secret_arn" \
  --query SecretString --output text | python3 -c 'import json,sys,urllib.parse; print(urllib.parse.quote(json.load(sys.stdin)["password"], safe=""))')"

echo "export PROVRAG_DATABASE_URL='postgresql://provrag:${password}@${endpoint}/provrag?sslmode=verify-full&sslrootcert=${bundle}'"
