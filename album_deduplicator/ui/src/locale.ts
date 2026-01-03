export type Language = 'en' | 'he';

export type Copy = {
  title: string;
  subtitle: string;
  heroTag: string;
  steps: string[];
  languageLabel: string;
  languageNames: { en: string; he: string };
  toasts: {
    scanStarted: string;
    scanCompleted: string;
    scanFailed: string;
    scanStartError: (message: string) => string;
    mergeSuccess: (count: number) => string;
    mergeError: (message: string) => string;
  };
  statuses: { working: string };
  folderSelector: {
    title: string;
    placeholder: string;
    add: string;
    empty: string;
  };
  configuration: {
    enableHashing: string;
    useML: string;
    useGemini: string;
    preferredBitrate: string;
    bitrateHigh: string;
    bitrate128: string;
    start: string;
    starting: string;
    availability: { available: string; unavailable: string };
  };
  similarityFilter: {
    label: (value: number) => string;
  };
  resultsExplorer: {
    visible: (count: number) => string;
    tableHeaders: { pair: string; scores: string; gemini: string; actions: string };
    notEvaluated: string;
    noRows: string;
    viewDetails: string;
  };
  qualityBadge: {
    unknown: string;
    quality: (score: number) => string;
  };
  actionReview: {
    title: string;
    subtitle: (count: number) => string;
    empty: string;
    merge: string;
    divider: string;
  };
  confirmation: {
    title: string;
    body: (count: number) => string;
    cancel: string;
    confirm: string;
  };
  comparisonDetail: {
    title: string;
    yes: string;
    no: string;
    rows: {
      weighted: string;
      mlSimilarity: string;
      combined: string;
      identical: string;
      geminiVerdict: string;
      geminiSimilarity: string;
      geminiReason: string;
      geminiError: string;
    };
  };
};

