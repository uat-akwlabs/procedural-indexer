/**
 * ts-to-zod.config.js — mirrors Python models.py as zod schemas.
 * Generates src/typescript/schemas.ts from src/typescript/types.ts
 * Usage: npx ts-to-zod src/typescript/types.ts src/typescript/schemas.ts
 */
/** @type {import('ts-to-zod').TsToZodConfig} */
export default {
  // keep generated headers minimal
  nameFilter: (name) => ["PathParts","FileEntry","FileTypeIndex","IndexResult"].includes(name),
};
