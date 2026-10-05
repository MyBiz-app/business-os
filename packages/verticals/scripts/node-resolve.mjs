// Lets Node's test runner load this package's TypeScript the way bundlers do: a relative
// import without an extension resolves to the .ts file next to it. Tests that import the
// package run with `node --import @business-os/verticals/node-resolve`.
import { register } from "node:module";

register(
  "data:text/javascript," +
    encodeURIComponent(`
      export async function resolve(specifier, context, next) {
        if (specifier.startsWith(".") && !/\\.[cm]?[jt]s$|\\.json$/.test(specifier)) {
          try { return await next(specifier + ".ts", context); } catch {}
        }
        return next(specifier, context);
      }`),
  import.meta.url,
);
