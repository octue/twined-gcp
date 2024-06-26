terraform {
  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "5.25.0"
    }
  }
  cloud {
    organization = "octue"
    workspaces {
      name = "octue-twined-gcp"
    }
  }
}


resource "google_project_service" "cloud_resource_manager" {
  project = var.project
  service = "cloudresourcemanager.googleapis.com"

  timeouts {
    create = "30m"
    update = "40m"
  }
}


resource "google_project_service" "iam" {
  project = var.project
  service = "iam.googleapis.com"

  timeouts {
    create = "30m"
    update = "40m"
  }
}


provider "google" {
  credentials = file(var.credentials_file)
  project     = var.project
  region      = var.region
#  zone        = var.zone
}
