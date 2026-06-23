# GitHub Manual Steps

GitHub CLI (`gh`) was not available in the packaging environment. The repository was prepared locally with git and tag `v1.0.0` when possible.

After installing and authenticating GitHub CLI, run:

```bash
cd public_release_v1
gh auth login
gh repo create mimic-psychiatric-delirium-outcomes --public --source=. --remote=origin --push
git push origin main
git push origin v1.0.0
gh release create v1.0.0 ../public_release_v1.zip SHA256SUMS.txt --title "Code and aggregate results for psychiatric comorbidity, ICU delirium, and post-discharge outcomes" --notes-file RELEASE_NOTES_v1.0.0.md
```
