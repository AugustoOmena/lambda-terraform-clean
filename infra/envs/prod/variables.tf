variable "aws_region" {
  default = "us-east-1"
}

variable "supabase_url" {
  description = "A URL do projeto Supabase"
  type        = string
  sensitive   = true
}

variable "supabase_key" {
  description = "A chave anon/public do Supabase"
  type        = string
  sensitive   = true
}

variable "firebase_project_id" {
  description = "Firebase Project ID"
  type        = string
  sensitive   = true
}

variable "firebase_client_email" {
  description = "Firebase Service Account Client Email"
  type        = string
  sensitive   = true
}

variable "firebase_private_key" {
  description = "Firebase Service Account Private Key"
  type        = string
  sensitive   = true
}

variable "firebase_database_url" {
  description = "Firebase Realtime Database URL"
  type        = string
  sensitive   = true
}

variable "melhor_envio_token" {
  description = "Token da API Melhor Envio (Sandbox ou produção)"
  type        = string
  sensitive   = true
}

variable "cep_origem" {
  description = "CEP de origem do envio (8 dígitos)"
  type        = string
}

variable "melhor_envio_api_url" {
  description = "URL base da API Melhor Envio (opcional; default = sandbox)"
  type        = string
  default     = "https://sandbox.melhorenvio.com.br"
}