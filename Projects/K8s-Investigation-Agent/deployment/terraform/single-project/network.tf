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

# Custom-mode VPC network for the private GKE cluster
resource "google_compute_network" "gke_vpc" {
  name                    = "${var.project_name}-vpc"
  project                 = var.project_id
  auto_create_subnetworks = false
  routing_mode            = "REGIONAL"
  description             = "Custom VPC network for private GKE cluster in ${var.project_name}"

  depends_on = [google_project_service.services]
}

# Regional subnetwork in us-east1 with Private Google Access and secondary IP ranges for GKE
resource "google_compute_subnetwork" "gke_subnet" {
  name                     = "${var.project_name}-gke-subnet-${var.region}"
  project                  = var.project_id
  region                   = var.region
  network                  = google_compute_network.gke_vpc.id
  ip_cidr_range            = var.nodes_subnet_cidr
  private_ip_google_access = true
  description              = "Private GKE subnetwork in ${var.region} with alias IP ranges for Pods and Services"

  secondary_ip_range {
    range_name    = var.pods_secondary_range_name
    ip_cidr_range = var.pods_secondary_cidr
  }

  secondary_ip_range {
    range_name    = var.services_secondary_range_name
    ip_cidr_range = var.services_secondary_cidr
  }
}

# Cloud Router for Cloud NAT
resource "google_compute_router" "gke_router" {
  name    = "${var.project_name}-router-${var.region}"
  project = var.project_id
  region  = var.region
  network = google_compute_network.gke_vpc.id
}

# Cloud NAT to provide outbound internet connectivity for private GKE nodes and pods
resource "google_compute_router_nat" "gke_nat" {
  name                               = "${var.project_name}-nat-${var.region}"
  project                            = var.project_id
  region                             = var.region
  router                             = google_compute_router.gke_router.name
  nat_ip_allocate_option             = "AUTO_ONLY"
  source_subnetwork_ip_ranges_to_nat = "LIST_OF_SUBNETWORKS"

  subnetwork {
    name                    = google_compute_subnetwork.gke_subnet.id
    source_ip_ranges_to_nat = ["ALL_IP_RANGES"]
  }

  log_config {
    enable = true
    filter = "ERRORS_ONLY"
  }
}

# Firewall rule allowing internal communication across nodes, pods, and services
resource "google_compute_firewall" "allow_internal" {
  name        = "${var.project_name}-allow-internal"
  project     = var.project_id
  network     = google_compute_network.gke_vpc.name
  description = "Allow internal traffic between GKE nodes, pods, and services"
  direction   = "INGRESS"
  priority    = 1000

  source_ranges = [
    var.nodes_subnet_cidr,
    var.pods_secondary_cidr,
    var.services_secondary_cidr,
  ]

  allow {
    protocol = "tcp"
  }

  allow {
    protocol = "udp"
  }

  allow {
    protocol = "icmp"
  }
}

# Firewall rule allowing SSH via Identity-Aware Proxy (IAP) for secure debugging
resource "google_compute_firewall" "allow_iap_ssh" {
  name        = "${var.project_name}-allow-iap-ssh"
  project     = var.project_id
  network     = google_compute_network.gke_vpc.name
  description = "Allow ingress SSH access via Google Cloud IAP"
  direction   = "INGRESS"
  priority    = 1000

  # Google Cloud IAP TCP forwarding IP range
  source_ranges = ["35.235.240.0/20"]

  allow {
    protocol = "tcp"
    ports    = ["22"]
  }
}
