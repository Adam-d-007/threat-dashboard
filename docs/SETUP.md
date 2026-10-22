# What Adam needs to do

Do the steps in order and tell Claude when each one is finished. Secrets are typed into
Terminal prompts that hide what you type; Claude never sees them.

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

## Step 3. ACLED

ACLED's API only accepts an email and a password; there is no Google login for programs.
API access also needs the Research, Partner or Enterprise level. Accounts with a public
address (gmail.com) get the Open level, which has no API.

1. Check which address your Google login used. If it was a gmail.com address, register again
   at acleddata.com with adam@mcslovakia.com, because the level depends on the address.
2. Give the account a password: open https://acleddata.com/user/password, enter the same
   email address, and follow the link ACLED emails you to set a password.
3. Store the login as GitHub secrets (each command asks for the value):

   ```bash
   gh secret set ACLED_EMAIL --repo Adam-d-007/threat-dashboard
   ```

   ```bash
   gh secret set ACLED_PASSWORD --repo Adam-d-007/threat-dashboard
   ```

4. Check what the account can read. This asks for the password once, hidden, and prints a
   verdict on the last line. Replace the email if you used a different one:

   ```bash
   read -rs "ACLED_PASSWORD?ACLED password: " && echo && ACLED_EMAIL="adam@mcslovakia.com" ACLED_PASSWORD="$ACLED_PASSWORD" uv run python -m pipeline.tools.acled_check
   ```

5. Tell Claude the verdict. If it says recent events are available, Claude switches ACLED on.

## Step 4. ReliefWeb

Already requested. ReliefWeb answers by email within two business days.

1. When the approval email arrives, send Claude the approved appname. It is not a secret.
2. Claude stores it as the GitHub variable `RELIEFWEB_APPNAME` and switches the source on.

## Step 5. Global Terrorism Database (optional, for history before 2022)

1. Go to START's GTD page (start.umd.edu/gtd), choose the download, and fill in their request
   form (non-commercial, research and education use).
2. When you have the file, put it anywhere on your Mac outside the project folder and tell
   Claude where it is. Its licence forbids publishing the raw file, so only yearly counts go
   into the repository.

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

## Step 7. Later: review the keyword lists

When phase 3 adds the prefilter keyword lists, Claude will ask you to check the Slovak and
Czech terms.
