interface SectionHeadingProps {
  number: number;
  title: string;
}

export default function SectionHeading({ number, title }: Readonly<SectionHeadingProps>) {
  return (
    <div className="report-section-heading">
      <span className="report-section-marker">§ {number}</span>
      <h2 className="report-section-title">{title}</h2>
    </div>
  );
}
