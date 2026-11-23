# Deliberately insecure GCP infrastructure, for IaC scanning only. Never apply this.

provider "google" {
  project = "demo-project"
  region  = "europe-west3"
}

# VULN (IaC): storage bucket without uniform access or versioning
resource "google_storage_bucket" "trade_reports" {
  name     = "demo-trade-reports-bucket"
  location = "EU"
}

# VULN (IaC): bucket readable by anyone on the internet
resource "google_storage_bucket_iam_member" "public_read" {
  bucket = google_storage_bucket.trade_reports.name
  role   = "roles/storage.objectViewer"
  member = "allUsers"
}

# VULN (IaC): SSH open to the whole internet
resource "google_compute_firewall" "allow_ssh" {
  name    = "allow-ssh-from-anywhere"
  network = "default"

  allow {
    protocol = "tcp"
    ports    = ["22"]
  }

  source_ranges = ["0.0.0.0/0"]
}

# VULN (IaC): database reachable from the internet, no SSL enforced
resource "google_sql_database_instance" "risk_db" {
  name             = "demo-risk-db"
  database_version = "POSTGRES_15"
  region           = "europe-west3"

  settings {
    tier = "db-f1-micro"

    ip_configuration {
      ipv4_enabled = true

      authorized_networks {
        name  = "anywhere"
        value = "0.0.0.0/0"
      }
    }
  }
}
