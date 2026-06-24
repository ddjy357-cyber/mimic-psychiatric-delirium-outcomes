# Manual GitHub Publish Commands

Status: real GitHub repository URL provided.

Repository: https://github.com/ddjy357-cyber/mimic-psychiatric-delirium-outcomes

```powershell
cd <LOCAL_PUBLIC_RELEASE_DIR>

git status
git rev-parse HEAD
git rev-list -n 1 v1.0.3

git remote add origin https://github.com/ddjy357-cyber/mimic-psychiatric-delirium-outcomes.git
git push -u origin main
git push origin v1.0.3
```

If `origin` already exists, use:

```powershell
git remote set-url origin https://github.com/ddjy357-cyber/mimic-psychiatric-delirium-outcomes.git
git push -u origin main
git push origin v1.0.3
```

Do not force-push `main`. Do not move the already published `v1.0.2` tag; use `v1.0.3` for this ORCID metadata correction.
