import { useState } from "react";
import { fmt, fmtPct } from "../../utils/format";
import type { CladeCell, CladeColumn, CladeNode, CladeResponse, CladeUnit } from "../../api/types";

// Levels open on first render: the anchor (0) and its children (1), so
// grandchildren are visible and anything deeper starts collapsed. Clicking
// Bacteria-level taxa would otherwise render thousands of rows at once.
const OPEN_DEPTH = 2;
// Children shown per parent before the rest fold into one summary row. A genus
// can hold dozens of sibling species that only the control carries, which
// buries the few taxa the reviewer needs. Children arrive sorted by signal, so
// the strongest survive the cut — and anything with signal in the sample is
// never folded, however weak.
const CHILD_LIMIT = 10;
const INDENT_PX = 16;

const COLUMN_LABEL: Record<CladeColumn["sample_type"], string> = {
  sample: "sample",
  positive_ctrl: "positive ctrl",
  negative_ctrl: "NTC",
};

type Row =
  | { kind: "taxon"; node: CladeNode; depth: number }
  | { kind: "more"; parentId: number; folded: CladeNode[]; depth: number };

interface CladeTreeProps {
  data: CladeResponse;
}

/**
 * Every taxon under the anchor with signal in the sample or a negative
 * control, one column per sample. The parent keys this component by
 * classifier and anchor, so expansion state resets when either changes.
 */
