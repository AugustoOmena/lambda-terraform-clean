# Overrides opcionais; vazio = usa parâmetros SSM (ver ssm.tf).
variable "smtp_host" {
  type        = string
  default     = ""
  sensitive   = true
  description = "Host SMTP Twilio; produção via SSM smtp_host."
}

variable "smtp_port" {
  type        = string
  default     = ""
  description = "Porta SMTP (ex.: 587); produção via SSM smtp_port."
}

variable "smtp_user" {
  type        = string
  default     = ""
  sensitive   = true
  description = "Usuário SMTP; produção via SSM smtp_user."
}

variable "smtp_pass" {
  type        = string
  default     = ""
  sensitive   = true
  description = "Senha SMTP; produção via SSM smtp_pass."
}

variable "melhor_envio_client_secret" {
  type        = string
  default     = ""
  sensitive   = true
  description = "Secret do app Melhor Envio (HMAC webhook); produção via SSM melhor_envio_client_secret."
}
