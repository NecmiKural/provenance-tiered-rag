output "endpoint" {
  description = "Host and port of the instance."
  value       = aws_db_instance.trial.endpoint
}

output "secret_arn" {
  description = "Secrets Manager secret holding the master user's password; read it with the AWS CLI, never print it."
  value       = aws_db_instance.trial.master_user_secret[0].secret_arn
}

output "region" {
  value = var.region
}
