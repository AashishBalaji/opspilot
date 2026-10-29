variable "chart_path" {
  description = "Filesystem path to the opspilot Helm chart (charts/opspilot at the repo root)"
  type        = string
}

variable "namespace" {
  type    = string
  default = "opspilot"
}

variable "image_repository" {
  type = string
}

variable "image_tag" {
  type    = string
  default = "latest"
}

variable "target_repo" {
  description = "owner/repo the agent watches"
  type        = string
}

variable "llm_provider" {
  type    = string
  default = "mock"
}

variable "replicas" {
  type    = number
  default = 1
}
