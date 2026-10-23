# Copyright 2026 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     https://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

# Artifact Registry Docker repository for the Agent container image
resource "google_artifact_registry_repository" "agent_repo" {
  location      = var.region
  project       = var.project_id
  repository_id = "${var.project_name}-repo"
  description   = "Docker repository for ${var.project_name} container images"
  format        = "DOCKER"

  depends_on = [google_project_service.services]
}

# Dedicated least-privilege Service Account for GKE worker nodes
resource "google_service_account" "gke_node_sa" {
  account_id   = "${var.project_name}-gke-nodes"
  display_name = "${var.project_name} GKE Node Service Account"
  project      = var.project_id

  depends_on = [google_project_service.services]
}

# Grant minimum required node permissions (logging, monitoring, node service account role)
resource "google_project_iam_member" "gke_node_sa_default" {
  project = var.project_id
  role    = "roles/container.defaultNodeServiceAccount"
  member  = "serviceAccount:${google_service_account.gke_node_sa.email}"
}

resource "google_project_iam_member" "gke_node_sa_artifact_reader" {
  project = var.project_id
  role    = "roles/artifactregistry.reader"
  member  = "serviceAccount:${google_service_account.gke_node_sa.email}"
}

# Private GKE Standard Cluster on the custom VPC network with Workload Identity enabled
resource "google_container_cluster" "primary" {
  name     = "${var.project_name}-gke-${var.region}"
  location = var.region
  project  = var.project_id

  network         = google_compute_network.gke_vpc.id
  subnetwork      = google_compute_subnetwork.gke_subnet.id
  networking_mode = "VPC_NATIVE"

  # Use separately managed node pool
  remove_default_node_pool = true
  initial_node_count       = 1

  deletion_protection = var.gke_deletion_protection

  release_channel {
    channel = "REGULAR"
  }

  # VPC-native alias IP ranges for Pods and Services
  ip_allocation_policy {
    cluster_secondary_range_name  = var.pods_secondary_range_name
    services_secondary_range_name = var.services_secondary_range_name
  }

  # Private nodes with public control plane endpoint
  private_cluster_config {
    enable_private_nodes    = true
    enable_private_endpoint = false
    master_ipv4_cidr_block  = var.gke_master_ipv4_cidr_block
  }

  # Enable Workload Identity Federation for GKE
  workload_identity_config {
    workload_pool = "${var.project_id}.svc.id.goog"
  }

  depends_on = [
    google_project_service.services,
    google_compute_subnetwork.gke_subnet,
  ]
}

# Separately managed GKE Node Pool with GKE Metadata Server enabled for Workload Identity
resource "google_container_node_pool" "primary_nodes" {
  name     = "${var.project_name}-node-pool"
  location = var.region
  cluster  = google_container_cluster.primary.name
  project  = var.project_id

  autoscaling {
    min_node_count = var.gke_min_node_count
    max_node_count = var.gke_max_node_count
  }

  management {
    auto_repair  = true
    auto_upgrade = true
  }

  node_config {
    machine_type    = var.gke_machine_type
    disk_size_gb    = 50
    disk_type       = "pd-standard"
    service_account = google_service_account.gke_node_sa.email

    oauth_scopes = [
      "https://www.googleapis.com/auth/cloud-platform",
    ]

    # Route Pod metadata requests through the GKE Metadata Server for Workload Identity
    workload_metadata_config {
      mode = "GKE_METADATA"
    }

    shielded_instance_config {
      enable_secure_boot          = true
      enable_integrity_monitoring = true
    }

    labels = {
      app = var.project_name
    }

    tags = ["${var.project_name}-gke-node"]
  }
}

# Bind the Kubernetes Service Account to the GCP Application Service Account via Workload Identity
resource "google_service_account_iam_member" "app_sa_workload_identity" {
  service_account_id = google_service_account.app_sa.name
  role               = "roles/iam.workloadIdentityUser"
  member             = "serviceAccount:${var.project_id}.svc.id.goog[${var.k8s_namespace}/${var.k8s_service_account_name}]"

  # The project Workload Identity pool is initialized when the cluster is created
  depends_on = [google_container_cluster.primary]
}