export const translations: Record<Language, Copy> = {
  en: {
    title: 'Album deduplicator',
    subtitle: 'Scan, compare, and merge duplicates with ML and Gemini-assisted verdicts.',
    heroTag: 'Dual language · RTL ready',
    steps: ['Configuration', 'Results exploration', 'Action review'],
    languageLabel: 'Language',
    languageNames: { en: 'English', he: 'עברית' },
    toasts: {
      scanStarted: 'Scan started. This may take a while...',
      scanCompleted: 'Scan completed. Explore the results below.',
      scanFailed: 'Scan failed. Check backend logs for details.',
      scanStartError: (message: string) => `Failed to start scan: ${message}`,
      mergeSuccess: (count: number) => `Merge executed for ${count} pair(s).`,
      mergeError: (message: string) => `Action failed: ${message}`,
    },
    statuses: { working: 'Working...' },
    folderSelector: {
      title: 'Folders to scan',
      placeholder: 'Add folder path',
      add: 'Add',
      empty: 'No folders selected yet.',
    },
    configuration: {
      enableHashing: 'Enable hashing',
      useML: 'Use ML similarity',
      useGemini: 'Use Gemini reasoning',
      preferredBitrate: 'Preferred bitrate',
      bitrateHigh: 'High',
      bitrate128: '128 kbps',
      start: 'Run scan',
      starting: 'Starting...',
      availability: { available: 'Available', unavailable: 'Unavailable' },
    },
    similarityFilter: {
      label: (value: number) => `Minimum similarity (${value}%)`,
    },
    resultsExplorer: {
      visible: (count: number) => `${count} pairs visible`,
      tableHeaders: { pair: 'Pair', scores: 'Scores', gemini: 'Gemini', actions: 'Actions' },
      notEvaluated: 'Not evaluated',
      noRows: 'No comparisons meet the filter yet.',
      viewDetails: 'View details',
    },
    qualityBadge: {
      unknown: 'Unknown quality',
      quality: (score: number) => `${score.toFixed(1)}% quality`,
    },
    actionReview: {
      title: 'Action review',
      subtitle: (count: number) =>
        count ? `${count} pairs selected for merge` : 'Select pairs to enable merge actions.',
      empty: 'No pairs selected yet.',
      merge: 'Merge selected',
      divider: '↔',
    },
    confirmation: {
      title: 'Execute merge action',
      body: (count: number) =>
        `You are about to merge ${count} folder pairs. The action will use the backend ActionHandler and may move or update files. Continue?`,
      cancel: 'Cancel',
      confirm: 'Confirm',
    },
    comparisonDetail: {
      title: 'Comparison details',
      yes: 'Yes',
      no: 'No',
      rows: {
        weighted: 'Weighted score',
        mlSimilarity: 'ML similarity',
        combined: 'Combined score',
        identical: 'Identical by hash',
        geminiVerdict: 'Gemini verdict',
        geminiSimilarity: 'Gemini similarity',
        geminiReason: 'Gemini reason',
        geminiError: 'Gemini error',
      },
    },
  },
  he: {
    title: 'מנקה כפילויות לאלבומים',
    subtitle: 'סרקו, השוו ומזגו כפילויות עם חיווי ML ותובנות מ-Gemini.',
    heroTag: 'דו-לשוני · תומך RTL',
    steps: ['הגדרות', 'תוצאות', 'סקירת פעולות'],
    languageLabel: 'שפה',
    languageNames: { en: 'English', he: 'עברית' },
    toasts: {
      scanStarted: 'הסריקה החלה. זה עשוי לקחת זמן...',
      scanCompleted: 'הסריקה הסתיימה. אפשר לחקור את התוצאות למטה.',
      scanFailed: 'הסריקה נכשלה. בדקו את לוגי השרת לקבלת פרטים.',
      scanStartError: (message: string) => `לא ניתן להתחיל סריקה: ${message}`,
      mergeSuccess: (count: number) => `בוצע מיזוג עבור ${count} זוגות תיקיות.`,
      mergeError: (message: string) => `הפעולה נכשלה: ${message}`,
    },
    statuses: { working: 'עובד...' },
    folderSelector: {
      title: 'תיקיות לסריקה',
      placeholder: 'הוספת נתיב תיקייה',
      add: 'הוסף',
      empty: 'לא נבחרו תיקיות.',
    },
    configuration: {
      enableHashing: 'הפעלת Hashing',
      useML: 'שימוש בדמיון ML',
      useGemini: 'הפעלת Gemini',
      preferredBitrate: 'עדיפות איכות',
      bitrateHigh: 'גבוהה',
      bitrate128: '128 kbps',
      start: 'התחלת סריקה',
      starting: 'מתחיל...',
      availability: { available: 'זמין', unavailable: 'לא זמין' },
    },
    similarityFilter: {
      label: (value: number) => `דמיון מינימלי (${value}%)`,
    },
    resultsExplorer: {
      visible: (count: number) => `${count} זוגות מוצגים`,
      tableHeaders: { pair: 'זוג', scores: 'ציונים', gemini: 'Gemini', actions: 'פעולות' },
      notEvaluated: 'לא הוערך',
      noRows: 'אין התאמות שעומדות במסנן.',
      viewDetails: 'פרטי השוואה',
    },
    qualityBadge: {
      unknown: 'איכות לא ידועה',
      quality: (score: number) => `${score.toFixed(1)}% איכות`,
    },
    actionReview: {
      title: 'סקירת פעולות',
      subtitle: (count: number) =>
        count ? `${count} זוגות נבחרו למיזוג` : 'בחרו זוגות כדי לאפשר פעולות מיזוג.',
      empty: 'עוד לא נבחרו זוגות.',
      merge: 'מיזוג נבחרים',
      divider: '↔',
    },
    confirmation: {
      title: 'אישור מיזוג',
      body: (count: number) =>
        `אתם עומדים למזג ${count} זוגות תיקיות. הפעולה תתבצע דרך ה-ActionHandler ועלולה להעביר או לעדכן קבצים. להמשיך?`,
      cancel: 'ביטול',
      confirm: 'אישור',
    },
    comparisonDetail: {
      title: 'פרטי השוואה',
      yes: 'כן',
      no: 'לא',
      rows: {
        weighted: 'ציון משוקלל',
        mlSimilarity: 'דמיון ML',
        combined: 'ציון משולב',
        identical: 'זהות לפי hash',
        geminiVerdict: 'פסק דין Gemini',
        geminiSimilarity: 'דמיון Gemini',
        geminiReason: 'הסבר Gemini',
        geminiError: 'שגיאת Gemini',
      },
    },
  },
};
