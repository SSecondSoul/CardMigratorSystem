// Parser-only diagnostic view of already frozen source and proposed code.
import fs from 'node:fs'
import {createRequire} from 'node:module'
import {templateRegions} from '../migration_system/browser/attribute-syntax.mjs'
import {normalizeTarget} from '../migration_system/browser/target-syntax.mjs'
const input=JSON.parse(fs.readFileSync(0,'utf8')),require=createRequire(input.repository+'/package.json')
const normalized=normalizeTarget(input.source,input.code,require)
process.stdout.write(JSON.stringify({syntax:normalized.after,
 source:templateRegions(input.source,require,true).filter(r=>!r.outer).map(r=>({scope:r.scope,text:r.text})),
 target:templateRegions(normalized.code,require).filter(r=>!r.outer).map(r=>({scope:r.scope,text:r.text}))}))
