# Changelog

כל שינוי משמעותי ב־`album_deduplicator` יתועד בקובץ זה.

הפורמט מבוסס על עקרונות `Keep a Changelog`, עם חלוקה לפי גרסאות או לפי `Unreleased` כאשר עדיין לא נוצר release רשמי.

## Unreleased

### Fixed

- סף כרטיסיית "בטוחים" מקובע לפי `SAFE_DELETE_MIN_SIMILARITY = 90`, כך שרק ציון כולל מעל 90 נחשב בטוח למחיקה.
- `run.bat` בודק כעת תלויות `Python` ו־frontend לפני פתיחת אפליקציית ה־desktop, כדי לעצור מוקדם כאשר חסרה תלות כמו `lightgbm`.
- אריזת ה־desktop כוללת כעת את מודל ה־`ML`, כך שגרסאות Windows ארוזות לא נופלות ל־scoring אלגוריתמי בלבד.
- קריאות `Gemini` מוגדרות כעת עם `thinking_level="medium"` עבור מודל `Gemini 3.1 Flash-Lite`.
- בדיקת התלויות של `run.bat` מזהה כעת נכון את חבילת `google-genai` דרך import בשם `google.genai`.

### Documentation

- תועד ש־`lightgbm` נדרש ב־`album_deduplicator/requirements.txt` עבור טעינת מודל ה־`ML` המקומי.
- נוספה תלות מפורשת ב־`google-genai>=2.3.0` עבור אינטגרציית `Gemini`.
- נוקה `README.md` מסעיף "מה חדש" ומרשימת עדכונים מצטברת.
- נוסף קובץ `CHANGELOG.md` שישמש מכאן ואילך לתיעוד שינויי קוד ועדכוני מוצר.

### Current Baseline

- היישום הראשי הוא desktop app מבוסס `Electron + React`, עם backend מקומי מבוסס `FastAPI`.
- ה־frontend משתמש ב־`Ant Design 6`, תמיכת RTL וזרימת עבודה למסכי בחירה, סריקה, סיכום, סקירה והעברה.
- מנוע הניתוח משלב scoring אלגוריתמי, מודל `ML` מקומי ו־`Gemini` אופציונלי לזוגות גבוליים.
- מחיקות מתבצעות דרך `send2trash` אל סל המחזור בלבד, לאחר אישור משתמש.
- קיימת תמיכה ב־sessions, אירועי `SSE`, שמירת החלטות משתמש, עטיפות אלבומים והשמעת שירים לצורך השוואה.
- קיימת תשתית CI/CD ל־Windows builds ול־GitHub Releases דרך tag מהצורה `album-deduplicator-vX.Y.Z`.
