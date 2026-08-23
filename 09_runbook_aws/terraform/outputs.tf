output "orderer_ips" {
  value = { for k, v in aws_instance.orderer : k => v.public_ip }
}

output "peer_org4_ip" {
  value = aws_instance.peer_org4.public_ip
}

output "caliper_ip" {
  value = aws_instance.caliper.public_ip
}

output "s3_bucket" {
  value = aws_s3_bucket.results.bucket
}

output "ansible_inventory" {
  value = templatefile("${path.module}/inventory.tmpl", {
    orderers      = aws_instance.orderer
    peer_org4_ip  = aws_instance.peer_org4.public_ip
    caliper_ip    = aws_instance.caliper.public_ip
  })
  sensitive = false
}
