import type { Subject } from "../../../api/subjects";
import KeyValueGrid, { type KvPair } from "./KeyValueGrid";
import SectionHeading from "./SectionHeading";

const SEX_LABEL: Record<string, string> = {
  F: "Female",
  M: "Male",
  X: "Other",
  unknown: "Unknown",
};

interface SubjectsSectionProps {
  subjects: Array<{ sample_id: string; subject: Subject | null }>;
}

function sexLabel(sex: string | null | undefined): string | undefined {
  if (!sex) return undefined;
  return SEX_LABEL[sex] ?? sex;
}

// Renders one block per (sample_id → subject) pair. When all samples share a
// single subject the list collapses to that subject's details only, matching
// the original SubjectSection layout.
export default function SubjectsSection({ subjects }: Readonly<SubjectsSectionProps>) {
  const linked = subjects.filter((s) => s.subject !== null);
  const distinctIds = new Set(linked.map((s) => s.subject?.subject_id));

  if (linked.length === 0) {
    return (
      <section className="report-section">
        <SectionHeading number={2} title="Subject" />
        <p className="report-soft">Not linked</p>
      </section>
    );
  }

  if (distinctIds.size === 1) {
    const subject = linked[0].subject!;
    const pairs: KvPair[] = [
      { label: "Subject ID", value: subject.subject_id, mono: true },
      { label: "Sex", value: sexLabel(subject.sex) },
    ];
    return (
      <section className="report-section">
        <SectionHeading number={2} title="Subject" />
        <KeyValueGrid pairs={pairs} />
      </section>
    );
  }

  return (
    <section className="report-section">
      <SectionHeading number={2} title="Subjects" />
      <ul className="report-subjects-list">
        {subjects.map(({ sample_id, subject }) => (
          <li key={sample_id} className="report-subject-row">
            <span className="report-mono report-subject-row-sample">{sample_id}</span>
            <span className="report-subject-row-arrow">→</span>
            <span className="report-mono">{subject?.subject_id ?? "—"}</span>
            {subject?.sex && (
              <span className="report-subject-row-sex">{sexLabel(subject.sex)}</span>
            )}
          </li>
        ))}
      </ul>
    </section>
  );
}
