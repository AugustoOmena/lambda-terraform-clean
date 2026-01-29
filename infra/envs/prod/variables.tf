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