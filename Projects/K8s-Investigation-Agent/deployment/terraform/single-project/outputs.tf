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

output "app_service_account_email" {
  description = "Application service account email"
  value       = google_service_account.app_sa.email
}

output "logs_bucket_name" {
  description = "Logs storage bucket name"
  value       = google_storage_bucket.logs_data_bucket.name
}

output "vpc_network_name" {
  description = "Name of the custom VPC network"
  value       = google_compute_network.gke_vpc.name
}

output "vpc_network_id" {
  description = "ID of the custom VPC network"
  value       = google_compute_network.gke_vpc.id
}

output "gke_subnetwork_name" {
  description = "Name of the GKE regional subnetwork"
  value       = google_compute_subnetwork.gke_subnet.name
}

output "gke_subnetwork_id" {
  description = "ID of the GKE regional subnetwork"
  value       = google_compute_subnetwork.gke_subnet.id
}

output "pods_secondary_range_name" {
  description = "Secondary IP range name for GKE Pods"
  value       = var.pods_secondary_range_name
}

output "services_secondary_range_name" {
  description = "Secondary IP range name for GKE Services"
  value       = var.services_secondary_range_name
}

output "gke_cluster_name" {
  description = "Name of the private GKE cluster"
  value       = google_container_cluster.primary.name
}

output "gke_cluster_location" {
  description = "Region/location of the private GKE cluster"
  value       = google_container_cluster.primary.location
}

output "gke_cluster_endpoint" {
  description = "Control plane IP endpoint of the GKE cluster"
  value       = google_container_cluster.primary.endpoint
  sensitive   = true
}

output "gke_node_service_account_email" {
  description = "Service account email used by GKE worker nodes"
  value       = google_service_account.gke_node_sa.email
}

output "workload_identity_pool" {
  description = "GKE Workload Identity pool for the project"
  value       = "${var.project_id}.svc.id.goog"
}

output "gke_get_credentials_command" {
  description = "gcloud command to configure kubectl credentials for the private GKE cluster"
  value       = "gcloud container clusters get-credentials ${google_container_cluster.primary.name} --region ${google_container_cluster.primary.location} --project ${var.project_id}"
}

output "artifact_registry_image_uri" {
  description = "Artifact Registry Docker image URI for the K8s Investigation Agent"
  value       = "${var.region}-docker.pkg.dev/${var.project_id}/${google_artifact_registry_repository.agent_repo.repository_id}/${var.project_name}:latest"
}