export default function CladeTree({ data }: Readonly<CladeTreeProps>) {
  const clickedPath = new Set(pathTo(data.root, data.clicked.taxon_id) ?? []);
  const sampleColumn = data.columns[0]?.sample_id ?? "";
  const [expanded, setExpanded] = useState(() => initialExpanded(data.root, clickedPath));
  const [unfolded, setUnfolded] = useState<Set<number>>(() => new Set());

  const rows = visibleRows(data.root, {
    expanded,
    unfolded,
    sampleColumn,
    keepIds: clickedPath,
  });

  return (
    <div className="overflow-x-auto">
      <table className="w-full text-left">
        <thead>
          <tr>
            <th className="px-4 py-2 text-xs font-medium text-gray-400 border-b border-gray-100">
              Taxon
            </th>
            {data.columns.map((col) => (
              <th
                key={col.sample_id}
                className="px-3 py-2 text-right border-b border-gray-100 align-bottom"
              >
                <div
                  className="text-xs font-mono text-gray-600 truncate max-w-[10rem] ml-auto"
                  title={col.sample_id}
                >
                  {col.sample_id}
                </div>
                <div className="text-[10px] uppercase tracking-wider text-gray-400">
                  {COLUMN_LABEL[col.sample_type]}
                </div>
                <div className="text-[10px] text-gray-400 tabular-nums">
                  {columnTotal(col, data.unit)}
                </div>
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((row) =>
            row.kind === "taxon" ? (
              <TaxonRow
                key={row.node.taxon_id}
                node={row.node}
                depth={row.depth}
                columns={data.columns}
                unit={data.unit}
                isClicked={row.node.taxon_id === data.clicked.taxon_id}
                isOpen={expanded.has(row.node.taxon_id)}
                onToggle={() => setExpanded(toggled(expanded, row.node.taxon_id))}
              />
            ) : (
              <MoreRow
                key={`more-${row.parentId}`}
                folded={row.folded}
                depth={row.depth}
                columns={data.columns}
                unit={data.unit}
                onShow={() => setUnfolded(toggled(unfolded, row.parentId))}
              />
            )
          )}
        </tbody>
      </table>
    </div>
  );
}

interface TaxonRowProps {
  node: CladeNode;
  depth: number;
  columns: CladeColumn[];
  unit: CladeUnit;
  isClicked: boolean;
  isOpen: boolean;
  onToggle: () => void;
}

function TaxonRow({
  node,
  depth,
  columns,
  unit,
  isClicked,
  isOpen,
  onToggle,
}: Readonly<TaxonRowProps>) {
  const hasChildren = node.children.length > 0;
  return (
    <tr
      aria-current={isClicked ? "true" : undefined}
      className={`border-t border-gray-50 align-top ${
        isClicked ? "bg-blue-50" : "hover:bg-gray-50"
      }`}
    >
      <td className="px-4 py-1.5">
        <div className="flex items-start gap-1.5" style={{ paddingLeft: depth * INDENT_PX }}>
          {hasChildren ? (
            <button
              type="button"
              onClick={onToggle}
              aria-expanded={isOpen}
              aria-label={`${isOpen ? "Collapse" : "Expand"} ${node.name}`}
              className="w-4 h-4 mt-0.5 flex-shrink-0 text-gray-400 hover:text-gray-700"
            >
              {isOpen ? "▾" : "▸"}
            </button>
          ) : (
            <span className="w-4 flex-shrink-0" />
          )}
          <div className="min-w-0">
            <span
              className={`text-xs italic ${node.is_connector ? "text-gray-400" : "text-gray-800"}`}
              title={
                node.is_connector
                  ? "No signal assigned directly to this taxon; shown to connect the taxa below it"
                  : undefined
              }
            >
              {node.name}
            </span>
            <span className="ml-1.5 text-[10px] text-gray-400">
              {node.rank ?? "no rank"} · {node.taxon_id}
            </span>
            {node.merged_from.length > 0 && (
              <div className="text-[10px] text-amber-600">
                includes retired taxid {node.merged_from.join(", ")}
              </div>
            )}
          </div>
        </div>
      </td>
      {columns.map((col) => (
        <ValueCell
          key={col.sample_id}
          cell={node.cells[col.sample_id]}
          unit={unit}
          showDirect={hasChildren}
        />
      ))}
    </tr>
  );
}

interface MoreRowProps {
  folded: CladeNode[];
  depth: number;
  columns: CladeColumn[];
  unit: CladeUnit;
  onShow: () => void;
}

/** The taxa folded away under one parent, with their combined signal. */
function MoreRow({ folded, depth, columns, unit, onShow }: Readonly<MoreRowProps>) {
  return (
    <tr className="border-t border-gray-50 align-top hover:bg-gray-50">
      <td className="px-4 py-1.5">
        <div className="flex items-start gap-1.5" style={{ paddingLeft: depth * INDENT_PX }}>
          <span className="w-4 flex-shrink-0 text-gray-400">▸</span>
          <button
            type="button"
            onClick={onShow}
            className="text-xs text-gray-500 hover:text-gray-800 underline text-left"
          >
            {folded.length} more taxa
          </button>
        </div>
      </td>
      {columns.map((col) => (
        <ValueCell
          key={col.sample_id}
          cell={foldedCell(folded, col.sample_id)}
          unit={unit}
          showDirect={false}
        />
      ))}
    </tr>
  );
}

interface ValueCellProps {
  cell: CladeCell | undefined;
  unit: CladeUnit;
  // Parents show their direct signal separately; for a leaf it equals clade.
  showDirect: boolean;
}

function ValueCell({ cell, unit, showDirect }: Readonly<ValueCellProps>) {
  if (!cell) {
    return (
      <td
        className="px-3 py-1.5 text-right text-xs text-gray-300"
        title="No profile for this classifier"
      >
        —
      </td>
    );
  }
  const empty = cell.clade === 0;
  return (
    <td className="px-3 py-1.5 text-right tabular-nums">
      <div className={`text-xs ${empty ? "text-gray-300" : "text-gray-800"}`}>
        {formatValue(cell.clade, unit)}
      </div>
      {!empty && cell.clade_rpm !== null && (
        <div className="text-[10px] text-gray-400">{formatRpm(cell.clade_rpm)}</div>
      )}
      {showDirect && cell.direct > 0 && (
        <div className="text-[10px] text-gray-400">{formatValue(cell.direct, unit)} direct</div>
      )}
    </td>
  );
}

/** Combined signal of folded taxa in one column; undefined when it has no cells. */
function foldedCell(folded: CladeNode[], sampleId: string): CladeCell | undefined {
  const cells = folded.map((n) => n.cells[sampleId]).filter((c): c is CladeCell => Boolean(c));
  if (cells.length === 0) return undefined;
  const clade = cells.reduce((sum, c) => sum + c.clade, 0);
  const rpms = cells.map((c) => c.clade_rpm).filter((r): r is number => r !== null);
  return {
    direct: clade,
    clade,
    direct_rpm: null,
    clade_rpm: rpms.length === cells.length ? rpms.reduce((a, b) => a + b, 0) : null,
  };
}

function formatValue(value: number, unit: CladeUnit): string {
  return unit === "fraction" ? fmtPct(value * 100, 2) : fmt(value);
}

function formatRpm(rpm: number): string {
  return `${fmt(rpm, rpm < 10 ? 1 : 0)} rpm`;
}

function columnTotal(col: CladeColumn, unit: CladeUnit): string {
  if (!col.has_profile) return "no profile";
  if (unit === "fraction" || col.classifier_total === null) return "relative abundance";
  return `${fmt(col.classifier_total)} reads`;
}

function toggled(current: Set<number>, id: number): Set<number> {
  const next = new Set(current);
  if (next.has(id)) next.delete(id);
  else next.add(id);
  return next;
}

/** Nodes open on first render: the top OPEN_DEPTH levels plus the clicked taxon's path. */
function initialExpanded(root: CladeNode, clickedPath: Set<number>): Set<number> {
  const open = new Set<number>();
  const walk = (node: CladeNode, depth: number) => {
    if (depth >= OPEN_DEPTH) return;
    open.add(node.taxon_id);
    node.children.forEach((child) => walk(child, depth + 1));
  };
  walk(root, 0);
  // Ancestors of the clicked taxon, so its highlighted row is never hidden.
  for (const taxonId of clickedPath) open.add(taxonId);
  return open;
}

/** Taxon IDs from *node* down to *targetId*, inclusive; null when absent. */
function pathTo(node: CladeNode, targetId: number): number[] | null {
  if (node.taxon_id === targetId) return [node.taxon_id];
  for (const child of node.children) {
    const path = pathTo(child, targetId);
    if (path) return [node.taxon_id, ...path];
  }
  return null;
}

/**
 * Children to show, and those folded into a summary row.
 *
 * Kept regardless of the cap: anything with signal in the sample, and the
 * clicked taxon's own branch. A weak hit in the patient sample is exactly what
 * the reviewer is looking for, so it must never end up behind "N more taxa".
 */
function splitChildren(
  children: CladeNode[],
  sampleColumn: string,
  keepIds: Set<number>
): { shown: CladeNode[]; folded: CladeNode[] } {
  const shown: CladeNode[] = [];
  const folded: CladeNode[] = [];
  for (const child of children) {
    const inSample = (child.cells[sampleColumn]?.clade ?? 0) > 0;
    if (inSample || keepIds.has(child.taxon_id) || shown.length < CHILD_LIMIT) shown.push(child);
    else folded.push(child);
  }
  return { shown, folded };
}

interface VisibleOptions {
  expanded: Set<number>;
  unfolded: Set<number>;
  sampleColumn: string;
  keepIds: Set<number>;
}

function visibleRows(root: CladeNode, opts: VisibleOptions): Row[] {
  const rows: Row[] = [];
  const walk = (node: CladeNode, depth: number) => {
    rows.push({ kind: "taxon", node, depth });
    if (!opts.expanded.has(node.taxon_id)) return;
    if (opts.unfolded.has(node.taxon_id)) {
      node.children.forEach((child) => walk(child, depth + 1));
      return;
    }
    const { shown, folded } = splitChildren(node.children, opts.sampleColumn, opts.keepIds);
    shown.forEach((child) => walk(child, depth + 1));
    if (folded.length > 0) {
      rows.push({ kind: "more", parentId: node.taxon_id, folded, depth: depth + 1 });
    }
  };
  walk(root, 0);
  return rows;
}
