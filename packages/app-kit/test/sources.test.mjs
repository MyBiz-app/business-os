import { checkSources } from "./support.mjs";

checkSources(new URL("../src", import.meta.url).pathname);
