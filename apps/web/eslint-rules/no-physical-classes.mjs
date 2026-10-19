// Direction-neutral layout (docs/guides/design-system.md): Hebrew pages are right-to-left, so classes
// that name a physical side (ml-2, text-left, left-0, rounded-r-lg) put things on the wrong side
// in one of the two languages. Use the logical ones: ms-/me-, ps-/pe-, start-/end-, text-start/
// text-end, border-s/border-e, rounded-s/rounded-e.
const WITH_VALUE = "(?:ml|mr|pl|pr|left|right|scroll-m[lr]|scroll-p[lr])-(?:\\S|$)";
const STANDALONE =
  "(?:border-[lr]|rounded-(?:[lr]|t[lr]|b[lr])|text-(?:left|right)|float-(?:left|right)|clear-(?:left|right))(?=$|\\s|[\"'`-])";
const PHYSICAL = new RegExp(`(?:^|[\\s"'\`:!])-?(?:${WITH_VALUE}|${STANDALONE})`);

const LOGICAL_HINT = "Use the logical class (ms-/me-, ps-/pe-, start-/end-, text-start/end, border-s/e, rounded-s/e).";

/** @type {import("eslint").Rule.RuleModule} */
const rule = {
  meta: {
    type: "problem",
    docs: { description: "Disallow physical-side Tailwind classes (use logical ones so RTL and LTR both work)." },
    schema: [],
    messages: { physical: `A class names a physical side (left/right). ${LOGICAL_HINT}` },
  },
  create(context) {
    const check = (node, value) => {
      if (typeof value === "string" && PHYSICAL.test(value)) context.report({ node, messageId: "physical" });
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

const plugin = { rules: { "no-physical-classes": rule } };
export default plugin;
