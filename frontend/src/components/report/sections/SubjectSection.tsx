import type { Subject } from "../../../api/subjects";
import KeyValueGrid, { type KvPair } from "./KeyValueGrid";
import SectionHeading from "./SectionHeading";

interface SubjectSectionProps {
  subject: Subject | null;
}

const SEX_LABEL: Record<string, string> = {
  F: "Female",
  M: "Male",
  X: "Other",
  unknown: "Unknown",
};

export default function SubjectSection({ subject }: Readonly<SubjectSectionProps>) {
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
    { label: "Sex", value: subject.sex ? (SEX_LABEL[subject.sex] ?? subject.sex) : undefined },
  ];

  return (
    <section className="report-section">
      <SectionHeading number={2} title="Subject" />
      <KeyValueGrid pairs={pairs} />
    </section>
  );
}
