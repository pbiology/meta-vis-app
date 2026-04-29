import type { CaseNote } from "../../../api/types";
import SectionHeading from "./SectionHeading";

interface CommentsSectionProps {
  caseNotes: CaseNote[];
  sampleNote: string | null;
}

export default function CommentsSection({ caseNotes, sampleNote }: Readonly<CommentsSectionProps>) {
  const empty = caseNotes.length === 0 && !sampleNote;
  return (
    <section className="report-section">
      <SectionHeading number={4} title="Comments" />
      {empty ? (
        <p className="report-soft">No comments.</p>
      ) : (
        <ul className="report-comments">
          {caseNotes.map((n) => (
            <li key={n.id} className="report-comment">
              <div className="report-comment-meta">
                <span className="report-mono">{n.author}</span>
                <span>{n.created_at}</span>
              </div>
              <p className="report-comment-text">{n.text}</p>
            </li>
          ))}
          {sampleNote && (
            <li className="report-comment">
              <div className="report-comment-meta">
                <span>Sample review</span>
              </div>
              <p className="report-comment-text">{sampleNote}</p>
            </li>
          )}
        </ul>
      )}
    </section>
  );
}
