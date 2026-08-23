# =============================================================================
# AWS 5-hour Fabric experiment — Terraform definition
# Locked at preregister hash time. DO NOT modify after T-1:00.
# =============================================================================

terraform {
  required_version = ">= 1.6.0"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.30"
    }
  }
  backend "local" {
    path = "terraform.tfstate"
  }
}

provider "aws" {
  region = "us-east-1"
  default_tags {
    tags = {
      Project   = "schedulable-bft-tnse"
      RunId     = var.run_id
      Owner     = "prof.jung78@gmail.com"
      AutoStop  = "true"
      ExpiresAt = formatdate("YYYY-MM-DDThh:mm:ssZ", timeadd(timestamp(), "5h30m"))
    }
  }
}

# ---------------------------------------------------------------------------
# Variables
# ---------------------------------------------------------------------------

variable "run_id" {
  type        = string
  description = "Unique run identifier, e.g. 2026-06-01-r1"
}

variable "fabric_ami_id" {
  type        = string
  description = "Pre-baked AMI containing Fabric 2.5.4 + Docker + Caliper"
}

variable "key_pair_name" {
  type        = string
  description = "EC2 key pair for SSH"
}

variable "bastion_cidr" {
  type        = string
  description = "Operator IP/32 for SSH"
}

# ---------------------------------------------------------------------------
# Network
# ---------------------------------------------------------------------------

resource "aws_vpc" "main" {
  cidr_block           = "10.0.0.0/16"
  enable_dns_hostnames = true
  tags = { Name = "sched-bft-${var.run_id}" }
}

resource "aws_internet_gateway" "gw" {
  vpc_id = aws_vpc.main.id
}

resource "aws_subnet" "az_a" {
  vpc_id                  = aws_vpc.main.id
  cidr_block              = "10.0.1.0/24"
  availability_zone       = "us-east-1a"
  map_public_ip_on_launch = true
}

resource "aws_subnet" "az_b" {
  vpc_id                  = aws_vpc.main.id
  cidr_block              = "10.0.2.0/24"
  availability_zone       = "us-east-1b"
  map_public_ip_on_launch = true
}

resource "aws_subnet" "az_c" {
  vpc_id                  = aws_vpc.main.id
  cidr_block              = "10.0.3.0/24"
  availability_zone       = "us-east-1c"
  map_public_ip_on_launch = true
}

resource "aws_route_table" "public" {
  vpc_id = aws_vpc.main.id
  route {
    cidr_block = "0.0.0.0/0"
    gateway_id = aws_internet_gateway.gw.id
  }
}

resource "aws_route_table_association" "a" {
  subnet_id      = aws_subnet.az_a.id
  route_table_id = aws_route_table.public.id
}
resource "aws_route_table_association" "b" {
  subnet_id      = aws_subnet.az_b.id
  route_table_id = aws_route_table.public.id
}
resource "aws_route_table_association" "c" {
  subnet_id      = aws_subnet.az_c.id
  route_table_id = aws_route_table.public.id
}

# ---------------------------------------------------------------------------
# Security group — minimal exposure
# ---------------------------------------------------------------------------

resource "aws_security_group" "cluster" {
  name        = "sched-bft-${var.run_id}"
  description = "Fabric cluster + observability"
  vpc_id      = aws_vpc.main.id

  ingress {
    description = "SSH from operator"
    from_port   = 22
    to_port     = 22
    protocol    = "tcp"
    cidr_blocks = [var.bastion_cidr]
  }

  ingress {
    description = "Fabric orderer client"
    from_port   = 7050
    to_port     = 7053
    protocol    = "tcp"
    self        = true
  }

  ingress {
    description = "Fabric peer chaincode"
    from_port   = 7051
    to_port     = 7053
    protocol    = "tcp"
    self        = true
  }

  ingress {
    description = "Orderer admin metrics"
    from_port   = 9443
    to_port     = 9443
    protocol    = "tcp"
    self        = true
  }

  ingress {
    description = "Prometheus scrape + probes"
    from_port   = 9090
    to_port     = 9095
    protocol    = "tcp"
    self        = true
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }
}

# ---------------------------------------------------------------------------
# IAM — minimal role: S3 PutObject + CloudWatch metrics
# ---------------------------------------------------------------------------

resource "aws_iam_role" "node" {
  name = "sched-bft-${var.run_id}-node"
  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect = "Allow"
      Principal = { Service = "ec2.amazonaws.com" }
      Action = "sts:AssumeRole"
    }]
  })
}

resource "aws_iam_role_policy" "node" {
  role = aws_iam_role.node.id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect   = "Allow"
        Action   = ["s3:PutObject", "s3:GetObject", "s3:ListBucket"]
        Resource = [
          aws_s3_bucket.results.arn,
          "${aws_s3_bucket.results.arn}/*"
        ]
      },
      {
        Effect   = "Allow"
        Action   = ["cloudwatch:PutMetricData"]
        Resource = "*"
      }
    ]
  })
}

