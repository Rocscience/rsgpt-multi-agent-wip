import {
    Table,
    TableHeader,
    TableColumn,
    TableBody,
    TableRow,
    TableCell,
    getKeyValue,
  } from "@heroui/react";
  import { Fragment, type ReactNode } from "react";
  import { jsx, jsxs } from "react/jsx-runtime";
  import { toJsxRuntime } from "hast-util-to-jsx-runtime";
  import type { Element, ElementContent, Root, Text } from "hast";

  function extractText(n: any): string {
    if (!n) return "";
    if (n.type === "text") return (n as Text).value ?? "";
    // Skip KaTeX subtrees: their hast contains the raw TeX annotation, the
    // MathML expansion, AND the visible rendered chars. Flattening all three
    // produced "0.002890.002890.00289"-style triplets in cells. We only need
    // a stable string for the column key here, so use the TeX annotation
    // when present, otherwise fall back to the visible render.
    if (n.type === "element") {
      const el = n as Element;
      const className = (el.properties?.className as string[] | undefined) ?? [];
      if (Array.isArray(className) && className.includes("katex")) {
        const annotation = findAnnotation(el);
        if (annotation) return annotation;
        const visible = (el.children as Element[]).find(
          (c) => c.type === "element" && (c.properties?.className as string[] | undefined)?.includes("katex-html"),
        );
        return visible ? extractTextRaw(visible) : extractTextRaw(el);
      }
    }
    if (Array.isArray(n.children)) return n.children.map(extractText).join("");
    return "";
  }

  function extractTextRaw(n: any): string {
    if (!n) return "";
    if (n.type === "text") return (n as Text).value ?? "";
    if (Array.isArray(n.children)) return n.children.map(extractTextRaw).join("");
    return "";
  }

  function findAnnotation(n: any): string | null {
    if (!n) return null;
    if (n.type === "element" && (n as Element).tagName === "annotation") {
      return extractTextRaw(n);
    }
    if (Array.isArray(n.children)) {
      for (const c of n.children) {
        const found = findAnnotation(c);
        if (found != null) return found;
      }
    }
    return null;
  }

  function renderChildren(children: ElementContent[], key: string): ReactNode {
    const root: Root = { type: "root", children };
    return toJsxRuntime(root, {
      Fragment,
      jsx: jsx as any,
      jsxs: jsxs as any,
      passKeys: true,
    }) as ReactNode;
  }

  function normalizeKey(label: string, i: number) {
    const k = label.trim().toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-+|-+$/g, "");
    return k || `col_${i + 1}`;
  }

  type MarkdownHeroTableProps = {
    node: Element; // hast element for <table>
    "data-aria-label"?: string; // optional passthrough
  };

  export function MarkdownHeroTable({ node, "data-aria-label": ariaLabel }: MarkdownHeroTableProps) {
    // Find thead/tbody (markdown-gfm produces them)
    const thead = (node.children as Element[]).find(
      (c) => (c as Element).tagName === "thead"
    ) as Element | undefined;

    const tbody = (node.children as Element[]).find(
      (c) => (c as Element).tagName === "tbody"
    ) as Element | undefined;

    // Header cells: keep a plain-text key for column normalization, but
    // render the label itself as a React subtree so inline math/code/links
    // in headers display correctly instead of being flattened.
    let headerEntries: { key: string; label: ReactNode; text: string }[] = [];
    if (thead) {
      const tr = (thead.children as Element[]).find((c) => (c as Element).tagName === "tr") as
        | Element
        | undefined;
      if (tr) {
        headerEntries = (tr.children as Element[])
          .filter((c) => (c as Element).tagName === "th")
          .map((th, i) => {
            const text = extractText(th) || `Column ${i + 1}`;
            return {
              key: normalizeKey(text, i),
              label: renderChildren(th.children as ElementContent[], `th-${i}`),
              text,
            };
          });
      }
    }

    // Body rows: render each <td>'s children as a React subtree so KaTeX
    // (and any other inline rehype output) is preserved as a real DOM node
    // tree instead of being plain-text-flattened.
    const bodyRows: ReactNode[][] = [];
    if (tbody) {
      (tbody.children as Element[])
        .filter((c) => (c as Element).tagName === "tr")
        .forEach((trEl, rowIdx) => {
          const tds = (trEl.children as Element[])
            .filter((c) => (c as Element).tagName === "td")
            .map((td, colIdx) =>
              renderChildren(td.children as ElementContent[], `td-${rowIdx}-${colIdx}`),
            );
          if (tds.length) bodyRows.push(tds);
        });
    }

    // If no thead, fabricate generic headers from the first body row.
    if (headerEntries.length === 0 && bodyRows.length > 0) {
      headerEntries = bodyRows[0].map((_, i) => ({
        key: `col_${i + 1}`,
        label: `Column ${i + 1}` as ReactNode,
        text: `Column ${i + 1}`,
      }));
    }

    const items = bodyRows.map((cells, rowIdx) => {
      const obj: Record<string, ReactNode> = { key: `${rowIdx}` };
      headerEntries.forEach((col, colIdx) => {
        obj[col.key] = cells[colIdx] ?? "";
      });
      return obj;
    });

    return (
      <Table
        aria-label={ariaLabel || "Table"}
        shadow="sm"
      >
        <TableHeader columns={headerEntries}>
          {(column) => (
            <TableColumn
              key={column.key}
              className="border-b border-divider bg-default-50 font-semibold"
            >
              {column.label}
            </TableColumn>
          )}
        </TableHeader>
        <TableBody items={items}>
          {(item) => (
            <TableRow
              key={item.key as string}
              className="border-b border-divider hover:bg-default-50"
            >
              {(columnKey) => (
                <TableCell className="border-r border-divider last:border-r-0">
                  {getKeyValue(item, columnKey) as ReactNode}
                </TableCell>
              )}
            </TableRow>
          )}
        </TableBody>
      </Table>
    );
  }
