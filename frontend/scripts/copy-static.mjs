/* Copy the static export into the Python package so `wingman web` serves it.
 * Runs automatically after `npm run build`.
 */
import { cp, rm, stat } from "node:fs/promises";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const here = dirname(fileURLToPath(import.meta.url));
const source = resolve(here, "..", "out");
const target = resolve(here, "..", "..", "src", "wingman", "web", "static");

try {
  await stat(source);
} catch {
  console.error(`No export found at ${source}. Did "next build" run?`);
  process.exit(1);
}

await rm(target, { recursive: true, force: true });
await cp(source, target, { recursive: true });
console.log(`Copied the export -> ${target}`);
