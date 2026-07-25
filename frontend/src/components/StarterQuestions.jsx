import { useLanguage } from "../i18n/LanguageContext";

const starters = [
  {
    icon: "🎓",
    titleKey: "starterAdmissionsTitle",
    questionKey: "starterAdmissionsQ",
  },
  {
    icon: "📝",
    titleKey: "starterRegistrationTitle",
    questionKey: "starterRegistrationQ",
  },
  {
    icon: "💰",
    titleKey: "starterTuitionTitle",
    questionKey: "starterTuitionQ",
  },
  {
    icon: "🏆",
    titleKey: "starterScholarshipsTitle",
    questionKey: "starterScholarshipsQ",
  },
  {
    icon: "📅",
    titleKey: "starterCalendarTitle",
    questionKey: "starterCalendarQ",
  },
];

export default function StarterQuestions({ onSelect }) {
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
