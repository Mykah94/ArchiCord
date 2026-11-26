# Publishing ArchiCord on GitHub 🚀

The main project repository is [Mykah94/ArchiCord](https://github.com/Mykah94/ArchiCord). This guide is for users who maintain their own fork or copy.

## Option A: GitHub website

1. Create a repository at [github.com](https://github.com/).
2. **Extract the project archive** first; upload the project files, not a single ZIP.
3. In your new repository, open **Add file → Upload files**. Keep the `.github/`, `docs/`, `tracker/` and `webui_assets/` directories, plus dotfiles such as `.gitignore`, `.gitattributes`, and `.env.example`.
4. Commit the public source files. **Do not upload `.env` or private tracker data.**
5. Visit **Actions** and review your test workflow.

## Option B: Git CLI

From an extracted, unversioned project folder:

```bash
git init
git add .
git status
git commit -m "Initial ArchiCord import"
git branch -M main
git remote add origin https://github.com/YOUR_USERNAME/ArchiCord.git
git push -u origin main
```

Replace `YOUR_USERNAME` with your GitHub username and create the destination repository first. If you cloned a repository instead of extracting a ZIP, use your existing Git history and remote instead.

**Before publishing:** inspect `git status --short` and `git ls-files` to ensure no tokens, `.env`, player YAMLs, seed archives, DeathLink state or other secrets are tracked.

## After publishing

- Add a concise English description and topics such as `archipelago`, `discord-bot`, `multiworld`, `universal-tracker`, and `python`.
- Choose a license explicitly and only if you have the rights required to grant it; **no license has been granted automatically**.
- Make a release only after tests and the desired live integration checks pass.
