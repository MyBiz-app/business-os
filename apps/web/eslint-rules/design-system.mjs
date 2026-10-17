// Design-system guards (docs/design-system.md, "Lint rules"):
//  - no-raw-colors: colors come from the tokens (globals.css, @business-os/design-tokens), so a hex
//    value or a Tailwind palette class (bg-amber-500, text-red-600) outside the allow-list in
//    eslint.config.mjs is an error. Use text-success-ink, bg-primary/10, text-danger and so on.
//  - no-raw-button: a <button> carries a system class (btn-primary, btn-secondary, btn-ghost,
//    btn-danger, btn-link, btn-icon, btn-plain, or control) so every button looks, focuses and sizes the same.
const HEX = /(?:^|[^\w&])#(?:[0-9a-fA-F]{8}|[0-9a-fA-F]{6}|[0-9a-fA-F]{3})(?![\w-])/;
const PALETTE = new RegExp(
  "(?:^|[\\s\"'`:!])-?(?:bg|text|border|ring|from|to|via|fill|stroke|shadow|divide|outline|decoration|accent|caret|placeholder)-" +
    "(?:slate|gray|zinc|neutral|stone|red|orange|amber|yellow|lime|green|emerald|teal|cyan|sky|blue|indigo|violet|purple|fuchsia|pink|rose)-\\d{2,3}(?![\\w-])",
);
const SYSTEM_BUTTON = /(?:^|[\s"'`:!])(?:btn-(?:primary|secondary|ghost|danger|link|icon|plain)|btn-|control)(?![a-z])/;

/** @type {import("eslint").Rule.RuleModule} */
const noRawColors = {
  meta: {
    type: "problem",
    docs: { description: "Disallow hex colors and Tailwind palette classes outside the design tokens." },
    schema: [],
    messages: {
      hex: "A hex color. Use a design token (a Tailwind color such as text-primary-ink, or a CSS variable), or add this file to the allow-list in eslint.config.mjs if it is a brand mark or illustration.",
      palette: "A Tailwind palette class. Use a design token (text-success-ink, bg-primary/10, text-danger, ...), or add this file to the allow-list in eslint.config.mjs if it is an illustration.",
    },
  },
  create(context) {
    const check = (node, value) => {
      if (typeof value !== "string") return;
      if (HEX.test(value)) context.report({ node, messageId: "hex" });
      else if (PALETTE.test(value)) context.report({ node, messageId: "palette" });
    };
    return {
      Literal(node) {
        if (node.parent?.type === "ImportDeclaration" || node.parent?.type === "ExportAllDeclaration") return;
        check(node, node.value);
      },
      TemplateElement(node) {
        check(node, node.value.cooked);
      },
    };
  },
};

/** The static text of a className value: string literals and template parts anywhere inside it. */
function classText(value) {
  if (!value) return null;
  if (value.type === "Literal") return String(value.value);
  if (value.type !== "JSXExpressionContainer") return null;
  const parts = [];
  let dynamicOnly = true;
  const walk = (node) => {
    if (!node || typeof node !== "object") return;
    if (node.type === "Literal" && typeof node.value === "string") {
      parts.push(node.value);
      dynamicOnly = false;
    } else if (node.type === "TemplateElement") {
      parts.push(node.value.cooked ?? "");
      dynamicOnly = false;
    }
    for (const key of Object.keys(node)) {
      if (key === "parent" || key === "loc" || key === "range") continue;
      const child = node[key];
      if (Array.isArray(child)) child.forEach(walk);
      else if (child && typeof child.type === "string") walk(child);
    }
  };
  walk(value.expression);
  return dynamicOnly ? null : parts.join(" ");
}

/** @type {import("eslint").Rule.RuleModule} */
const noRawButton = {
  meta: {
    type: "problem",
    docs: { description: "A <button> needs a system class (btn-primary, btn-secondary, btn-ghost, btn-danger or control)." },
    schema: [],
    messages: { raw: "A raw <button>. Add a system class: btn-primary, btn-secondary, btn-ghost, btn-danger (visible buttons), btn-link (text action), btn-icon (icon only), btn-plain (a card or row that is a button) or control (globals.css)." },
  },
  create(context) {
    return {
      JSXOpeningElement(node) {
        if (node.name.type !== "JSXIdentifier" || node.name.name !== "button") return;
        const attr = node.attributes.find((a) => a.type === "JSXAttribute" && a.name.name === "className");
        // A spread may carry the class; a className that is only a variable or call cannot be checked here.
        if (node.attributes.some((a) => a.type === "JSXSpreadAttribute")) return;
        if (attr && classText(attr.value) === null) return;
        const text = attr ? classText(attr.value) : "";
        if (!SYSTEM_BUTTON.test(` ${text}`)) context.report({ node, messageId: "raw" });
      },
    };
  },
};

const plugin = { rules: { "no-raw-colors": noRawColors, "no-raw-button": noRawButton } };
export default plugin;
