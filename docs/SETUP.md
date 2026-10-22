# What Adam needs to do

Do the steps in order and tell Claude when each one is finished. Secrets are typed into
Terminal prompts that hide what you type; Claude never sees them.

Where things stand (2026-10-22):

| Step | State |
|---|---|
| 1. Gemini key | Done |
| 2. Groq key | Done |
| 3. ACLED | Not used: ACLED's terms forbid public dashboards (their answer, 2026-10-22) |
| 4. ReliefWeb | Waiting for the approved appname |
| 5. GTD | Optional; the tool is ready, waiting for your download |
| 6. Permission requests | Optional; not sent |
| 7. Keyword review | Done (Adam checked the Slovak and Czech terms, 2026-10-22) |

All Terminal commands are run from the project folder:

```bash
cd ~/threat-dashboard
```

## Step 1. Gemini API key (unblocks phase 3)

Google's Gemini API terms require users to be 18 or older. If that is a problem, an adult at
MCS should create the key on their own Google account.

1. Open https://aistudio.google.com and sign in with your Google account.
2. Accept the terms if asked.
3. In the left panel open **Dashboard**, then **API Keys**, and click **Create API key**.
   If it asks for a project, pick the default one or create a new one.
4. Copy the key.
5. In Terminal run the command below, paste the key when asked, and press Enter:

   ```bash
   gh secret set GEMINI_API_KEY --repo Adam-d-007/threat-dashboard
   ```

6. Find your free-tier limits: in AI Studio's **Dashboard**, open the usage or rate-limit page
   for your project, and send Claude the numbers (or a screenshot) for the Flash models:
   requests per minute and requests per day. The pipeline needs about 90 requests a day.

## Step 2. Groq API key (the backup model)

1. Open https://console.groq.com and sign in (Google login is fine).
2. Open **API Keys** (https://console.groq.com/keys) and create a key named `threat-dashboard`.
3. Copy the key; Groq shows it only once.
4. In Terminal:

   ```bash
   gh secret set GROQ_API_KEY --repo Adam-d-007/threat-dashboard
   ```

## Step 3. ACLED: not used

ACLED answered on 2026-10-22 that its terms forbid dashboards built on its data from being public,
so ACLED is not part of the dashboard. Its adapter and checks were removed. You can delete the
two secrets, which nothing uses any more:

```bash
gh secret delete ACLED_EMAIL --repo Adam-d-007/threat-dashboard
```

```bash
gh secret delete ACLED_PASSWORD --repo Adam-d-007/threat-dashboard
```

## Step 4. ReliefWeb

Already requested. ReliefWeb answers by email within two business days.

1. When the approval email arrives, send Claude the approved appname. It is not a secret.
2. Claude stores it as the GitHub variable `RELIEFWEB_APPNAME` and switches the source on.

## Step 5. Global Terrorism Database (optional, for history before 2022)

1. Go to START's GTD page (start.umd.edu/gtd), choose the download, and fill in their request
   form (non-commercial, research and education use).
2. When you have the file, put it anywhere on your Mac outside the project folder, for
   example in Downloads. Its licence forbids publishing the raw file, so only yearly counts go
   into the repository.
3. Run the tool on it (replace the path with yours; for a .csv file leave out
   `--with openpyxl`):

   ```bash
   uv run --with openpyxl python -m pipeline.tools.gtd_aggregates ~/Downloads/globalterrorismdb.xlsx
   ```

4. Tell Claude. It checks `static/gtd_aggregates.json` and commits it; the next run shows the
   history on both terrorism pages. Or just tell Claude where the file is.

## Step 6. Permission requests for blocked sources (optional)

These sites block automated access or forbid it, so they can only be added with their
permission: MZV, GLOBSEC, ISW, EUvsDisinfo, Euractiv (Rapporteur), DW and PAP. Use the contact
address on each site. Claude can adapt these texts to each recipient.

**Slovak, for MZV and GLOBSEC:**

> Vážená pani, vážený pán,
>
> obraciam sa na Vás v mene neziskovej organizácie Model Conferences Slovakia, n.o. (MCS),
> ktorá sa venuje vzdelávaniu mladých ľudí v oblasti medzinárodných vzťahov, diplomacie a
> bezpečnostnej politiky a vypracúva analýzy z verejne dostupných informácií.
>
> Pripravujeme nekomerčný otvorený prehľad bezpečnostného vývoja relevantného pre Slovensko
> a EÚ, ktorý dvakrát denne zobrazuje titulky a odkazy na pôvodné zdroje. Radi by sme do neho
> zaradili aj Vaše tlačové správy a publikácie. Ochrana Vašej stránky však automatizované
> načítanie blokuje.
>
> Chcel by som sa preto zdvorilo opýtať, či by ste nám mohli poskytnúť RSS kanál alebo
> povoliť prístup nášmu nástroju (User-Agent „threat-dashboard/0.1“). Zobrazovali by sme
> výlučne názov, dátum a odkaz na Vašu stránku, s uvedením zdroja.
>
> Ďakujem za Váš čas a teším sa na Vašu odpoveď.
>
> S úctou,
> Adam, Model Conferences Slovakia, n.o.

**English, for the others:**

> Dear Sir or Madam,
>
> I am writing on behalf of Model Conferences Slovakia (MCS), a non-profit organisation that
> educates young people about international relations, diplomacy and security policy and
> produces analyses from publicly available information.
>
> We are building a non-commercial, open-source dashboard of security developments relevant
> to Slovakia and the EU, updated twice a day, which shows headlines with links back to the
> original sources. We would like to include your publications, but your site's protection
> blocks automated access.
>
> Could you provide an RSS feed, or allow access for our tool (User-Agent
> "threat-dashboard/0.1")? We would show only the title, date and a link to your page, with
> attribution, and never the full text.
>
> Thank you for considering this.
>
> Kind regards,
> Adam, Model Conferences Slovakia

## Step 7. Review the Slovak and Czech keywords

The prefilter keeps an item only if its title or snippet contains one of the terms in
`pipeline/config/keywords.yaml` (under `prefilter`, the `sk` and `cs` lists). Terms are word
beginnings without diacritics: `terori` matches "teroristický", "terorizmus" and so on. A term
ending in `!` must match a whole word.

1. Open `pipeline/config/keywords.yaml` and read the `sk` and `cs` lists.
2. Tell Claude any word that is missing (how Slovak and Czech media write about attacks,
   arrests, extremism, sabotage, espionage), and any term that catches too much.
