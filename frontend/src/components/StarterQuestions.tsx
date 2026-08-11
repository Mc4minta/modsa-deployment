import { useLanguage } from "../i18n/LanguageContext";

const icons = {
  admissions: (
    <svg width="20" height="20" viewBox="0 0 20 20" fill="none" aria-hidden="true">
      <path d="M10 3L18 7L10 11L2 7L10 3Z" stroke="currentColor" strokeWidth="1.5" strokeLinejoin="round" />
      <path d="M5 9V14C5 14 7 16 10 16C13 16 15 14 15 14V9" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  ),
  registration: (
    <svg width="20" height="20" viewBox="0 0 20 20" fill="none" aria-hidden="true">
      <rect x="4" y="2.5" width="12" height="15" rx="1.5" stroke="currentColor" strokeWidth="1.5" />
      <path d="M7 7H13M7 10.5H13M7 14H10" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
    </svg>
  ),
  tuition: (
    <svg width="20" height="20" viewBox="0 0 20 20" fill="none" aria-hidden="true">
      <circle cx="10" cy="10" r="7" stroke="currentColor" strokeWidth="1.5" />
      <path d="M10 6.5V13.5M12.2 8.2C12.2 7.2 11.2 6.5 10 6.5C8.8 6.5 7.8 7.2 7.8 8.2C7.8 9.2 8.8 9.6 10 10C11.2 10.4 12.2 10.8 12.2 11.8C12.2 12.8 11.2 13.5 10 13.5C8.8 13.5 7.8 12.8 7.8 11.8" stroke="currentColor" strokeWidth="1.3" strokeLinecap="round" />
    </svg>
  ),
  scholarships: (
    <svg width="20" height="20" viewBox="0 0 20 20" fill="none" aria-hidden="true">
      <path d="M10 2L12 7H18L13 10.5L15 16L10 12.5L5 16L7 10.5L2 7H8L10 2Z" stroke="currentColor" strokeWidth="1.4" strokeLinejoin="round" />
    </svg>
  ),
  calendar: (
    <svg width="20" height="20" viewBox="0 0 20 20" fill="none" aria-hidden="true">
      <rect x="3" y="4" width="14" height="13" rx="1.5" stroke="currentColor" strokeWidth="1.5" />
      <path d="M3 8H17M6.5 2.5V5M13.5 2.5V5" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
    </svg>
  ),
};

const starters = [
  {
    icon: icons.admissions,
    titleKey: "starterAdmissionsTitle",
    questionKey: "starterAdmissionsQ",
  },
  {
    icon: icons.registration,
    titleKey: "starterRegistrationTitle",
    questionKey: "starterRegistrationQ",
  },
  {
    icon: icons.tuition,
    titleKey: "starterTuitionTitle",
    questionKey: "starterTuitionQ",
  },
  {
    icon: icons.scholarships,
    titleKey: "starterScholarshipsTitle",
    questionKey: "starterScholarshipsQ",
  },
  {
    icon: icons.calendar,
    titleKey: "starterCalendarTitle",
    questionKey: "starterCalendarQ",
  },
];

interface StarterQuestionsProps {
  onSelect: (question: string) => void;
}

export default function StarterQuestions({ onSelect }: StarterQuestionsProps) {
  const { t } = useLanguage();

  return (
    <div className="starter-questions" id="starter-questions">
      <div className="starter-grid">
        {starters.map((s, i) => (
          <button
            key={i}
            className="starter-card"
            onClick={() => onSelect(t(s.questionKey))}
            id={`starter-card-${i}`}
          >
            <span className="starter-icon">{s.icon}</span>
            <span className="starter-title">{t(s.titleKey)}</span>
            <span className="starter-question">{t(s.questionKey)}</span>
          </button>
        ))}
      </div>
    </div>
  );
}
