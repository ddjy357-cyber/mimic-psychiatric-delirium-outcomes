# GitHub Manual Steps

Repository: https://github.com/ddjy357-cyber/mimic-psychiatric-delirium-outcomes

GitHub CLI (`gh`) was not available in the packaging environment, so publication can be completed with plain git:

```bash
cd public_release_v1_0_2
git remote set-url origin https://github.com/ddjy357-cyber/mimic-psychiatric-delirium-outcomes.git
git push -u origin main
git push origin v1.0.2
```

If no `origin` remote exists, use:

```bash
git remote add origin https://github.com/ddjy357-cyber/mimic-psychiatric-delirium-outcomes.git
git push -u origin main
git push origin v1.0.2
```

Create the GitHub release for tag `v1.0.2` after the push succeeds. Upload `public_release_v1_0_2.zip` and `SHA256SUMS.txt`.
