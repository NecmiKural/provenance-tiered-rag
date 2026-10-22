variable "region" {
  description = "AWS region. Auckland by default; use ap-southeast-2 (Sydney) if RDS PostgreSQL 17 is not offered there."
  type        = string
  default     = "ap-southeast-6"
}

variable "my_ip_cidr" {
  description = "The one address allowed to connect, as a /32, for example 203.0.113.7/32."
  type        = string

  validation {
    condition     = can(cidrhost(var.my_ip_cidr, 0)) && endswith(var.my_ip_cidr, "/32")
    error_message = "my_ip_cidr must be a single IPv4 address as a /32."
  }
}

variable "budget_email" {
  description = "Where the monthly budget alerts go."
  type        = string
}

variable "budget_usd" {
  description = "Monthly budget for the account, in US dollars."
  type        = number
  default     = 5
}

variable "instance_class" {
  description = "The smallest Graviton class is enough for a replayed evaluation."
  type        = string
  default     = "db.t4g.micro"
}

variable "engine_version" {
  description = "PostgreSQL major version; RDS picks its default minor version."
  type        = string
  default     = "17"
}
