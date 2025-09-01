GIT init & push steps (PowerShell)

Use these commands in a PowerShell terminal inside the project folder `C:\Users\mario\OneDrive\Documentos\secretaria_juliana`.

1) Check git is available
```powershell
git --version
```

2) Configure user (if needed)
```powershell
git config --global user.name "Juliana Mariano"
git config --global user.email "marioliver84@yahoo.com.br"
```

3) Initialize repo (if not already)
```powershell
cd 'C:\Users\mario\OneDrive\Documentos\secretaria_juliana'
# only run git init if repo not yet initialized
git init
```

4) Add, commit (if not committed yet)
```powershell
git add .
git commit -m "Primeira versão da secretária virtual"
```

5) Add the remote you provided and push
```powershell
# replace with the exact URL you gave
git remote add origin https://github.com/julianamariano84/secretaria-juliana.git

# if your local branch is called 'master'
git push -u origin master

# if GitHub rejects master because default is 'main', rename and push:
git branch -M main
git push -u origin main
```

6) If push is rejected due to remote history
- If the remote repo already has commits (for example a README created on GitHub), do:
```powershell
git pull --rebase origin main
# resolve conflicts if any, then
git push -u origin main
```

7) Alternative: use GitHub CLI to create & push (one step)
```powershell
# requires gh (GitHub CLI)
gh auth login
gh repo create julianamariano84/secretaria-juliana --public --source=. --remote=origin --push
```

Authentication
- Use GitHub personal access token (PAT) if Git asks for a password. Prefer Git Credential Manager on Windows.

Troubleshooting
- "git: O termo 'git' não é reconhecido": instale Git for Windows and re-open PowerShell.
- Push denied: check branch name (main vs master) and run the appropriate rename/push commands above.

