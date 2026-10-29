terraform {
  required_version = ">= 1.6"
  required_providers {
    helm = {
      source  = "hashicorp/helm"
      version = "~> 2.14"
    }
  }
}

# This block is the ONE thing that changes to move this project from
# "real ephemeral cluster in CI" to "real persistent cluster on
# Azure" -- the opspilot_release module below needs zero changes
# either way, since it only talks to whatever cluster this provider
# points at.
#
# Today (this repo's CI): kubeconfig points at a `kind` cluster the
# workflow itself creates on a GitHub-hosted runner -- real, applied,
# and torn down on every run (see .github/workflows/ci.yml).
#
# On Azure (not done in this sandbox -- no Azure subscription was
# available; documented honestly rather than silently assumed): swap
# config_path for
#   kubernetes {
#     host                   = azurerm_kubernetes_cluster.this.kube_config[0].host
#     client_certificate     = base64decode(azurerm_kubernetes_cluster.this.kube_config[0].client_certificate)
#     client_key             = base64decode(azurerm_kubernetes_cluster.this.kube_config[0].client_key)
#     cluster_ca_certificate = base64decode(azurerm_kubernetes_cluster.this.kube_config[0].cluster_ca_certificate)
#   }
# fed by a sibling azurerm_kubernetes_cluster resource (a separate,
# not-yet-written module, since provisioning the cluster itself is a
# different concern from deploying a workload onto one).
provider "helm" {
  kubernetes {
    config_path = var.kubeconfig_path
  }
}

module "opspilot" {
  source = "./modules/opspilot_release"

  chart_path       = "${path.module}/../../charts/opspilot"
  image_repository = var.image_repository
  image_tag        = var.image_tag
  target_repo      = var.target_repo
  llm_provider     = var.llm_provider
  replicas         = var.replicas
}
