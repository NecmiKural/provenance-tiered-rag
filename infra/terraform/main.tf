# A single PostgreSQL instance for a one-day trial: reachable from one address only, TLS
# required, the master password kept in Secrets Manager rather than in Terraform state, and a
# budget alarm. Not a production layout: no Multi-AZ, no backups, no final snapshot.

data "aws_vpc" "default" {
  default = true
}

data "aws_subnets" "default" {
  filter {
    name   = "vpc-id"
    values = [data.aws_vpc.default.id]
  }
}

resource "aws_db_subnet_group" "trial" {
  name       = "provrag-trial"
  subnet_ids = data.aws_subnets.default.ids
}

resource "aws_security_group" "postgres" {
  name        = "provrag-trial-postgres"
  description = "PostgreSQL from one address only"
  vpc_id      = data.aws_vpc.default.id
}

resource "aws_vpc_security_group_ingress_rule" "postgres_from_me" {
  security_group_id = aws_security_group.postgres.id
  description       = "PostgreSQL from the trial operator"
  cidr_ipv4         = var.my_ip_cidr
  ip_protocol       = "tcp"
  from_port         = 5432
  to_port           = 5432
}

resource "aws_db_parameter_group" "tls_only" {
  name   = "provrag-trial-pg17"
  family = "postgres${var.engine_version}"

  parameter {
    name  = "rds.force_ssl"
    value = "1"
  }
}

resource "aws_db_instance" "trial" {
  identifier     = "provrag-trial"
  engine         = "postgres"
  engine_version = var.engine_version
  instance_class = var.instance_class

  allocated_storage = 20
  storage_type      = "gp3"
  storage_encrypted = true

  db_name                     = "provrag"
  username                    = "provrag"
  manage_master_user_password = true

  db_subnet_group_name   = aws_db_subnet_group.trial.name
  vpc_security_group_ids = [aws_security_group.postgres.id]
  parameter_group_name   = aws_db_parameter_group.tls_only.name
  publicly_accessible    = true # reachable only through the security group above

  backup_retention_period    = 0
  skip_final_snapshot        = true
  deletion_protection        = false
  auto_minor_version_upgrade = true
  apply_immediately          = true
}

resource "aws_budgets_budget" "monthly" {
  name         = "provrag-trial-monthly"
  budget_type  = "COST"
  limit_amount = tostring(var.budget_usd)
  limit_unit   = "USD"
  time_unit    = "MONTHLY"

  notification {
    comparison_operator        = "GREATER_THAN"
    threshold                  = 50
    threshold_type             = "PERCENTAGE"
    notification_type          = "ACTUAL"
    subscriber_email_addresses = [var.budget_email]
  }

  notification {
    comparison_operator        = "GREATER_THAN"
    threshold                  = 100
    threshold_type             = "PERCENTAGE"
    notification_type          = "FORECASTED"
    subscriber_email_addresses = [var.budget_email]
  }
}
