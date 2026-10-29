variable "kubeconfig_path" {
  description = "Path to a kubeconfig file. In CI this points at the ephemeral kind cluster the workflow creates."
  type        = string
  default     = "~/.kube/config"
}

variable "image_repository" {
  description = "Container image repository for the OpsPilot agent, built and loaded into the cluster by CI before this applies"
  type        = string
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
