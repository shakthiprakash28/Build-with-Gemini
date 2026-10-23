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

variable "project_name" {
  type        = string
  description = "Project name used as a base for resource naming"
  default     = "k8s-investigate"
}

variable "project_id" {
  type        = string
  description = "Google Cloud Project ID for resource deployment."
  default     = "k8s-investigation-agent-511111"
}

variable "region" {
  type        = string
  description = "Google Cloud region for resource deployment."
  default     = "us-east1"
}

variable "nodes_subnet_cidr" {
  type        = string
  description = "Primary IPv4 CIDR range for GKE nodes in the regional subnet."
  default     = "10.0.0.0/20"
}

variable "pods_secondary_range_name" {
  type        = string
  description = "Name of the secondary IP range used for GKE Pods."
  default     = "gke-pods"
}

variable "pods_secondary_cidr" {
  type        = string
  description = "Secondary IPv4 CIDR range for GKE Pods."
  default     = "10.4.0.0/14"
}

variable "services_secondary_range_name" {
  type        = string
  description = "Name of the secondary IP range used for GKE Services."
  default     = "gke-services"
}

variable "services_secondary_cidr" {
  type        = string
  description = "Secondary IPv4 CIDR range for GKE Services."
  default     = "10.8.0.0/20"
}

variable "gke_master_ipv4_cidr_block" {
  type        = string
  description = "IPv4 CIDR block (/28) for the GKE private cluster control plane."
  default     = "172.16.0.0/28"
}

variable "gke_machine_type" {
  type        = string
  description = "Compute Engine machine type for GKE worker nodes."
  default     = "e2-standard-4"
}

variable "gke_min_node_count" {
  type        = number
  description = "Minimum number of nodes per zone in the primary GKE node pool."
  default     = 1
}

variable "gke_max_node_count" {
  type        = number
  description = "Maximum number of nodes per zone in the primary GKE node pool."
  default     = 3
}

variable "gke_deletion_protection" {
  type        = bool
  description = "Whether or not to allow Terraform to destroy the GKE cluster."
  default     = false
}

variable "k8s_namespace" {
  type        = string
  description = "Kubernetes namespace for Workload Identity binding."
  default     = "default"
}

variable "k8s_service_account_name" {
  type        = string
  description = "Kubernetes Service Account name bound to the application Google Service Account via Workload Identity."
  default     = "k8s-investigate-ksa"
}

variable "telemetry_logs_filter" {
  type        = string
  description = "Log Sink filter for capturing telemetry data. Captures logs with the `traceloop.association.properties.log_type` attribute set to `tracing`."
  default     = "labels.service_name=\"k8s-investigate\" labels.type=\"agent_telemetry\""
}

variable "app_sa_roles" {
  description = "List of roles to assign to the application service account"
  type        = list(string)
  default = [

    "roles/aiplatform.user",
    "roles/logging.logWriter",
    "roles/cloudtrace.agent",
    "roles/storage.admin",
    "roles/serviceusage.serviceUsageConsumer",
  ]
}

variable "agent_framework" {
  description = "Framework label on the Agent Runtime deployment. The Google Cloud console reads it to pick a playground; override it when the container is not an ADK app."
  type        = string
  default     = "google-adk"
}
