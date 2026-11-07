# Publish the merged lab from your Mac

The complete changes are committed locally. At preparation time, both Git push
and the connected GitHub API refused writes with HTTP 403. This is a GitHub
integration permission issue; chat approval does not grant repository write access.
The remote branch was not changed.

The latest Mac setup kit includes both the source folder and a sibling
`Microelectronic-layout.bundle`. Run `bash scripts/setup-git-macos.sh` from the
source folder. It restores a real checkout, preserves existing identity, uses
browser GitHub authentication, merges remote changes and pushes without force.
Default checkout: `~/Developer/Microelectronic-layout`. The full continuation
prompt is a separate kit file, not repository content.

Option 1: reconnect the GitHub integration with Contents read/write access to
`LamAnhProj/Microelectronic-layout`, then retry the push from the prepared checkout.

Option 2: download the supplied Git bundle and clone it on the Mac. It contains
the existing repository history plus the merged lab commits. Replace the download
path if your browser saves the file elsewhere:

```sh
git clone ~/Downloads/Microelectronic-layout.bundle Microelectronic-layout
cd Microelectronic-layout
git remote set-url origin https://github.com/LamAnhProj/Microelectronic-layout.git
git push origin master
bash scripts/bootstrap-macos.sh
```

Push uses your Mac's own GitHub authentication. If the remote has newer changes,
the normal push will refuse; fetch and merge them before retrying. Do not force-push.

The ZIP alternative contains source files without Git history. Unzip it and run
`bash scripts/bootstrap-macos.sh` from its directory to install/test the tools.
For publication that preserves history, use the Git bundle above.
