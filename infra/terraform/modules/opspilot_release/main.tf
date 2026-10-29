# Reusable module: wraps `helm install` as a Terraform-managed
# resource, rather than Terraform hand-rolling the same Kubernetes
# manifests the Helm chart already defines. This is the realistic
# division of labor between the two tools -- the chart (charts/opspilot/)
# is the single source of truth for what gets deployed; Terraform's job
# is lifecycle management (install/upgrade/rollback, tracked in state,
# composable with whatever else Terraform provisions alongside it --
# e.g. the cluster itself, DNS, secrets).
#
# Reusability: this module takes no opinion on WHICH chart or cluster
# -- chart_path and the provider's kubeconfig are both inputs -- so the
# same module can deploy a second, unrelated service later by pointing
# it at a different chart, which is what "reusable module" means in
# practice rather than just in name.

resource "helm_release" "opspilot" {
  name             = "opspilot"
  namespace        = var.namespace
  create_namespace = true
  chart            = var.chart_path

  set {
    name  = "image.repository"
    value = var.image_repository
  }
  set {
    name  = "image.tag"
    value = var.image_tag
  }
  set {
    name  = "config.targetRepo"
    value = var.target_repo
  }
  set {
    name  = "config.llmProvider"
    value = var.llm_provider
  }
  set {
    name  = "replicaCount"
    value = var.replicas
  }

  # A Deployment rolling out is not the same as it being ready --
  # wait=true makes `terraform apply` only report success once the
  # pod actually passes its readiness probe (see deployment.yaml),
  # the same discipline as the CI workflow's own smoke test.
  wait    = true
  timeout = 120
}
