# Manual GitHub Publish Commands

Status: real GitHub repository URL provided.

Repository: https://github.com/ddjy357-cyber/mimic-psychiatric-delirium-outcomes

```powershell
cd <LOCAL_PUBLIC_RELEASE_DIR>

git status
git rev-parse HEAD
git rev-list -n 1 v1.0.1

git remote add origin https://github.com/ddjy357-cyber/mimic-psychiatric-delirium-outcomes.git
git push -u origin main
git push origin v1.0.1
```

If `origin` already exists, use:

```powershell
git remote set-url origin https://github.com/ddjy357-cyber/mimic-psychiatric-delirium-outcomes.git
git push -u origin main
git push origin v1.0.1
```

Do not force-push `main`. If `v1.0.1` has already been publicly released, do not move it silently; use a new patch version instead.
