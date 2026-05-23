# Strict Architectural & Code Quality Standards

## 1. General Constraints & Delivery
* **Zero Snippets:** Never emit partial code, placeholders, comments like "// implement logic here", or code snippets. Always output full, complete files or full, self-contained replacements of functions/classes that are drop-in ready.
* **Deterministic Logic:** Prioritize boring, well-tested, readable design patterns over clever, short, or highly compressed syntax. Code readability and future maintainability are paramount.

## 2. Robust Type Safety & Compilation
* **Strict Type Declaration:** Every file must enforce the absolute strictest type checking available for the language environment (e.g., use `declare(strict_types=1);` in PHP, or strict mode in TypeScript).
* **Explicit Signatures:** All function and method arguments, along with their return values, must have explicit data type hints. Do not rely on implicit type coercion or loose type dynamic evaluations.
* **Docblock Annotations:** Supplement type signatures with structural docblocks when utilizing complex arrays, collections, or mixed objects, defining internal keys explicitly.

## 3. Defensive Programming & Validation
* **Strict Input Validation:** Treat all incoming parameters, API payloads, and query results as untrusted. Validate types, formats, ranges, and lengths immediately at the entry boundary.
* **Fail Fast Pattern:** Evaluate guard clauses and edge cases at the very top of methods. Return early or throw specialized exceptions immediately if validation fails, minimizing nested `if-else` blocks.
* **Null Handling:** Never assume an object or database row exists. Explicitly check for `null` or empty values and provide robust, safe fallbacks or managed error outcomes.

## 4. Error Management & Resilience
* **Explicit Exceptions:** Wrap all file I/O, database interactions, network requests, and structural mutations in clean `try-catch` blocks.
* **No Swallowing Errors:** Catch blocks must never be empty. Every caught exception must either be logged with context, gracefully mitigated with a structured fallback, or re-thrown as a meaningful, custom domain exception.

## 5. Security & Persistence Integrity
* **Parameterized Queries:** Under no circumstances should variables be concatenated directly into SQL queries. Every database operation must use strictly prepared statements and bound execution parameters.
* **Sanitization:** All outputs destined for a user interface or terminal output must be explicitly escaped or sanitized based on the destination context to block injection vectors.