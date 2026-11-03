# R2 storage and separate compute

R2 is S3-compatible object storage, not a CPU/GPU server:
https://developers.cloudflare.com/r2/ . Remote execution needs a separate Linux
host; none has been purchased or configured here.

Select/create a private bucket and configure `chip-lab-r2` with `rclone config`:
https://developers.cloudflare.com/r2/examples/rclone/ . Use the example in
`config/rclone-r2.example.conf`. Store real credentials in rclone's private config
outside the repo, with a bucket-scoped token. Do not paste secrets into chat or
give them to simulation containers.

```sh
# Preview: no objects copied.
bash scripts/archive-r2.sh runs chip-lab-r2:YOUR_BUCKET
# Explicit transfer after reviewing the preview.
bash scripts/archive-r2.sh runs chip-lab-r2:YOUR_BUCKET --upload
```

`rclone copy` preserves local files and does not delete remote objects. The script
archives one selected directory, never the whole repository or home. It does not
yet reclaim disk space or validate a complete archival manifest. Before manually
removing local data, verify remote contents/checksums. Review source licenses
before mirroring PDKs or datasets.

Prefixes: `data/raw/<source>/<revision>/`, `data/curated/<version>/`,
`pdks/<process>/<revision>/`, `runs/<uuid>/`. Keep small manifests in Git with
source, revision, SHA256, license, intended use and validation status. Materialize
only active subsets locally.
