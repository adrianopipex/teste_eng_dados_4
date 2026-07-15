terraform {
  required_version = ">= 1.5.0"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}

provider "aws" {
  region = var.aws_region
}

data "aws_caller_identity" "current" {}

variable "aws_region" {
  description = "Região da AWS onde o Glue Job será criado."
  type        = string
  default     = "us-east-1"
}

variable "glue_job_name" {
  description = "Nome do Glue Job."
  type        = string
  default     = "case_tecnico"
}

variable "glue_role_arn" {
  description = "ARN da IAM role usada pelo Glue Job."
  type        = string
}

variable "glue_script_location" {
  description = "Caminho do script ETL no S3 que o Glue Job deve executar."
  type        = string
  default     = "s3://bucket-dados/scripts/script_etl_clientes.py"
}

variable "glue_job_tags" {
  description = "Tags aplicadas ao Glue Job."
  type        = map(string)
  default = {
    Nome  = "projeto"
    Valor = "teste_eng_dados"
  }
}

resource "aws_glue_job" "cliente_glue_job" {
  name              = var.glue_job_name
  role_arn          = var.glue_role_arn
  glue_version      = "5.0"
  worker_type       = "G.1X"
  number_of_workers = 10
  max_retries       = 0

  command {
    script_location = var.glue_script_location
    python_version  = "3"
  }

  default_arguments = {
    "--job-language" = "python"
    "--TempDir"       = "s3://aws-glue-assets-${data.aws_caller_identity.current.account_id}-${var.aws_region}/temporary/"
  }

  tags = var.glue_job_tags
}

output "glue_job_name" {
  value       = aws_glue_job.cliente_glue_job.name
  description = "Nome do Glue Job criado."
}
