# 🌐 Free Hosting Guide for Options Probability Dashboard

The dashboard is built as an ultra-fast, self-contained single-page application. Because the **Upstox API v2 supports direct browser CORS requests (`Access-Control-Allow-Origin: *`)**, you can host this dashboard **100% free forever** on any static hosting service.

Your Upstox API token is stored securely in your browser's private `localStorage`—it never gets uploaded or exposed to third-party servers.

---

## 🏆 Method 1: GitHub Pages (Recommended - 100% Free Forever)

GitHub Pages gives you a free, permanent HTTPS URL (e.g., `https://yourusername.github.io/options-dashboard`).

### Steps:
1. Initialize git and commit your files:
   ```bash
   git init
   git add .
   git commit -m "Initial commit of Options Dashboard"
   ```
2. Create a new public repository on [GitHub](https://github.com/new) (e.g. `options-dashboard`).
3. Push your code:
   ```bash
   git remote add origin https://github.com/<your-username>/options-dashboard.git
   git branch -M main
   git push -u origin main
   ```
4. On your GitHub repo page:
   - Go to **Settings** > **Pages** (in the left sidebar).
   - Under **Build and deployment** > **Source**, select **GitHub Actions** (our included `.github/workflows/deploy.yml` will handle the rest) OR select **Deploy from a branch** (`main` / root `/`).
   - Click **Save**.

Your dashboard will be live at `https://<your-username>.github.io/options-dashboard` in under 60 seconds!

---

## ⚡ Method 2: Vercel (Fastest 1-Click Deploy)

Vercel provides a free `*.vercel.app` domain with instant CDN deployment.

### Steps:
1. Install Vercel CLI (or use the Vercel web dashboard):
   ```bash
   npm i -g vercel
   ```
2. Run in this directory:
   ```bash
   vercel
   ```
3. Follow the 3 prompts (hit Enter to accept defaults).

You will immediately get a live production URL like:
`https://options-probability-dashboard.vercel.app`

---

## 🚀 Method 3: Netlify Drop (Zero Setup, Drag & Drop)

If you don't want to use Git or terminal commands:

1. Open [app.netlify.com/drop](https://app.netlify.com/drop) in your browser.
2. Drag and drop this folder (`c:\Users\gnjns\options calculator`) into the browser window.
3. Done! Netlify immediately deploys your site with a free URL (e.g., `https://amazing-options-calc.netlify.app`).

---

## 🔑 How the Upstox API Works on Hosted Sites

1. When you open your hosted dashboard on your laptop or mobile phone, click the **🔑 API Token Settings** button in the top right.
2. Paste your Upstox Bearer token (from `Upstox API.txt`).
3. Click **Save Token**.
4. The token is saved in your device's browser `localStorage`. Every time you enter a ticker like **`RELIANCE 27 OCT 1140 PUT`**, it directly fetches live quotes and option chains from Upstox!
