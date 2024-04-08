# Add a bucket to store cloud function source code in.
resource "google_storage_bucket" "twined_gcp_source" {
  name                        = "twined-gcp"
  location                    = "EU"
  force_destroy               = true
  uniform_bucket_level_access = true
  cors {
    origin          = ["*"]
    method          = ["GET"]
    response_header = ["*"]
    max_age_seconds = 3600
  }
}


# Make bucket contents public.
resource "google_storage_bucket_iam_binding" "static_assets_object_viewer" {
  bucket = google_storage_bucket.twined_gcp_source.name
  role   = "roles/storage.objectViewer"
  members = [
    "allUsers"
  ]
}
