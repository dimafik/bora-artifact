# Terraform configuration for multi-region AWS Raft deployment
# Deploys 5-node cluster across 3 regions: us-east-1, eu-west-1, ap-northeast-1
# Usage:
#   terraform init
#   terraform plan -var="ai_augmented=true"
#   terraform apply

terraform {
  required_version = ">= 1.5"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}

variable "ai_augmented" {
  type        = bool
  default     = true
  description = "Enable AI-augmented bounded-blacklist advisor"
}

variable "image_uri" {
  type        = string
  default     = "ghcr.io/example/raft-blacklist:v28"
  description = "Container image URI"
}

variable "instance_type" {
  type    = string
  default = "c5n.xlarge"
}

provider "aws" {
  alias  = "us_east_1"
  region = "us-east-1"
}

provider "aws" {
  alias  = "eu_west_1"
  region = "eu-west-1"
}

provider "aws" {
  alias  = "ap_northeast_1"
  region = "ap-northeast-1"
}

# Topology
# Nodes 0,1 in us-east-1
# Nodes 2,3 in eu-west-1
# Node 4   in ap-northeast-1
locals {
  topology = {
    0 = "us-east-1"
    1 = "us-east-1"
    2 = "eu-west-1"
    3 = "eu-west-1"
    4 = "ap-northeast-1"
  }
}

resource "aws_instance" "raft_us_east" {
  for_each      = { for k, v in local.topology : k => v if v == "us-east-1" }
  provider      = aws.us_east_1
  ami           = data.aws_ami.amazon_linux_2_use1.id
  instance_type = var.instance_type
  tags = {
    Name      = "raft-node-${each.key}-us-east-1"
    NodeId    = each.key
    Region    = "us-east-1"
    Component = "raft-blacklist"
  }
  user_data = templatefile("${path.module}/userdata.sh.tpl", {
    node_id      = each.key
    region       = "us-east-1"
    image_uri    = var.image_uri
    ai_augmented = var.ai_augmented
  })
}

resource "aws_instance" "raft_eu_west" {
  for_each      = { for k, v in local.topology : k => v if v == "eu-west-1" }
  provider      = aws.eu_west_1
  ami           = data.aws_ami.amazon_linux_2_euw1.id
  instance_type = var.instance_type
  tags = {
    Name      = "raft-node-${each.key}-eu-west-1"
    NodeId    = each.key
    Region    = "eu-west-1"
    Component = "raft-blacklist"
  }
  user_data = templatefile("${path.module}/userdata.sh.tpl", {
    node_id      = each.key
    region       = "eu-west-1"
    image_uri    = var.image_uri
    ai_augmented = var.ai_augmented
  })
}

resource "aws_instance" "raft_ap_northeast" {
  for_each      = { for k, v in local.topology : k => v if v == "ap-northeast-1" }
  provider      = aws.ap_northeast_1
  ami           = data.aws_ami.amazon_linux_2_apne1.id
  instance_type = var.instance_type
  tags = {
    Name      = "raft-node-${each.key}-ap-northeast-1"
    NodeId    = each.key
    Region    = "ap-northeast-1"
    Component = "raft-blacklist"
  }
  user_data = templatefile("${path.module}/userdata.sh.tpl", {
    node_id      = each.key
    region       = "ap-northeast-1"
    image_uri    = var.image_uri
    ai_augmented = var.ai_augmented
  })
}

data "aws_ami" "amazon_linux_2_use1" {
  provider    = aws.us_east_1
  most_recent = true
  owners      = ["amazon"]
  filter {
    name   = "name"
    values = ["amzn2-ami-hvm-*-x86_64-gp2"]
  }
}

data "aws_ami" "amazon_linux_2_euw1" {
  provider    = aws.eu_west_1
  most_recent = true
  owners      = ["amazon"]
  filter {
    name   = "name"
    values = ["amzn2-ami-hvm-*-x86_64-gp2"]
  }
}

data "aws_ami" "amazon_linux_2_apne1" {
  provider    = aws.ap_northeast_1
  most_recent = true
  owners      = ["amazon"]
  filter {
    name   = "name"
    values = ["amzn2-ami-hvm-*-x86_64-gp2"]
  }
}

output "node_ips" {
  description = "Public IPs of all Raft nodes"
  value = {
    for k, v in merge(
      aws_instance.raft_us_east,
      aws_instance.raft_eu_west,
      aws_instance.raft_ap_northeast
    ) : k => v.public_ip
  }
}
