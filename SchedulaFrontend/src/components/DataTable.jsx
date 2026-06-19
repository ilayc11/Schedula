// src/components/DataTable.jsx
import React from "react";

export default function DataTable({
  columns,
  rows,
  rowKey,
  sort,
  onSort,
  onRowClick,
  tableClassName = "assignments-table",
  wrapClassName = "assignments-table-wrap",
  emptyText = "No results",
}) {
  const sortIndicator = (key) => {
    if (!sort || sort.key !== key) return "";
    return sort.dir === "asc" ? " ▲" : " ▼";
  };

  const handleSortClick = (sortKey) => {
    if (!sortKey || !onSort) return;
    onSort(sortKey);
  };

  return (
    <div className={wrapClassName}>
      <table className={tableClassName}>
        <thead>
          <tr>
            {columns.map((c) => {
              const clickable = Boolean(c.sortKey && onSort);
              return (
                <th
                  key={c.id || c.header}
                  onClick={() => handleSortClick(c.sortKey)}
                  style={{ cursor: clickable ? "pointer" : "default" }}
                >
                  {c.header}
                  {clickable ? sortIndicator(c.sortKey) : ""}
                </th>
              );
            })}
          </tr>
        </thead>

        <tbody>
          {rows.length === 0 ? (
            <tr>
              <td colSpan={columns.length} style={{ padding: "18px" }}>
                {emptyText}
              </td>
            </tr>
          ) : (
            rows.map((row) => (
              <tr
                key={rowKey(row)}
                onClick={onRowClick ? () => onRowClick(row) : undefined}
                style={{ cursor: onRowClick ? "pointer" : "default" }}
              >
                {columns.map((c) => (
                  <td key={c.id || c.header}>
                    {c.render ? c.render(row) : String(row?.[c.key] ?? "—")}
                  </td>
                ))}
              </tr>
            ))
          )}
        </tbody>
      </table>
    </div>
  );
}
