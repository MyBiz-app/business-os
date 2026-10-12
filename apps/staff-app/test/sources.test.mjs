import { checkSources } from "../../../packages/app-kit/test/support.mjs";

checkSources(new URL("../src", import.meta.url).pathname, {
  routes: new URL("../src/app", import.meta.url).pathname,
});
