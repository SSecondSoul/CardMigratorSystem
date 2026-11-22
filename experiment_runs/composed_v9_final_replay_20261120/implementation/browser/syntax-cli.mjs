import fs from 'node:fs'
import path from 'node:path'
import {createRequire} from 'node:module'
import {inspectTarget, normalizeTarget} from './target-syntax.mjs'
const input = JSON.parse(fs.readFileSync(0, 'utf8'))
const require = createRequire(path.join(input.repository, 'package.json'))
const result = input.action === 'normalize' ? normalizeTarget(input.source, input.code, require) : inspectTarget(input.code, require)
process.stdout.write(JSON.stringify(result))
