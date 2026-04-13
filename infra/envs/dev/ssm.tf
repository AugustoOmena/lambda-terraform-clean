# Secrets vivem no SSM da conta DEV (SecureString). Prefixo distinto de prod.
# IAM do deploy precisa de ssm:GetParameter em .../loja-omena/terraform/dev/*
# service_role Supabase: .../dev/supabase_service_role_key (Lambda products usa em SUPABASE_SERVICE_ROLE_KEY)

locals {
  ssm_prefix = "/loja-omena/terraform/dev"
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
