# Secrets vivem no SSM (SecureString). O IAM usado no GitHub Actions precisa de
# ssm:GetParameter em arn:aws:ssm:us-east-1:*:parameter/loja-omena/terraform/prod/*
#
# Exemplo (repetir para cada chave em local.ssm_keys):
# aws ssm put-parameter --name "/loja-omena/terraform/prod/supabase_url" --value "..." --type SecureString
# service_role (secret, não expor no front): .../supabase_service_role_key

locals {
  ssm_prefix = "/loja-omena/terraform/prod"
  ssm_keys = [
    "supabase_url",
    "supabase_key",
    "supabase_anon_key",
    # Chave service_role (Settings → API); necessária para CRUD em tabelas com RLS no backend.
    "supabase_service_role_key",
    "firebase_project_id",
    "firebase_client_email",
    "firebase_private_key",
    "firebase_database_url",
    "melhor_envio_token",
    "cep_origem",
    "melhor_envio_api_url",
  ]
}

data "aws_ssm_parameter" "app" {
  for_each        = toset(local.ssm_keys)
  name            = "${local.ssm_prefix}/${each.key}"
  with_decryption = true
}
