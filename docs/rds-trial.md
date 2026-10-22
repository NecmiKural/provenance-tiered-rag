# Running the index on Amazon RDS

A one-day trial: create a PostgreSQL 17 instance with Terraform, load the index into it, run the database tests, the replay gate and the latency measurement against it, and destroy it the same day. The output is one results file, `results/<date>-latency-rds-<region>.json`; the README table is regenerated from it.

## What the Terraform creates

[`infra/terraform/`](../infra/terraform) creates, in the default VPC:

- a `db.t4g.micro` PostgreSQL 17 instance with 20 GB of encrypted gp3 storage, no backups, no Multi-AZ and no final snapshot;
- a security group that admits port 5432 from one address only, given as a /32;
- a parameter group with `rds.force_ssl = 1`, so every connection uses TLS;
- the master password in Secrets Manager (`manage_master_user_password`), so it never enters Terraform state or this repository;
- a monthly cost budget with email alerts at half the limit and at a forecast over it.

State stays on this machine and is gitignored.

## 1. Account and tools, once

1. Create an AWS account, turn on MFA for the root user, and stop using the root user.
2. In IAM Identity Center, create a user for yourself with the `PowerUserAccess` permission set. That is enough for RDS, EC2 security groups, Secrets Manager and Budgets. Remove the assignment after the trial if you like.
3. Install the CLI and sign in:

```bash
brew install awscli
aws configure sso
aws sso login
```

## 2. Check the region

Auckland (`ap-southeast-6`) is the default. Check that it offers PostgreSQL 17, and use Sydney (`ap-southeast-2`) if it does not:

```bash
aws rds describe-db-engine-versions --engine postgres --engine-version 17 --region ap-southeast-6 --query 'DBEngineVersions[0].EngineVersion' --output text
```

## 3. Create

```bash
terraform -chdir=infra/terraform init
terraform -chdir=infra/terraform apply -var my_ip_cidr="$(curl -s https://checkip.amazonaws.com)/32" -var budget_email=you@example.com
```

Creating the instance takes several minutes. Add `-var region=ap-southeast-2` if step 2 said so.

## 4. Measure

```bash
eval "$(infra/connect.sh)"
psql "$PROVRAG_DATABASE_URL" -c "SELECT name, default_version FROM pg_available_extensions WHERE name IN ('vector', 'btree_gist')"
uv run provrag index
uv run pytest tests/test_db.py tests/test_retrieve.py tests/test_gate.py
uv run provrag latency --label rds-ap-southeast-6
```

`connect.sh` prints an export line carrying the password, so always run it through `eval`, never on its own. The connection verifies the server certificate against the RDS bundle (`sslmode=verify-full`).

## 5. Destroy, the same day

```bash
terraform -chdir=infra/terraform destroy -var my_ip_cidr="$(curl -s https://checkip.amazonaws.com)/32" -var budget_email=you@example.com
```

Check in the console that no instance is left. The budget costs nothing and may stay.

## 6. Hand back

Commit the latency results file, run `uv run provrag report`, and commit the README.
