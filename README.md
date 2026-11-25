# משחק המניות (Paper Trading) — פריסה עם GitHub + Streamlit Cloud + Supabase

## 1. Supabase (מסד הנתונים)
1. היכנסו ל-supabase.com, צרו פרויקט חדש (החבילה החינמית מספיקה).
2. SQL Editor -> New query -> הדביקו את התוכן של `supabase_schema.sql` -> Run.
3. Project Settings -> API: העתיקו את **Project URL** ואת **המפתח הסודי** (`service_role`, או `secret` בממשק החדש).
   אל תשתמשו במפתח ה-`anon`/`publishable`: הטבלה חסומה אליו בכוונה.

## 2. GitHub
1. צרו ריפו חדש (אפשר פרטי) והעלו אליו את כל הקבצים. `.gitignore` כבר מוציא את הסודות והנתונים המקומיים.
2. ודאו שהקובץ `.streamlit/secrets.toml` **לא** עלה (רק ה-`.example`).

## 3. Streamlit Community Cloud
1. היכנסו ל-share.streamlit.io עם חשבון GitHub -> **Create app**.
2. בחרו את הריפו, את ה-branch, והגדירו Main file path: `app.py`.
3. Advanced settings -> **Secrets**, הדביקו:
   ```toml
   SUPABASE_URL = "https://YOUR-PROJECT-REF.supabase.co"
   SUPABASE_SERVICE_KEY = "YOUR-SECRET-KEY"
   ```
4. Deploy. שלחו לחברים את הקישור. כל אחד נרשם עם שם משתמש וסיסמה (לפחות 6 תווים).
   בסרגל הצד מופיעה השורה "אחסון: Supabase" כשהחיבור תקין.

## הרצה מקומית
```
pip install -r requirements.txt
cp .streamlit/secrets.toml.example .streamlit/secrets.toml   # למלא פרטים; בלי הקובץ הנתונים נשמרים ב-game_data.json
streamlit run app.py
```

## טיפים
- האפליקציה החינמית "נרדמת" אחרי תקופה בלי כניסות, ונדלקת מחדש בכניסה הבאה. הנתונים נשארים ב-Supabase.
- פרויקט Supabase חינמי מושהה אחרי כשבוע בלי פעילות. אפשר להפעיל אותו מחדש בלחיצה בדשבורד.
- כדי לאפס את המשחק: ב-Supabase Table Editor מחקו את השורה היחידה בטבלה `game_state`.
- כדי להגביל מי יכול לפתוח את האפליקציה: Streamlit Cloud -> Share -> הוספת כתובות מייל.
