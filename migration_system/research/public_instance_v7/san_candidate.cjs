/* Research-only guarded transform. The pinned upstream file is never written.
 * San is MIT licensed; its original license header remains in the evaluated source.
 */
'use strict';
const fs = require('node:fs'), path = require('node:path');
const {createHash} = require('node:crypto');
const project = path.resolve(__dirname, '../..');
const upstreamFile = path.join(project, 'engine/node_modules/san/dist/san.dev.js');
const UPSTREAM_SHA256 = '4b1c4a3a918d91663c0f79a4f77358a9de3c0ee1fbc01dfc47897f8531543134';
const digest = bytes => createHash('sha256').update(bytes).digest('hex');
const anchor = 'if (getItemKey && newLen && oldChildrenLen) {';
const guard = `
                    // Research v7: only synchronous, attached single-element-root components.
                    // Do not equate destroying/recreating a moved component with retaining it.
                    if (!childIsElem) {
                        var keyedParent = this.el && this.el.parentNode;
                        for (var keyedIndex = 0; keyedIndex < this.children.length; keyedIndex++) {
                            var keyedChild = this.children[keyedIndex];
                            if (!keyedParent || !keyedChild || keyedChild.nodeType !== NodeType.CMPT
                                || keyedChild._rootNode || keyedChild.sel || !keyedChild.el
                                || keyedChild.el.nodeType !== 1 || keyedChild.el.parentNode !== keyedParent
                                || !keyedChild.lifeCycle.attached || keyedChild.lifeCycle.disposed
                                || keyedChild.transition
                                || keyedChild.aNode.directives.transition
                                || keyedChild.source && keyedChild.source.directives.transition) {
                                throw new Error('research_keyed_component_shape_unsupported');
                            }
                        }
                        // Upstream uses object dictionaries. Reject ambiguous/reserved/duplicate keys
                        // before any keyed disposal/move; full key semantics are not claimed here.
                        var keyedLists = [this.listData, newList];
                        for (var keyedListIndex = 0; keyedListIndex < keyedLists.length; keyedListIndex++) {
                            var keyedSeen = Object.create(null);
                            for (var keyedItemIndex = 0; keyedItemIndex < keyedLists[keyedListIndex].length; keyedItemIndex++) {
                                var keyedKey = getItemKey(keyedLists[keyedListIndex][keyedItemIndex]);
                                if (typeof keyedKey !== 'string' || !keyedKey.length
                                    || keyedKey in Object.prototype || keyedSeen[keyedKey]) {
                                    throw new Error('research_keyed_component_key_unsupported');
                                }
                                keyedSeen[keyedKey] = true;
                            }
                        }
                        childIsElem = true;
                    }
`;
function buildCandidate(upstream, version = '3.15.6') {
  if (version !== '3.15.6' || digest(upstream) !== UPSTREAM_SHA256) {
    throw new Error('research_san_upstream_fingerprint_mismatch');
  }
  if (upstream.split(anchor).length !== 2) throw new Error('research_san_patch_anchor_mismatch');
  const content = upstream.replace(anchor, anchor + guard);
  return {content, candidate_sha256: digest(content), upstream_sha256: UPSTREAM_SHA256,
    upstream_version: version, patch_id: 'single-element-keyed-component-move-v7',
    production_admission_eligible: false};
}
function loadCandidate() {
  const version = JSON.parse(fs.readFileSync(path.join(project, 'engine/node_modules/san/package.json'))).version;
  return buildCandidate(fs.readFileSync(upstreamFile, 'utf8'), version);
}
function fingerprintFiles() {
  return Object.fromEntries([__filename, upstreamFile, path.join(project, 'engine/node_modules/san/package.json')]
    .map(file => [path.relative(project, file).replaceAll('\\', '/'), digest(fs.readFileSync(file))]));
}
module.exports = {buildCandidate, loadCandidate, fingerprintFiles, UPSTREAM_SHA256};
