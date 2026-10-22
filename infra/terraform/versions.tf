terraform {
  required_version = ">= 1.9"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 6.60"
    }
  }
}

provider "aws" {
  region = var.region

  default_tags {
    tags = {
      Project = "provenance-tiered-rag"
      Purpose = "one-day RDS trial; destroy the same day"
    }
  }
}
