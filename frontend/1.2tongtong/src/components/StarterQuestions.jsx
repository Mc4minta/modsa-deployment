import { useLanguage } from "../i18n/useLanguage";
import { Icon } from "./Icon";

const STARTERS = [
  {
    id: "registration",
    titleKey: "starterRegistrationTitle",
    questionKey: "starterRegistrationQ",
  },
  {
    id: "tuition",
    titleKey: "starterTuitionTitle",
    questionKey: "starterTuitionQ",
  },
  {
    id: "scholarships",
    titleKey: "starterScholarshipsTitle",
    questionKey: "starterScholarshipsQ",
  },
  {
    id: "calendar",
    titleKey: "starterCalendarTitle",
    questionKey: "starterCalendarQ",
  },
];

export function StarterQuestions({ onSelect }) {
  const { t } = useLanguage();

  return (
    <div className="starter-grid" aria-label={t("welcomeHint")}>
      {STARTERS.map((starter) => (
        <button
          key={starter.id}
          className="starter-card"
          onClick={() => onSelect(t(starter.questionKey))}
          type="button"
        >
          <span className="starter-copy">
            <span className="starter-title">{t(starter.titleKey)}</span>
            <span className="starter-question">{t(starter.questionKey)}</span>
          </span>
          <span className="starter-arrow">
            <Icon name="arrowRight" size={17} />
          </span>
        </button>
      ))}
    </div>
  );
}
