# Manual GitHub Release Steps

Status: pending GitHub authentication/release creation.

After pushing `main` and `v1.0.3`:

1. Open the repository in GitHub.
2. Go to **Releases**.
3. Select **Draft a new release**.
4. Choose tag `v1.0.3`.
5. Use release title:
   `ORCID metadata correction for psychiatric comorbidity, ICU delirium, and post-discharge outcomes`
6. Paste the contents of `RELEASE_NOTES_v1.0.3.md` into the release body.
7. Upload:
   - `<PROJECT_ROOT>\public_release_v1_0_3.zip`
   - `<LOCAL_PUBLIC_RELEASE_DIR>\SHA256SUMS.txt`
8. Publish the release.
9. Record the real GitHub repository URL and release URL.

Do not invent or pre-fill the GitHub release URL before it exists.
