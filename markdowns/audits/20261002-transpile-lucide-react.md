# Audit: Transpile Lucide React Package

**Date**: 2026-10-02
**Commit topic**: transpile-lucide-react
**Severity**: Low

## Findings

### 1. Vendor Chunk Desynchronization in Next.js Dev Mode — Low

**Evidence**: Next.js 15 dev server threw `Cannot find module './vendor-chunks/lucide-react.js'` in the webpack runtime stack when loading routes utilizing Lucide icons after build or cache operations.
**Mitigation**: Adding `transpilePackages: ["lucide-react"]` in `next.config.ts` forces Next.js/Turbopack/Webpack to process `lucide-react` through standard compilation, removing dependence on fragile external vendor-chunk files.

### 2. Client Bundle Size and Build Time — Low

**Evidence**: Transpiling third-party packages can marginally increase build compilation overhead if applied to large monolithic packages.
**Mitigation**: `lucide-react` is tree-shakeable with ES module exports; `npm run build` completed in ~13 seconds with no regression in chunk size (First Load JS shared remains ~103 kB).

## Tests Not Run

- Multi-browser automated rendering checks across legacy mobile browsers were not automated.

This is a focused review of build configuration and dependency bundling, not an exhaustive security audit.
