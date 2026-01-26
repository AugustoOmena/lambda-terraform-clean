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