resource "aws_iam_instance_profile" "node" {
  name = "sched-bft-${var.run_id}-node"
  role = aws_iam_role.node.name
}

# ---------------------------------------------------------------------------
# S3 — durable results
# ---------------------------------------------------------------------------

resource "aws_s3_bucket" "results" {
  bucket = "schedulable-bft-${var.run_id}"
  force_destroy = false  # protect run artifacts
}

resource "aws_s3_bucket_versioning" "results" {
  bucket = aws_s3_bucket.results.id
  versioning_configuration { status = "Enabled" }
}

resource "aws_s3_bucket_lifecycle_configuration" "results" {
  bucket = aws_s3_bucket.results.id
  rule {
    id     = "transition-cold"
    status = "Enabled"
    # An empty filter selects the whole bucket. Omitting both filter and prefix
    # is accepted with a warning by provider 5.x and becomes an error later, so
    # the intent is stated rather than left to a default that is going away.
    filter {}
    transition {
      days          = 90
      storage_class = "GLACIER"
    }
  }
}

# ---------------------------------------------------------------------------
# Compute — 5 c5n.4xlarge + 1 t3.large
# ---------------------------------------------------------------------------

locals {
  orderers = {
    orderer1 = { subnet = aws_subnet.az_a.id, az = "us-east-1a", org = "Org1" }
    orderer2 = { subnet = aws_subnet.az_b.id, az = "us-east-1b", org = "Org2" }
    orderer3 = { subnet = aws_subnet.az_c.id, az = "us-east-1c", org = "Org3" }
  }
}

resource "aws_instance" "orderer" {
  for_each      = local.orderers
  ami           = var.fabric_ami_id
  instance_type = "c5n.4xlarge"
  subnet_id     = each.value.subnet
  key_name      = var.key_pair_name
  vpc_security_group_ids = [aws_security_group.cluster.id]
  iam_instance_profile   = aws_iam_instance_profile.node.name

  root_block_device {
    volume_type = "gp3"
    volume_size = 200
    iops        = 3000
    throughput  = 125
  }

  user_data = templatefile("${path.module}/userdata.sh", {
    role     = "orderer"
    org      = each.value.org
    run_id   = var.run_id
    bucket   = aws_s3_bucket.results.bucket
  })

  tags = { Name = "sched-bft-${var.run_id}-${each.key}", Role = "orderer", Org = each.value.org }
}

resource "aws_instance" "peer_org4" {
  ami           = var.fabric_ami_id
  instance_type = "c5n.4xlarge"
  subnet_id     = aws_subnet.az_a.id
  key_name      = var.key_pair_name
  vpc_security_group_ids = [aws_security_group.cluster.id]
  iam_instance_profile   = aws_iam_instance_profile.node.name

  root_block_device {
    volume_type = "gp3"
    volume_size = 200
    iops        = 3000
    throughput  = 125
  }

  user_data = templatefile("${path.module}/userdata.sh", {
    role   = "peer"
    org    = "Org4"
    run_id = var.run_id
    bucket = aws_s3_bucket.results.bucket
  })

  tags = { Name = "sched-bft-${var.run_id}-peer-org4", Role = "peer", Org = "Org4" }
}

resource "aws_instance" "caliper" {
  ami           = var.fabric_ami_id
  instance_type = "t3.large"
  subnet_id     = aws_subnet.az_b.id
  key_name      = var.key_pair_name
  vpc_security_group_ids = [aws_security_group.cluster.id]
  iam_instance_profile   = aws_iam_instance_profile.node.name

  root_block_device {
    volume_type = "gp3"
    volume_size = 100
    iops        = 3000
  }

  user_data = templatefile("${path.module}/userdata.sh", {
    role   = "caliper"
    org    = "DriverOrg"
    run_id = var.run_id
    bucket = aws_s3_bucket.results.bucket
  })

  tags = { Name = "sched-bft-${var.run_id}-caliper", Role = "caliper" }
}

# ---------------------------------------------------------------------------
# Cost guard — billing alarm
# ---------------------------------------------------------------------------

resource "aws_cloudwatch_metric_alarm" "billing_50" {
  alarm_name          = "sched-bft-${var.run_id}-billing-50"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 1
  metric_name         = "EstimatedCharges"
  namespace           = "AWS/Billing"
  period              = 300
  statistic           = "Maximum"
  threshold           = 50
  alarm_description   = "Soft warning: run cost has crossed $50"
}

resource "aws_cloudwatch_metric_alarm" "billing_60" {
  alarm_name          = "sched-bft-${var.run_id}-billing-60"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 1
  metric_name         = "EstimatedCharges"
  namespace           = "AWS/Billing"
  period              = 300
  statistic           = "Maximum"
  threshold           = 60
  alarm_description   = "Hard stop: trigger run abort"
}
