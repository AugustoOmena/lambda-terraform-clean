variable "function_name" { description = "Nome da função Lambda" }
variable "handler" { description = "Ex: handler.lambda_handler" }
variable "source_dir" { description = "Caminho da pasta com o código Python" }
variable "layers" { 
  description = "Lista de ARNs de Layers" 
  type = list(string)
  default = []
}
variable "environment_variables" {
  description = "Variáveis de ambiente"
  type = map(string)
  default = {}
}
variable "tags" { type = map(string) }
variable "timeout" {
  description = "Timeout da Lambda em segundos"
  type        = number
  default     = 10
}
variable "memory_size" {
  description = "Memória da Lambda em MB"
  type        = number
  default     = 128
}

variable "ssm_app_secrets_prefix" {
  description = "Prefixo SSM (ex: /loja-omena/terraform/prod) para ssm:GetParameter em {prefix}/* — reduz env > 4KB. Vazio = desligado."
  type        = string
  default     = ""
}