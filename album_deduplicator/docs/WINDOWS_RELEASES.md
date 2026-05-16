# Windows Releases

מסמך זה מתאר את תהליך ה-`CI/CD` הנוכחי לפריסת אפליקציית ה-`Windows` של `Album Deduplicator`.

## קבצים רלוונטיים

- `frontend/package.json`
- `frontend/electron/app-version.cjs`
- `frontend/electron-builder.config.cjs`
- `frontend/scripts/sync-icons.py`
- `.github/workflows/album-deduplicator-windows-release.yml`

## מה ה-workflow עושה

ה-workflow משתמש ב-`windows-latest` ומחולק ל-3 מסלולים:

1. `verify`
   - רץ על `pull_request`, `push` ל-`main`, `workflow_dispatch`, וגם לפני release על tag
   - מתקין `Python 3.12` ו-`Node 24`
   - מריץ `python -m pytest tests -q`
   - מריץ `npm test`
   - מריץ `npm run build`

2. `package-preview`
   - רץ על `push` ל-`main` ועל `workflow_dispatch`
   - בונה מתקין `NSIS` לא חתום עם `npm run dist:desktop`
   - שומר את תוצרי האריזה תחת `frontend/desktop-dist`
   - מעלה את קובצי ה-`exe`, `blockmap`, ו-`latest.yml` כ-artifact של ה-run

3. `publish-release`
   - רץ רק על tag מהצורה `album-deduplicator-vX.Y.Z`
   - מחלץ את גרסת האפליקציה ישירות מתוך ה-tag
   - בונה ומפרסם את קובצי ה-`Windows` מתוך `frontend/desktop-dist` ל-`GitHub Releases` דרך `electron-builder`

## איך משחררים גרסה

1. ודא שהבדיקות עוברות מקומית:

```bash
cd album_deduplicator
pytest tests -q

cd frontend
npm test
npm run sync:icons
npm run dist:desktop
```

2. צור tag release:

```bash
git tag album-deduplicator-v0.1.0
git push origin album-deduplicator-v0.1.0
```

3. ה-workflow ייצור `GitHub Release` ויצרף אליו את מתקין ה-`Windows`

במהלך ה-build:

- `frontend/electron/app-version.cjs` מעדיף את `GITHUB_REF_NAME` או tag מקומי שמצביע ל-`HEAD`
- `electron-builder` מקבל את הגרסה דרך `extraMetadata.version`
- `Electron` מעביר את אותה גרסה גם ל-backend דרך `ALBUM_DEDUP_VERSION`

## למה נבחרה הגישה הזו

- `electron-builder` כבר נמצא בפרויקט ומוגדר ל-`NSIS`, כך שאין צורך להוסיף מערכת packaging נוספת
- ה-tag ב-Git הוא כעת מקור האמת לגרסת release, ולכן לא צריך לעדכן ידנית את `frontend/package.json` לפני כל שחרור
- האייקון של האפליקציה נגזר אוטומטית מתוך `album_deduplicator/frontend/build/icons/app-icon-source.png`, כך שחלון ה-`Electron`, קובץ ה-`exe`, המתקין וה-uninstaller משתמשים באותו נכס רשמי
- `GitHub Releases` הוא provider נתמך ישירות על ידי `electron-builder`, ולכן התהליך קצר ויציב יותר מפתרון custom
- הפלט כולל `latest.yml`, כך שאם בהמשך תתווסף שכבת `electron-updater`, בסיס הפרסום כבר קיים
- ה-workflow מפריד בין `preview artifacts` לבין release אמיתי, כדי לא לפרסם כל build ללקוחות
- תוצרי ה-desktop נכתבים ל-`frontend/desktop-dist` ולא ל-`frontend/dist`, כדי למנוע רקורסיה מול משאבי ה-renderer שנארזים יחד עם האפליקציה

## מגבלות נוכחיות

- המתקין עדיין לא self-contained מבחינת backend:
  - ה-`Electron shell` אורז את קוד ה-`FastAPI` כ-source resources
  - בזמן ריצה האפליקציה עדיין מצפה ל-`Python` זמין במכונה של המשתמש
- ה-release כרגע לא מבצע `code signing`
  - ב-`Windows`, אפליקציה לא חתומה עלולה לקבל אזהרות `SmartScreen`
  - ה-workflow מבטל `CSC_IDENTITY_AUTO_DISCOVERY` כדי למנוע כשלי build בסביבה לא חתומה

## תחזוקת אייקון האפליקציה

- מקור האמת של האייקון הוא `album_deduplicator/frontend/build/icons/app-icon-source.png`
- `npm run sync:icons` יוצר/מעדכן ממנו את:
  - `frontend/build/icons/app-icon.ico`
  - `frontend/public/app-icon.png`
  - `frontend/electron/assets/icons/app-icon.png`
  - `frontend/electron/assets/icons/app-icon.ico`
- `npm run build`, `npm run electron`, ו-`npm run dev:electron` מריצים את הסנכרון הזה אוטומטית, כך שכל build או הרצה של מעטפת ה-Desktop משתמשים בגרסה המעודכנת של האייקון

## שלב מומלץ הבא

אם רוצים חוויית התקנה טובה יותר למשתמשי `Windows`, שני השיפורים הטבעיים הבאים הם:

1. לארוז את ה-backend כ-executable, כדי להסיר את הדרישה ל-`Python` מותקן מראש
2. להוסיף `code signing`, רצוי דרך `Azure Trusted Signing` או תהליך signing ארגוני אחר שנתמך על ידי `electron-builder`
