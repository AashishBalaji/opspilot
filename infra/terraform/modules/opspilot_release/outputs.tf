output "namespace" {
  value = helm_release.opspilot.namespace
}

output "release_name" {
  value = helm_release.opspilot.name
}

output "release_status" {
  value = helm_release.opspilot.status
}
