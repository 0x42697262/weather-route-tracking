import { readFileSync, readdirSync, statSync } from "node:fs";
import { join, relative } from "node:path";
import ts from "typescript";

const ROOT_DIR = process.cwd();
const SCANNED_ROOTS = ["src", "scripts", "vite.config.ts", "eslint.config.js"];
const SOURCE_EXTENSION = /\.(ts|tsx|js|mjs)$/;
const GENERATED_FILES = new Set(["src/api/schema.d.ts"]);
const ALLOWED_COMMENT = /^\/[/*]\s*(eslint-disable|eslint-enable|@ts-expect-error)/;
const FAILURE_EXIT_CODE = 1;

function sourceFiles(path) {
  if (statSync(path).isFile()) {
    return SOURCE_EXTENSION.test(path) ? [path] : [];
  }
  return readdirSync(path).flatMap((entry) => sourceFiles(join(path, entry)));
}

function commentRanges(sourceFile) {
  const text = sourceFile.getFullText();
  const ranges = new Map();
  const collect = (node) => {
    const leading = ts.getLeadingCommentRanges(text, node.getFullStart()) ?? [];
    const trailing = ts.getTrailingCommentRanges(text, node.getEnd()) ?? [];
    const insideJsxBraces = ts.isJsxExpression(node)
      ? [
          ...(ts.getLeadingCommentRanges(text, node.getStart() + 1) ?? []),
          ...(ts.getTrailingCommentRanges(text, node.getStart() + 1) ?? []),
        ]
      : [];
    for (const range of [...leading, ...trailing, ...insideJsxBraces]) {
      ranges.set(range.pos, range);
    }
    ts.forEachChild(node, collect);
  };
  collect(sourceFile);
  collect(sourceFile.endOfFileToken);
  return [...ranges.values()];
}

function commentViolations(path, text) {
  const sourceFile = ts.createSourceFile(path, text, ts.ScriptTarget.Latest, true);
  return commentRanges(sourceFile)
    .map((range) => ({
      line: sourceFile.getLineAndCharacterOfPosition(range.pos).line + 1,
      comment: text.slice(range.pos, range.end),
    }))
    .filter(({ comment }) => !ALLOWED_COMMENT.test(comment));
}

const violations = SCANNED_ROOTS.flatMap((root) => sourceFiles(join(ROOT_DIR, root)))
  .filter((path) => !GENERATED_FILES.has(relative(ROOT_DIR, path)))
  .flatMap((path) =>
    commentViolations(path, readFileSync(path, "utf8")).map(
      ({ line, comment }) => `${relative(ROOT_DIR, path)}:${line}: ${comment}`,
    ),
  );

for (const violation of violations) {
  process.stdout.write(`${violation}\n`);
}
process.exitCode = violations.length > 0 ? FAILURE_EXIT_CODE : 0;
