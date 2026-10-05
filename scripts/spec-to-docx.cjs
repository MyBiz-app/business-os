// Turns the Markdown spec (docs/spec/v3/spec.<locale>.md) into a Word document.
// Supports what the spec uses: #/##/### headings, paragraphs, "- " bullets, "1. " numbered
// items (nested by three spaces) and pipe tables. Hebrew is laid out right-to-left.
//
//   node scripts/spec-to-docx.cjs he   → docs/spec/MyBiz-Spec-he.docx
//   node scripts/spec-to-docx.cjs en   → docs/spec/MyBiz-Spec-en.docx
//
// Needs the `docx` npm package (npm i -g docx, or run from a folder that has it).

const fs = require("node:fs");
const path = require("node:path");
const {
  AlignmentType,
  BorderStyle,
  Document,
  Footer,
  HeadingLevel,
  LevelFormat,
  Packer,
  PageNumber,
  Paragraph,
  ShadingType,
  Table,
  TableCell,
  TableRow,
  TextRun,
  WidthType,
} = require("docx");

const locale = process.argv[2] === "en" ? "en" : "he";
const rtl = locale === "he";
const root = path.join(__dirname, "..");
const source = fs.readFileSync(path.join(root, "docs/spec/v3", `spec.${locale}.md`), "utf8");
const output = path.join(root, "docs/spec", `MyBiz-Spec-${locale}.docx`);

const FONT = rtl ? "Arial" : "Calibri";
const BRAND = "4F46E5";
const PAGE_WIDTH = 11906; // A4
const MARGIN = 1134; // 2 cm
const CONTENT_WIDTH = PAGE_WIDTH - 2 * MARGIN;

/** Text with **bold** segments. */
function runs(text, extra = {}) {
  return text.split(/(\*\*[^*]+\*\*)/).filter(Boolean).map((part) =>
    new TextRun({
      text: part.replace(/^\*\*|\*\*$/g, ""),
      bold: part.startsWith("**") || extra.bold,
      font: FONT,
      rightToLeft: rtl,
      size: extra.size,
      color: extra.color,
    }),
  );
}

const align = rtl ? AlignmentType.RIGHT : AlignmentType.LEFT;
const paragraph = (text, options = {}) =>
  new Paragraph({ children: runs(text, options), bidirectional: rtl, alignment: align, spacing: { after: 120 }, ...options.paragraph });

function table(lines) {
  const rows = lines
    .filter((line) => !/^\|\s*-+/.test(line))
    .map((line) => line.trim().replace(/^\||\|$/g, "").split("|").map((cell) => cell.trim()));
  const columns = rows[0].length;
  const width = Math.floor(CONTENT_WIDTH / columns);
  const widths = Array.from({ length: columns }, (_, i) => (i === columns - 1 ? CONTENT_WIDTH - width * (columns - 1) : width));
  const border = { style: BorderStyle.SINGLE, size: 4, color: "D4D4DC" };
  return new Table({
    width: { size: CONTENT_WIDTH, type: WidthType.DXA },
    columnWidths: widths,
    visuallyRightToLeft: rtl,
    rows: rows.map((cells, rowIndex) =>
      new TableRow({
        tableHeader: rowIndex === 0,
        children: cells.map((cell, i) =>
          new TableCell({
            width: { size: widths[i], type: WidthType.DXA },
            borders: { top: border, bottom: border, left: border, right: border },
            shading: rowIndex === 0 ? { type: ShadingType.CLEAR, fill: "EEF0FF", color: "auto" } : undefined,
            margins: { top: 60, bottom: 60, left: 100, right: 100 },
            children: [paragraph(cell, { bold: rowIndex === 0, size: 20, paragraph: { spacing: { after: 0 } } })],
          }),
        ),
      }),
    ),
  });
}

const children = [];
const lines = source.split("\n");
for (let i = 0; i < lines.length; i++) {
  const line = lines[i];
  if (!line.trim()) continue;
  if (line.startsWith("|")) {
    const block = [];
    while (i < lines.length && lines[i].startsWith("|")) block.push(lines[i++]);
    i--;
    children.push(table(block), new Paragraph({ children: [], spacing: { after: 120 } }));
    continue;
  }
  const heading = line.match(/^(#{1,3}) (.*)$/);
  if (heading) {
    const level = heading[1].length;
    children.push(
      new Paragraph({
        heading: [HeadingLevel.TITLE, HeadingLevel.HEADING_1, HeadingLevel.HEADING_2][level - 1],
        bidirectional: rtl,
        alignment: align,
        children: runs(heading[2]),
        spacing: { before: level === 1 ? 0 : 280, after: 140 },
      }),
    );
    continue;
  }
  const bullet = line.match(/^(\s*)- (.*)$/);
  if (bullet) {
    children.push(new Paragraph({ numbering: { reference: "bullets", level: bullet[1].length >= 3 ? 1 : 0 }, bidirectional: rtl, alignment: align, children: runs(bullet[2]), spacing: { after: 60 } }));
    continue;
  }
  const numbered = line.match(/^(\s*)\d+\. (.*)$/);
  if (numbered) {
    children.push(new Paragraph({ numbering: { reference: "numbers", level: numbered[1].length >= 3 ? 1 : 0 }, bidirectional: rtl, alignment: align, children: runs(numbered[2]), spacing: { after: 60 } }));
    continue;
  }
  children.push(paragraph(line));
}

const indent = (level) => ({ indent: { left: 540 + level * 360, hanging: 300 } });
const doc = new Document({
  creator: "MyBiz",
  title: locale === "he" ? "MyBiz — אפיון מוצר" : "MyBiz — Product Specification",
  styles: {
    default: { document: { run: { font: FONT, size: 22 } } },
    paragraphStyles: [
      { id: "Title", name: "Title", basedOn: "Normal", run: { size: 44, bold: true, color: BRAND, font: FONT } },
      { id: "Heading1", name: "Heading 1", basedOn: "Normal", next: "Normal", quickFormat: true, run: { size: 32, bold: true, color: BRAND, font: FONT }, paragraph: { outlineLevel: 0 } },
      { id: "Heading2", name: "Heading 2", basedOn: "Normal", next: "Normal", quickFormat: true, run: { size: 26, bold: true, font: FONT }, paragraph: { outlineLevel: 1 } },
    ],
  },
  numbering: {
    config: [
      { reference: "bullets", levels: [0, 1].map((level) => ({ level, format: LevelFormat.BULLET, text: level ? "◦" : "•", alignment: align, style: { paragraph: indent(level) } })) },
      { reference: "numbers", levels: [0, 1].map((level) => ({ level, format: LevelFormat.DECIMAL, text: `%${level + 1}.`, alignment: align, style: { paragraph: indent(level) } })) },
    ],
  },
  sections: [
    {
      properties: { page: { size: { width: PAGE_WIDTH, height: 16838 }, margin: { top: MARGIN, bottom: MARGIN, left: MARGIN, right: MARGIN } } },
      footers: {
        default: new Footer({
          children: [new Paragraph({ alignment: AlignmentType.CENTER, children: [new TextRun({ children: ["MyBiz · ", PageNumber.CURRENT], font: FONT, size: 18, color: "71717A" })] })],
        }),
      },
      children,
    },
  ],
});

Packer.toBuffer(doc).then((buffer) => {
  fs.writeFileSync(output, buffer);
  console.log(`wrote ${path.relative(root, output)}`);
});
