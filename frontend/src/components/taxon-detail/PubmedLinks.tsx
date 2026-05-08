interface PubmedLinksProps {
  pmids?: (string | number)[];
}

export default function PubmedLinks({ pmids }: Readonly<PubmedLinksProps>) {
  if (!pmids || pmids.length === 0) return <span className="text-gray-300">—</span>;
  return (
    <div className="flex flex-wrap gap-1">
      {pmids.map((id) => (
        <a
          key={id}
          href={`https://pubmed.ncbi.nlm.nih.gov/${id}/`}
          target="_blank"
          rel="noopener noreferrer"
          className="text-xs text-blue-500 hover:underline tabular-nums"
        >
          {id}
        </a>
      ))}
    </div>
  );
}
