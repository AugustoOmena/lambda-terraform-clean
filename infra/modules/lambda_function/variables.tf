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