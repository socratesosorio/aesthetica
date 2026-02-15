#!/usr/bin/env node

import { existsSync } from 'node:fs'
import { resolve } from 'node:path'
import { spawnSync } from 'node:child_process'

const cwd = process.cwd()
const eslintBin = resolve(cwd, 'node_modules', '.bin', 'eslint')
const tscBin = resolve(cwd, 'node_modules', '.bin', 'tsc')

function run(bin, args) {
  const result = spawnSync(bin, args, {
    cwd,
    stdio: 'inherit',
    env: process.env,
  })
  return typeof result.status === 'number' ? result.status : 1
}

if (existsSync(eslintBin)) {
  process.exit(run(eslintBin, ['.']))
}

if (!existsSync(tscBin)) {
  console.error('No lint tooling found: eslint and tsc are unavailable in node_modules/.bin')
  process.exit(1)
}

console.warn('eslint is unavailable; running TypeScript lint fallback (tsc --noEmit)')
process.exit(run(tscBin, ['--noEmit']))

