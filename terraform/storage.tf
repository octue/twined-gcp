# Add a static bucket (public contents)
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


# Make static bucket contents public
resource "google_storage_bucket_iam_binding" "static_assets_object_viewer" {
  bucket = google_storage_bucket.twined_gcp_source.name
  role   = "roles/storage.objectViewer"
  members = [
    "allUsers"
  ]
}


## Allow operating service account to generate signed upload urls
#resource "google_storage_bucket_iam_binding" "media_assets_object_admin" {
#  bucket = google_storage_bucket.media_assets.name
#  role   = "roles/storage.objectAdmin"
#  members = [
#    "serviceAccount:${google_service_account.server_service_account.email}"
#  ]
#}
