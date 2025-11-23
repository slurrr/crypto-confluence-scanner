# Git Cheat Sheet (Quick Reference)

## Basics

### Check repo status
```bash
git status
```

Shows:
- Which branch you're on
- Which files are modified / staged
- Whether you're ahead/behind GitHub

---

### Get latest changes from GitHub
```bash
git pull origin main
```

Use this at the **start** of a work session.

If you're working on a different branch, replace `main` with that branch name.

---

### Stage changes

Stage a single file:
```bash
git add path/to/file.py
```

Stage everything:
```bash
git add .
```

---

### Commit staged changes
```bash
git commit -m "Short description of what you changed"
```

---

### Push local commits to GitHub
```bash
git push origin main
```

Replace `main` if pushing from a feature branch.

Use this at the **end** of a work session.

---

## Branches

### Create and switch to a new feature branch
```bash
git checkout -b feature/my-feature-name
```

First push for new branches:
```bash
git push -u origin feature/my-feature-name
```

---

### Switch between branches
```bash
git checkout main
git checkout feature/my-feature-name
```

> Tip: Always `git pull` after switching to a branch.

---

### Merge branches
```bash
# 1) Make sure you're up to date
git checkout feature/data-layer
git pull

# 2) Switch to main
git checkout main
git pull

# 3) Merge the branch
git merge feature/data-layer

# 4) Push
git push origin main


```

> Tip: Always `git pull` after switching to a branch.

---

## Undo / Discard

### Discard changes in a single file (revert to last commit)
```bash
git checkout -- path/to/file.py
```

### Discard ALL uncommitted changes (**Dangerous**)
```bash
git reset --hard
```

This wipes everything not committed.

---

## Typical Daily Workflow

1. **Start work**
   ```bash
   git checkout main
   git pull origin main
   git checkout -b feature/whatever   # if starting a new feature
   ```

2. **Make edits in VS Code**

3. **Commit locally**
   ```bash
   git status
   git add .
   git commit -m "Implement X/Y/Z"
   ```

4. **Push to GitHub**
   ```bash
   git push
   ```

5. *(Optional)* **Open a Pull Request** on GitHub

---

## Quick Rule of Thumb

- **Pull at the beginning**  
- **Push at the end**  
- Use **feature branches** for anything beyond trivial edits  
