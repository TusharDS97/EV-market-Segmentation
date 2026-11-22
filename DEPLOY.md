# Deploying the app (free, about 10 minutes)

I use Streamlit Community Cloud. It runs the app straight from your GitHub repo and gives you a public link.

## Before you start

1. The repo must be **public** on GitHub.
2. These folders must be committed, because the app reads them: `src/`, `data/clean/`, `outputs/`, plus `app.py` and `requirements.txt`.
3. Test it on your own computer first:

```powershell
pip install -r requirements.txt
python src/clean.py
python src/segment.py
streamlit run app.py
```

A browser tab opens. Click through all five tabs. If something breaks here, it will break online too.

## Push to GitHub

```powershell
git add .
git commit -m "EV market segmentation project"
git push
```

(For a new repo, create an empty one on github.com first, then `git init`, `git branch -M main`, `git remote add origin <your repo url>`, `git push -u origin main`.)

## Deploy

1. Go to **share.streamlit.io** and sign in with GitHub.
2. Click **Create app** (or **New app**), then choose your repository.
3. Branch: `main`. Main file path: `app.py`.
4. Click **Deploy**. The first build takes a few minutes while it installs the libraries.
5. Copy the link, which will look like `https://your-app-name.streamlit.app`, and paste it at the top of the README where it says "add your Streamlit link here".
6. Push the README change.

## If it doesn't work

- **"ModuleNotFoundError":** a package is missing from `requirements.txt`.
- **"FileNotFoundError ... outputs/metrics.json":** the `outputs/` folder wasn't committed. Run `git status` and commit it.
- **The app is asleep:** free apps sleep after a few days without visitors. Open the link and click the wake-up button. Do that before sharing the link with a recruiter.
- Anything else: open the app, click "Manage app" at the bottom right, copy the error log and send it to me.
