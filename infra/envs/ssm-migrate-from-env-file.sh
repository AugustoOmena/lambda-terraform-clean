#!/usr/bin/env bash
# Popula SSM a partir de um arquivo com linhas KEY=value (chaves = local.ssm_keys em ssm.tf).
# Uso (na conta AWS correta, com AWS CLI configurado):
#   PREFIX=/loja-omena/terraform/prod ./ssm-migrate-from-env-file.sh ./secrets.prod.env
set -euo pipefail

PREFIX="${PREFIX:?set PREFIX e.g. /loja-omena/terraform/prod}"
FILE="${1:?caminho do arquivo env}"

while IFS= read -r line || [[ -n "$line" ]]; do
  [[ "$line" =~ ^[[:space:]]*# ]] && continue
  [[ -z "${line// }" ]] && continue
  key="${line%%=*}"
  val="${line#*=}"
  key="${key// /}"
  [[ -z "$key" ]] && continue
  aws ssm put-parameter \
    --name "${PREFIX}/${key}" \
    --value "$val" \
    --type SecureString \
    --overwrite
done < "$FILE"
