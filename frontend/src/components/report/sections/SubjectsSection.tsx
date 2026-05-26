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
  subject: Subject | null;
}

function sexLabel(sex: string | null | undefined): string | undefined {
  if (!sex) return undefined;
  return SEX_LABEL[sex] ?? sex;
}

// A case belongs to at most one subject, enforced at ingest. Control-only
// cases legitimately have no subject and render an unlinked notice.
export default function SubjectsSection({ subject }: Readonly<SubjectsSectionProps>) {
  if (!subject) {
    return (
      <section className="report-section">
        <SectionHeading number={2} title="Subject" />
        <p className="report-soft">Not linked</p>
      </section>
    );
  }

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
