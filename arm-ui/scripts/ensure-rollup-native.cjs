'use strict'
/**
 * Rollup ships platform-specific optional binaries. On Windows ARM64 (Node
 * process.arch === 'arm64'), npm sometimes leaves only the x64 addon in
 * node_modules, which breaks `vite build`. Install the matching @rollup/* if missing.
 */
const fs = require('fs')
const path = require('path')
const { execSync } = require('child_process')

const root = path.join(__dirname, '..')

if (process.platform !== 'win32') {
  process.exit(0)
}

const bindingByArch = {
  arm64: '@rollup/rollup-win32-arm64-msvc',
  x64: '@rollup/rollup-win32-x64-msvc',
  ia32: '@rollup/rollup-win32-ia32-msvc',
}

const binding = bindingByArch[process.arch]
if (!binding) {
  process.exit(0)
}

let rollupVersion
try {
  rollupVersion = require(path.join(root, 'node_modules', 'rollup', 'package.json')).version
} catch {
  process.exit(0)
}

const pkgDir = path.join(root, 'node_modules', ...binding.split('/'))
if (fs.existsSync(path.join(pkgDir, 'package.json'))) {
  process.exit(0)
}

execSync(`npm install ${binding}@${rollupVersion} --no-save --no-audit --no-fund`, {
  stdio: 'inherit',
  cwd: root,
})
